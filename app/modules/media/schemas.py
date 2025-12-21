from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class VideoBase(BaseModel):
    filename: str = Field(..., max_length=255)


class VideoCreate(VideoBase):
    pass

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

        # Check for allowed video extensions
        allowed_extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError("Only video files are allowed (mp4, mov, avi, mkv, webm)")

        return v.strip()


class VideoUpdate(BaseModel):
    filename: Optional[str] = Field(None, max_length=255)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v):
        if v is not None:
            if not v or len(v.strip()) == 0:
                raise ValueError("Filename cannot be empty")

            # Check for dangerous characters
            dangerous_chars = ["..", "/", "\\", "<", ">", ":", '"', "|", "?", "*"]
            for char in dangerous_chars:
                if char in v:
                    raise ValueError(f"Filename contains invalid character: {char}")

            return v.strip()
        return v


class VideoRead(VideoBase):
    id: UUID
    user_id: UUID
    storage_path: str
    duration_seconds: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoReadWithDetails(VideoRead):
    user: "UserRead"
    audio_files: List["AudioFileRead"] = []
    processing_jobs: List["ProcessingJobRead"] = []
    notations: List["NotationRead"] = []

    class Config:
        from_attributes = True


class VideoUploadResponse(BaseModel):
    message: str
    video: VideoRead


class VideoListResponse(BaseModel):
    videos: List[VideoRead]
    total: int
    page: int
    per_page: int
    pages: int


# Audio File Schemas
class AudioFileBase(BaseModel):
    sample_rate: int = Field(..., ge=1, le=192000)
    channels: int = Field(..., ge=1, le=8)
    duration_seconds: Optional[float] = Field(None, ge=0)


class AudioFileCreate(AudioFileBase):
    video_id: UUID
    storage_path: str


class AudioFileRead(AudioFileBase):
    id: UUID
    video_id: UUID
    storage_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AudioFileReadWithDetails(AudioFileRead):
    video: VideoRead
    drum_events: List["DrumEventRead"] = []

    class Config:
        from_attributes = True


# Processing Job Schemas (for future use)
class ProcessingJobRead(BaseModel):
    id: UUID
    video_id: UUID
    job_type: str
    status: str
    progress: Optional[float]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


# Notation Schemas (for future use)
class NotationRead(BaseModel):
    id: UUID
    video_id: UUID
    tempo: Optional[int]
    time_signature: Optional[str]
    notation_json: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Drum Event Schemas (for future use)
class DrumEventRead(BaseModel):
    id: UUID
    audio_file_id: UUID
    time_seconds: float
    instrument: str
    velocity: Optional[float]
    confidence: Optional[float]
    model_version: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# File upload related schemas
class UploadedVideoFile(BaseModel):
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

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v):
        allowed_types = [
            "video/mp4",
            "video/quicktime",  # mov
            "video/x-msvideo",  # avi
            "video/x-matroska",  # mkv
            "video/webm",
        ]
        if v.lower() not in allowed_types:
            raise ValueError(f"Content type {v} is not allowed for video uploads")
        return v

    @field_validator("size")
    @classmethod
    def validate_size(cls, v):
        max_size = 500 * 1024 * 1024  # 500MB for video files
        if v > max_size:
            raise ValueError("Video file size exceeds maximum allowed size (500MB)")
        return v


# Statistics Schemas
class VideoStatsResponse(BaseModel):
    total_videos: int
    total_size_bytes: int
    total_size_mb: float
    total_duration_seconds: Optional[float]
    total_duration_minutes: Optional[float]
    videos_with_audio: int
    videos_with_notation: int
    storage_quota_bytes: int
    storage_quota_mb: int
    storage_used_percentage: float


# Import at the end to avoid circular imports
from app.modules.users.schemas import UserRead

# Update forward references
VideoReadWithDetails.model_rebuild()
AudioFileReadWithDetails.model_rebuild()
