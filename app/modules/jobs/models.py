import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.shared.base_model import BaseModel


class ProcessingJob(BaseModel):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False)

    job_type = Column(
        String(50), nullable=False
    )  # e.g., 'audio_extraction', 'drum_detection', 'notation_generation'
    status = Column(
        Enum("pending", "running", "completed", "failed", name="job_status"),
        nullable=False,
        default="pending",
    )
    progress = Column(Float, nullable=True, default=0.0)  # 0.0 to 100.0
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    video = relationship("Video", back_populates="processing_jobs")

    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, video_id={self.video_id}, job_type={self.job_type}, status={self.status})>"

    def mark_as_started(self):
        """Mark job as started with current timestamp"""
        self.status = "running"
        self.started_at = datetime.utcnow()
        self.progress = 0.0

    def mark_as_completed(self):
        """Mark job as completed with current timestamp"""
        self.status = "completed"
        self.finished_at = datetime.utcnow()
        self.progress = 100.0

    def mark_as_failed(self, error_message: str):
        """Mark job as failed with error message and current timestamp"""
        self.status = "failed"
        self.finished_at = datetime.utcnow()
        self.error_message = error_message

    def update_progress(self, progress: float):
        """Update job progress (0.0 to 100.0)"""
        self.progress = max(0.0, min(100.0, progress))
