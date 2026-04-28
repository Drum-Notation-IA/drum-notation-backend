"""Pydantic v2 schemas for the 2FA / OTP module."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.password_utils import validate_password_length


# ---------------------------------------------------------------------------
# Login (step 1)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        ok, errors = validate_password_length(v)
        if not ok:
            raise ValueError("; ".join(errors))
        return v


class EmailLoginRequest(BaseModel):
    """Passwordless login request - email only."""

    email: EmailStr


class RegisterRequest(BaseModel):
    """Registration payload that triggers an immediate OTP challenge."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        ok, errors = validate_password_length(v)
        if not ok:
            raise ValueError("; ".join(errors))
        return v


class LoginChallengeResponse(BaseModel):
    """Response when credentials are valid and an OTP has been dispatched."""

    challenge_token: str = Field(
        ..., description="Short-lived token to be sent back with the OTP."
    )
    otp_required: Literal[True] = True
    delivery_method: Literal["email"] = "email"
    masked_destination: str = Field(
        ..., description="Partially-masked email where the OTP was sent."
    )
    expires_in: int = Field(..., description="OTP TTL in seconds.")
    challenge_expires_in: int = Field(
        ..., description="Challenge token TTL in seconds."
    )
    resend_available_in: int = Field(
        ..., description="Seconds before /auth/resend-otp can be called."
    )
    message: str = "An OTP has been sent to your email."


# ---------------------------------------------------------------------------
# Verify OTP (step 2)
# ---------------------------------------------------------------------------

class VerifyOTPRequest(BaseModel):
    challenge_token: str = Field(..., min_length=16, max_length=256)
    otp: str = Field(..., min_length=4, max_length=10)

    @field_validator("otp")
    @classmethod
    def _otp_is_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds.")


# ---------------------------------------------------------------------------
# Resend OTP
# ---------------------------------------------------------------------------

class ResendOTPRequest(BaseModel):
    challenge_token: str = Field(..., min_length=16, max_length=256)


class ResendOTPResponse(BaseModel):
    challenge_token: str
    expires_in: int
    challenge_expires_in: int
    resend_available_in: int
    masked_destination: str
    message: str = "A new OTP has been sent to your email."


# ---------------------------------------------------------------------------
# Internal DTO (not exposed by the API)
# ---------------------------------------------------------------------------

class OTPCodeRead(BaseModel):
    id: str
    user_id: str
    purpose: str
    attempts: int
    max_attempts: int
    expires_at: datetime
    verified_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
