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
