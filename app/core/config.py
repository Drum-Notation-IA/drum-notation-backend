from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database settings
    DATABASE_URL_ASYNC: str = Field(..., description="Async database URL")
    DATABASE_URL_SYNC: str = Field(..., description="Sync database URL")

    # JWT settings
    SECRET_KEY: str = Field(default="your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenAI settings - handle common typos
    OPENAI_API_KEY: Optional[str] = Field(default=None, alias="OPENAI_KEY")

    # Development settings
    DEBUG: bool = False

    # File storage settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB

    # =========================
    # 2FA / OTP settings
    # =========================
    OTP_LENGTH: int = Field(default=6, ge=4, le=10, description="Number of digits in OTP")
    OTP_EXPIRE_MINUTES: int = Field(default=5, ge=1, le=30, description="OTP TTL in minutes")
    OTP_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20, description="Max verify attempts per OTP")
    OTP_RESEND_COOLDOWN_SECONDS: int = Field(default=30, ge=0, le=300, description="Seconds before allowing resend")
    OTP_LOGIN_RATE_LIMIT_PER_HOUR: int = Field(default=10, ge=1, description="Max login attempts/hour per email+IP")
    OTP_VERIFY_RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1, description="Max verify attempts/minute per IP")
    CHALLENGE_TOKEN_EXPIRE_MINUTES: int = Field(default=10, ge=1, le=60, description="Challenge token TTL")

    # =========================
    # SMTP settings (email delivery)
    # =========================
    SMTP_HOST: Optional[str] = Field(default=None, description="SMTP server host")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USERNAME: Optional[str] = Field(default=None, description="SMTP auth username")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP auth password")
    SMTP_FROM: str = Field(default="no-reply@drum-notation.local", description="From address for outgoing email")
    SMTP_FROM_NAME: str = Field(default="Drum Notation", description="From display name")
    SMTP_USE_TLS: bool = Field(default=True, description="Use STARTTLS (port 587) when True")
    SMTP_USE_SSL: bool = Field(default=False, description="Use implicit SSL (port 465) when True")
    SMTP_TIMEOUT: int = Field(default=20, description="SMTP connect/send timeout in seconds")
    OTP_EMAIL_DEBUG: bool = Field(
        default=False,
        description="If True, OTP code is logged to stdout instead of being sent (dev only)",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v):
        if (
            v == "your-secret-key-here"
            or v == "your-secret-key-here-change-in-production"
            or len(v) < 32
        ):
            import secrets
            import warnings

            warnings.warn(
                f"SECRET_KEY too short ({len(v)} chars). Generated secure one for development."
            )
            return secrets.token_urlsafe(32)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # Ignore unknown fields instead of forbidding
        case_sensitive=False,  # Allow case insensitive env vars
    )


settings = Settings()
