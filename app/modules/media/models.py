import uuid
from enum import Enum

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.shared.base_model import BaseModel


class MediaType(str, Enum):
    """Supported media types"""

    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"


class Media(BaseModel):
    __tablename__ = "media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_path = Column(Text, nullable=False)
    content_type = Column(String(100), nullable=False)
    media_type = Column(String(20), nullable=False)  # audio, video, image
    file_size = Column(Integer, nullable=False)  # Size in bytes
    description = Column(Text, nullable=True)

    # User relationship
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="media_files")

    def __repr__(self):
        return f"<Media(id={self.id}, filename={self.original_filename}, type={self.media_type})>"
