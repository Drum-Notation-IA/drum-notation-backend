"""Business logic for the 2FA / OTP login flow.

Pipeline
--------
1. ``start_login(email, password)`` validates credentials, invalidates any
   pending OTP for the user, generates and persists a new one (hashed),
   sends it via email and returns a temporary challenge token.

2. ``verify_otp(challenge_token, otp)`` looks up the challenge by hash,
   validates expiry / attempts / OTP, then issues the final JWT.

3. ``resend_otp(challenge_token)`` re-issues an OTP for an active challenge,
   subject to a cooldown.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.modules.auth.email_service import (
    EmailService,
    EmailServiceError,
    mask_email,
)
from app.modules.auth.models import OTPCode
from app.modules.auth.repository import OTPRepository
from app.modules.auth.schemas import (
    LoginChallengeResponse,
    ResendOTPResponse,
    TokenResponse,
)
from app.modules.auth.utils import (
    constant_time_equals,
    generate_challenge_token,
    generate_numeric_otp,
    hash_challenge_token,
    hash_otp,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate

logger = logging.getLogger(__name__)


class AuthService:
    """High-level 2FA orchestrator.

    Stateless except for its dependencies — safe to instantiate per-request
    or as a module-level singleton.
    """

    def __init__(
        self,
        otp_repo: Optional[OTPRepository] = None,
        user_repo: Optional[UserRepository] = None,
        email_service: Optional[EmailService] = None,
    ) -> None:
        self.otp_repo = otp_repo or OTPRepository()
        self.user_repo = user_repo or UserRepository()
        self.email_service = email_service or EmailService()

    # ==================================================================
    # Step 1a - login with credentials (email + password -> OTP challenge)
    # ==================================================================

    async def start_login(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginChallengeResponse:
        # Always run verify_password to keep response time roughly constant
        # whether the user exists or not (mitigates user-enumeration timing).
        user = await self.user_repo.authenticate(db, email)
        password_ok = (
            verify_password(password, str(user.password_hash)) if user else False
        )
        if not user or not password_ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await self._issue_and_send_otp(
            db,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # ==================================================================
    # Registration - create the user and dispatch an OTP in one shot
    # ==================================================================

    async def register(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginChallengeResponse:
        """Create a new user account and immediately issue an OTP challenge.

        Returns the same ``LoginChallengeResponse`` shape as the login flows so
        the client can navigate straight to the OTP verification screen and
        finish onboarding by calling ``POST /auth/verify-otp``.
        """
        # Reject duplicates with a clear 409 (vs the anti-enumeration that
        # applies to login). Registration is an explicit user action where
        # surfacing "this email is taken" is the correct UX.
        if await self.user_repo.email_exists(db, email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # Persist the user. We rely on UserRepository.create to hash the
        # password and add the row; the OTP issuance below shares the same
        # transaction so the row only commits if the email also went out.
        user = await self.user_repo.create(
            db, UserCreate(email=email, password=password)
        )
        await db.flush()

        return await self._issue_and_send_otp(
            db,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # ==================================================================
    # Step 1b - passwordless login (email-only -> OTP challenge)
    # ==================================================================

    async def start_passwordless_login(
        self,
        db: AsyncSession,
        *,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginChallengeResponse:
        """Email-only login: dispatches an OTP to the user's email if it exists.

        To prevent user enumeration the response shape is identical whether or
        not the email is registered. When the email is unknown we generate a
        decoy challenge token (not persisted) and run equivalent hashing work
        so the response time and payload are indistinguishable from a real
        challenge. Any subsequent ``/auth/verify-otp`` call will simply 401.
        """
        user = await self.user_repo.get_by_email(db, email)
        if user is not None:
            return await self._issue_and_send_otp(
                db,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        # --- Decoy branch -------------------------------------------------
        # Generate values and run hashing so the wall-clock cost roughly
        # matches the happy path. Nothing is written to the database.
        decoy_otp = generate_numeric_otp()
        decoy_token = generate_challenge_token()
        _ = hash_otp(decoy_otp)
        _ = hash_challenge_token(decoy_token)
        logger.info(
            "Passwordless login requested for unknown email; returning decoy challenge."
        )
        return LoginChallengeResponse(
            challenge_token=decoy_token,
            masked_destination=mask_email(email),
            expires_in=settings.OTP_EXPIRE_MINUTES * 60,
            challenge_expires_in=settings.CHALLENGE_TOKEN_EXPIRE_MINUTES * 60,
            resend_available_in=settings.OTP_RESEND_COOLDOWN_SECONDS,
        )

    # ------------------------------------------------------------------
    # Shared issuance helper used by both login flows
    # ------------------------------------------------------------------

    async def _issue_and_send_otp(
        self,
        db: AsyncSession,
        *,
        user: User,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> LoginChallengeResponse:
        """Invalidate previous OTPs, issue+persist a new one, send the email.

        Used by both ``start_login`` (credentials flow) and
        ``start_passwordless_login`` (email-only flow).
        """
        # Single-active-OTP policy: any pending OTP is invalidated first.
        await self.otp_repo.invalidate_active_for_user(db, user.id, purpose="login")

        otp_record, plaintext_otp, plaintext_token = await self._issue_otp(
            db,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Persist before sending the email so a delivery failure can be retried
        # via /auth/resend-otp without leaving an orphan record.
        await db.flush()

        try:
            await self.email_service.send_otp_email(
                to_email=str(user.email),
                otp=plaintext_otp,
                expire_minutes=settings.OTP_EXPIRE_MINUTES,
                ip_address=ip_address,
            )
        except EmailServiceError as exc:
            # Roll the OTP back so the user can retry cleanly.
            await self.otp_repo.soft_delete(db, otp_record.id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        return LoginChallengeResponse(
            challenge_token=plaintext_token,
            masked_destination=mask_email(str(user.email)),
            expires_in=settings.OTP_EXPIRE_MINUTES * 60,
            challenge_expires_in=settings.CHALLENGE_TOKEN_EXPIRE_MINUTES * 60,
            resend_available_in=settings.OTP_RESEND_COOLDOWN_SECONDS,
        )

    # ==================================================================
    # Step 2 - verify (OTP -> JWT)
    # ==================================================================

    async def verify_otp(
        self,
        db: AsyncSession,
        *,
        challenge_token: str,
        otp: str,
    ) -> TokenResponse:
        otp_record = await self._load_active_challenge(db, challenge_token)

        # Expiration -------------------------------------------------------
        now = datetime.utcnow()
        if otp_record.expires_at <= now:
            await self.otp_repo.soft_delete(db, otp_record.id)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="OTP has expired. Please request a new one.",
            )

        # Lockout ----------------------------------------------------------
        if int(otp_record.attempts) >= int(otp_record.max_attempts):
            await self.otp_repo.soft_delete(db, otp_record.id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many invalid attempts. This OTP has been locked, "
                    "please request a new one."
                ),
            )

        # Validate OTP (constant-time) ------------------------------------
        provided_hash = hash_otp(otp)
        is_match = constant_time_equals(provided_hash, str(otp_record.otp_hash))

        if not is_match:
            new_attempts = await self.otp_repo.increment_attempts(db, otp_record.id)
            remaining = max(int(otp_record.max_attempts) - int(new_attempts), 0)
            if remaining <= 0:
                await self.otp_repo.soft_delete(db, otp_record.id)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Too many invalid attempts. This OTP has been locked, "
                        "please request a new one."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid OTP. {remaining} attempt(s) remaining.",
            )

        # Success: consume the OTP & mint the access token ----------------
        await self.otp_repo.mark_verified_and_consumed(db, otp_record.id)

        user = await self.user_repo.get_by_id(db, otp_record.user_id)
        if not user:
            # Should never happen due to FK, but be defensive
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return self._issue_jwt(user)

    # ==================================================================
    # Resend
    # ==================================================================

    async def resend_otp(
        self,
        db: AsyncSession,
        *,
        challenge_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ResendOTPResponse:
        existing = await self._load_active_challenge(db, challenge_token)

        # Cooldown ---------------------------------------------------------
        # Measured from the last issuance time. ``updated_at`` is bumped on
        # the initial create as well as on every rotate, so it always reflects
        # "when was the latest OTP code emitted for this challenge".
        cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
        if cooldown > 0:
            last_issued_at = existing.updated_at or existing.created_at
            elapsed = (datetime.utcnow() - last_issued_at).total_seconds()
            if elapsed < cooldown:
                wait = int(cooldown - elapsed) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {wait} second(s) before requesting another OTP.",
                    headers={"Retry-After": str(wait)},
                )

        user = await self.user_repo.get_by_id(db, existing.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Rotate the OTP in-place: brand new code, fresh expiry, attempts
        # reset, but the challenge_token (and its hash) stays unchanged so the
        # client can keep using the token it already received from /auth/login
        # or /auth/login-email. This eliminates the foot-gun where a client
        # tracks a rotated token incorrectly and gets locked out with a 401.
        plaintext_otp = generate_numeric_otp()
        challenge_ttl_minutes = max(
            settings.CHALLENGE_TOKEN_EXPIRE_MINUTES,
            settings.OTP_EXPIRE_MINUTES,
        )
        new_expires_at = datetime.utcnow() + timedelta(
            minutes=challenge_ttl_minutes
        )

        await self.otp_repo.rotate_otp(
            db,
            existing.id,
            otp_hash=hash_otp(plaintext_otp),
            expires_at=new_expires_at,
        )
        await db.flush()

        try:
            await self.email_service.send_otp_email(
                to_email=str(user.email),
                otp=plaintext_otp,
                expire_minutes=settings.OTP_EXPIRE_MINUTES,
                ip_address=ip_address,
            )
        except EmailServiceError as exc:
            # Delivery failed after rotation: soft-delete to avoid leaving a
            # half-rotated row whose OTP nobody knows. The user must restart
            # the flow via /auth/login(-email).
            await self.otp_repo.soft_delete(db, existing.id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        return ResendOTPResponse(
            challenge_token=challenge_token,  # unchanged on rotation
            expires_in=settings.OTP_EXPIRE_MINUTES * 60,
            challenge_expires_in=settings.CHALLENGE_TOKEN_EXPIRE_MINUTES * 60,
            resend_available_in=settings.OTP_RESEND_COOLDOWN_SECONDS,
            masked_destination=mask_email(str(user.email)),
        )

    # ==================================================================
    # Internal helpers
    # ==================================================================

    async def _issue_otp(
        self,
        db: AsyncSession,
        *,
        user: User,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> tuple[OTPCode, str, str]:
        """Generate plaintext OTP+token, persist their hashes, return all three."""
        plaintext_otp = generate_numeric_otp()
        plaintext_token = generate_challenge_token()

        # Use the longer of the two windows so the challenge token outlives
        # the OTP itself (allowing a resend after the OTP expires).
        challenge_ttl = max(
            settings.CHALLENGE_TOKEN_EXPIRE_MINUTES,
            settings.OTP_EXPIRE_MINUTES,
        )
        otp_expires_at = datetime.utcnow() + timedelta(
            minutes=challenge_ttl,
        )

        otp_record = await self.otp_repo.create(
            db,
            user_id=user.id,
            challenge_token_hash=hash_challenge_token(plaintext_token),
            otp_hash=hash_otp(plaintext_otp),
            expires_at=otp_expires_at,
            max_attempts=settings.OTP_MAX_ATTEMPTS,
            purpose="login",
            ip_address=(ip_address or "")[:45] or None,
            user_agent=(user_agent or "")[:512] or None,
        )
        return otp_record, plaintext_otp, plaintext_token

    async def _load_active_challenge(
        self, db: AsyncSession, challenge_token: str
    ) -> OTPCode:
        token_hash = hash_challenge_token(challenge_token)
        otp_record = await self.otp_repo.get_active_by_challenge_hash(db, token_hash)
        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired challenge token.",
            )
        return otp_record

    @staticmethod
    def _issue_jwt(user: User) -> TokenResponse:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.email)},
            expires_delta=expires_delta,
        )
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
        )
