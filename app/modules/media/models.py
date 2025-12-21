import uuid

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.shared.base_model import BaseModel


class Video(BaseModel):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    filename = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=False)
    duration_seconds = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="videos")
    audio_files = relationship(
        "AudioFile", back_populates="video", cascade="all, delete-orphan"
    )
    processing_jobs = relationship(
        "ProcessingJob", back_populates="video", cascade="all, delete-orphan"
    )
    notations = relationship(
        "Notation", back_populates="video", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Video(id={self.id}, filename={self.filename}, user_id={self.user_id})>"
        )


class AudioFile(BaseModel):
    __tablename__ = "audio_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False)

    sample_rate = Column(Integer, nullable=False)
    channels = Column(Integer, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    storage_path = Column(Text, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="audio_files")
    drum_events = relationship(
        "DrumEvent", back_populates="audio_file", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AudioFile(id={self.id}, video_id={self.video_id}, sample_rate={self.sample_rate})>"
