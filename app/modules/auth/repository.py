"""Repository for OTPCode entities (async SQLAlchemy 2.0)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import OTPCode


class OTPRepository:
    """Data access layer for OTP codes.

    All methods are async and accept the session as the first argument so the
    caller (service layer) controls transaction boundaries.
    """

    # ---------------------------------------------------------------- create
    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        challenge_token_hash: str,
        otp_hash: str,
        expires_at: datetime,
        max_attempts: int,
        purpose: str = "login",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OTPCode:
        otp = OTPCode(
            user_id=user_id,
            purpose=purpose,
            challenge_token_hash=challenge_token_hash,
            otp_hash=otp_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
            attempts=0,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(otp)
        await db.flush()
        await db.refresh(otp)
        return otp

    # ----------------------------------------------------------------- read
    async def get_active_by_challenge_hash(
        self, db: AsyncSession, challenge_token_hash: str
    ) -> Optional[OTPCode]:
        """Return an OTP that is not consumed and not soft-deleted.

        Expiration / attempt limits are enforced in the service layer so we
        can return precise error codes (expired vs locked vs invalid).
        """
        query = select(OTPCode).where(
            and_(
                OTPCode.challenge_token_hash == challenge_token_hash,
                OTPCode.consumed_at.is_(None),
                OTPCode.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, otp_id: UUID) -> Optional[OTPCode]:
        query = select(OTPCode).where(
            and_(OTPCode.id == otp_id, OTPCode.deleted_at.is_(None))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    # --------------------------------------------------------------- update
    async def increment_attempts(self, db: AsyncSession, otp_id: UUID) -> int:
        """Atomically increment attempts and return the new value."""
        query = (
            update(OTPCode)
            .where(OTPCode.id == otp_id)
            .values(attempts=OTPCode.attempts + 1, updated_at=datetime.utcnow())
            .returning(OTPCode.attempts)
        )
        result = await db.execute(query)
        new_value = result.scalar_one_or_none()
        return int(new_value) if new_value is not None else 0

    async def rotate_otp(
        self,
        db: AsyncSession,
        otp_id: UUID,
        *,
        otp_hash: str,
        expires_at: datetime,
    ) -> None:
        """Replace the OTP value of an existing challenge in-place.

        Used by the resend flow: the ``challenge_token`` (and therefore its
        hash) stays unchanged so the client can keep using the token it
        already received, while the OTP itself is rotated to a fresh value
        and the attempt counter is reset.
        """
        now = datetime.utcnow()
        query = (
            update(OTPCode)
            .where(OTPCode.id == otp_id)
            .values(
                otp_hash=otp_hash,
                expires_at=expires_at,
                attempts=0,
                updated_at=now,
            )
        )
        await db.execute(query)

    async def mark_verified_and_consumed(
        self, db: AsyncSession, otp_id: UUID
    ) -> None:
        now = datetime.utcnow()
        query = (
            update(OTPCode)
            .where(OTPCode.id == otp_id)
            .values(verified_at=now, consumed_at=now, updated_at=now)
        )
        await db.execute(query)

    async def soft_delete(self, db: AsyncSession, otp_id: UUID) -> None:
        now = datetime.utcnow()
        query = (
            update(OTPCode)
            .where(and_(OTPCode.id == otp_id, OTPCode.deleted_at.is_(None)))
            .values(deleted_at=now, updated_at=now)
        )
        await db.execute(query)

    async def invalidate_active_for_user(
        self, db: AsyncSession, user_id: UUID, purpose: str = "login"
    ) -> int:
        """Soft-delete every active (non-consumed, non-deleted) OTP for a user.

        Used to invalidate the previous OTP when the user requests a resend
        or starts a new login flow.
        """
        now = datetime.utcnow()
        query = (
            update(OTPCode)
            .where(
                and_(
                    OTPCode.user_id == user_id,
                    OTPCode.purpose == purpose,
                    OTPCode.consumed_at.is_(None),
                    OTPCode.deleted_at.is_(None),
                )
            )
            .values(deleted_at=now, updated_at=now)
            .returning(OTPCode.id)
        )
        result = await db.execute(query)
        return len(list(result.scalars().all()))

    # --------------------------------------------------------- housekeeping
    async def count_recent_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        within: timedelta,
        purpose: str = "login",
    ) -> int:
        """Count OTPs created for a user within a time window (for rate limiting)."""
        threshold = datetime.utcnow() - within
        query = select(func.count(OTPCode.id)).where(
            and_(
                OTPCode.user_id == user_id,
                OTPCode.purpose == purpose,
                OTPCode.created_at >= threshold,
            )
        )
        result = await db.execute(query)
        return int(result.scalar_one() or 0)

    async def get_latest_for_user(
        self, db: AsyncSession, user_id: UUID, purpose: str = "login"
    ) -> Optional[OTPCode]:
        query = (
            select(OTPCode)
            .where(
                and_(
                    OTPCode.user_id == user_id,
                    OTPCode.purpose == purpose,
                    OTPCode.deleted_at.is_(None),
                )
            )
            .order_by(OTPCode.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
