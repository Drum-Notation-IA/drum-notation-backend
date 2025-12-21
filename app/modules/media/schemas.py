from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.modules.media.models import MediaType


class MediaBase(BaseModel):
    original_filename: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class MediaCreate(MediaBase):
    content_type: str = Field(..., max_length=100)
    media_type: MediaType
    file_size: int = Field(..., gt=0)

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, v):
        # Max file size: 100MB for videos, 50MB for audio, 10MB for images
        max_sizes = {
            MediaType.VIDEO: 100 * 1024 * 1024,  # 100MB
            MediaType.AUDIO: 50 * 1024 * 1024,  # 50MB
            MediaType.IMAGE: 10 * 1024 * 1024,  # 10MB
        }
        # We'll validate against the maximum possible size here
        if v > max(max_sizes.values()):
            raise ValueError("File size exceeds maximum allowed size")
        return v


class MediaUpdate(BaseModel):
    original_filename: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class MediaRead(MediaBase):
    id: UUID
    stored_filename: str
    file_path: str
    content_type: str
    media_type: MediaType
    file_size: int
    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MediaReadWithUser(MediaRead):
    user: "UserRead"

    class Config:
        from_attributes = True


class MediaUploadResponse(BaseModel):
    message: str
    media: MediaRead


class MediaListResponse(BaseModel):
    media: list[MediaRead]
    total: int
    page: int
    per_page: int
    pages: int


# File upload related schemas
class UploadedFile(BaseModel):
    filename: str
    content_type: str
    size: int

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Filename cannot be empty")

        # Check for dangerous characters
        dangerous_chars = ["..", "/", "\\", "<", ">", ":", '"', "|", "?", "*"]
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Filename contains invalid character: {char}")

        return v.strip()


# Import at the end to avoid circular imports
from app.modules.users.schemas import UserRead

# Update forward references
MediaReadWithUser.model_rebuild()
