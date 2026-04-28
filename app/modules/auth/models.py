"""SQLAlchemy models for the 2FA / OTP module."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.shared.base_model import BaseModel


class OTPCode(BaseModel):
    """
    One-Time Password issued during a 2FA-enabled login.

    Security notes:
    - `otp_hash` stores SHA-256(otp + pepper). The plaintext OTP is only sent
      via email and never persisted.
    - `challenge_token_hash` stores SHA-256 of the temporary token returned
      to the client. The plaintext token is only known by the client; on
      verify we hash the incoming token and look it up by index.
    - `attempts` is incremented atomically on each failed verify; once
      `attempts >= max_attempts` the OTP is locked.
    - `consumed_at` marks an OTP that successfully exchanged for a JWT; it
      can never be reused (defense-in-depth alongside expiry).
    """

    __tablename__ = "otp_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'login' for now; future-proofed for password_reset, email_change, etc.
    purpose = Column(String(32), nullable=False, default="login")

    # Hex-encoded SHA-256 of the random challenge token (64 chars)
    challenge_token_hash = Column(
        String(128), nullable=False, unique=True, index=True
    )

    # Hex-encoded SHA-256 of the OTP plaintext + server pepper (64 chars)
    otp_hash = Column(String(128), nullable=False)

    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)

    expires_at = Column(DateTime, nullable=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    consumed_at = Column(DateTime, nullable=True)

    # Audit / forensic context
    ip_address = Column(String(45), nullable=True)  # supports IPv6
    user_agent = Column(String(512), nullable=True)
