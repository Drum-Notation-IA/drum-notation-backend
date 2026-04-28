"""
Auth module - 2FA / OTP login flow.

Public exports:
    OTPCode         - SQLAlchemy model
    OTPRepository   - async DB repository
    AuthService     - business logic for login + OTP verification
    EmailService    - SMTP delivery (replaceable)
    router          - FastAPI router (mounted at /auth)
"""
from .email_service import EmailService, EmailServiceError
from .models import OTPCode
from .repository import OTPRepository
from .router import router
from .schemas import (
    EmailLoginRequest,
    LoginChallengeResponse,
    LoginRequest,
    RegisterRequest,
    ResendOTPRequest,
    ResendOTPResponse,
    TokenResponse,
    VerifyOTPRequest,
)
from .service import AuthService

__all__ = [
    # Model
    "OTPCode",
    # Repository
    "OTPRepository",
    # Services
    "AuthService",
    "EmailService",
    "EmailServiceError",
    # Router
    "router",
    # Schemas
    "LoginRequest",
    "EmailLoginRequest",
    "RegisterRequest",
    "LoginChallengeResponse",
    "VerifyOTPRequest",
    "TokenResponse",
    "ResendOTPRequest",
    "ResendOTPResponse",
]
