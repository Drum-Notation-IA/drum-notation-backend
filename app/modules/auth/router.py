"""HTTP routes for the 2FA / OTP login flow.

Endpoints:
    POST /auth/login         - Validate credentials and email an OTP
    POST /auth/verify-otp    - Exchange OTP for a JWT access token
    POST /auth/resend-otp    - Re-send the OTP for an active challenge
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.modules.auth.schemas import (
    EmailLoginRequest,
    LoginChallengeResponse,
    LoginRequest,
    RegisterRequest,
    ResendOTPRequest,
    ResendOTPResponse,
    TokenResponse,
    VerifyOTPRequest,
)
from app.modules.auth.service import AuthService
from app.modules.auth.utils import login_rate_limiter, verify_rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------

def get_auth_service() -> AuthService:
    return AuthService()


def _client_ip(request: Request) -> Optional[str]:
    # Honor a single hop of X-Forwarded-For when present (typical behind a
    # reverse proxy). For multi-hop trust chains, configure your proxy to
    # rewrite this header explicitly.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


async def _enforce_rate_limit(
    limiter, key: str, max_requests: int, window_seconds: int
) -> None:
    allowed, retry_after = await limiter.hit(key, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=LoginChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and dispatch an OTP for email verification",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginChallengeResponse:
    """Register a new user and immediately start the OTP verification flow.

    On success the response carries a ``challenge_token`` that the client must
    send back to ``POST /auth/verify-otp`` together with the OTP delivered to
    the inbox to complete onboarding and receive the JWT access token.
    """
    ip = _client_ip(request)
    rl_key = f"register:{payload.email.lower()}:{ip or 'unknown'}"
    await _enforce_rate_limit(
        login_rate_limiter,
        rl_key,
        max_requests=settings.OTP_LOGIN_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    return await auth_service.register(
        db,
        email=str(payload.email),
        password=payload.password,
        ip_address=ip,
        user_agent=_user_agent(request),
    )


@router.post(
    "/login",
    response_model=LoginChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 1 - validate credentials and dispatch an OTP",
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginChallengeResponse:
    """Validate credentials and start a 2FA challenge.

    Returns a short-lived ``challenge_token`` that the client must send back
    to ``/auth/verify-otp`` together with the OTP delivered by email.
    """
    ip = _client_ip(request)
    rl_key = f"login:{payload.email.lower()}:{ip or 'unknown'}"
    await _enforce_rate_limit(
        login_rate_limiter,
        rl_key,
        max_requests=settings.OTP_LOGIN_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    return await auth_service.start_login(
        db,
        email=str(payload.email),
        password=payload.password,
        ip_address=ip,
        user_agent=_user_agent(request),
    )


@router.post(
    "/login-email",
    response_model=LoginChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 1 (passwordless) - request an OTP using only the email address",
)
async def login_email(
    payload: EmailLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginChallengeResponse:
    """Passwordless login: dispatch an OTP to the provided email.

    The response shape is identical regardless of whether the email is
    registered, to prevent user enumeration. Continue with
    ``POST /auth/verify-otp`` using the returned ``challenge_token`` and the
    OTP that arrives in the inbox.
    """
    ip = _client_ip(request)
    rl_key = f"login:{payload.email.lower()}:{ip or 'unknown'}"
    await _enforce_rate_limit(
        login_rate_limiter,
        rl_key,
        max_requests=settings.OTP_LOGIN_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    return await auth_service.start_passwordless_login(
        db,
        email=str(payload.email),
        ip_address=ip,
        user_agent=_user_agent(request),
    )


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 2 - exchange OTP for a JWT access token",
)
async def verify_otp(
    payload: VerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Verify the OTP for a given challenge and issue the final JWT."""
    ip = _client_ip(request)
    rl_key = f"verify:{ip or 'unknown'}"
    await _enforce_rate_limit(
        verify_rate_limiter,
        rl_key,
        max_requests=settings.OTP_VERIFY_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )

    return await auth_service.verify_otp(
        db,
        challenge_token=payload.challenge_token,
        otp=payload.otp,
    )


@router.post(
    "/resend-otp",
    response_model=ResendOTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-send the OTP for an active challenge",
)
async def resend_otp(
    payload: ResendOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> ResendOTPResponse:
    """Issue a new OTP for an active challenge token (subject to a cooldown)."""
    return await auth_service.resend_otp(
        db,
        challenge_token=payload.challenge_token,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
