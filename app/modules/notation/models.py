import uuid

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.shared.base_model import BaseModel


class Notation(BaseModel):
    __tablename__ = "notations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False)

    tempo = Column(Integer, nullable=True)  # BPM
    time_signature = Column(String(10), nullable=True)  # e.g., "4/4", "3/4"
    notation_json = Column(JSON, nullable=False, default=dict)  # Notation data

    # Analysis metadata
    model_version = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)  # Overall confidence (0.0-1.0)

    # Relationships
    # video = relationship("Video", back_populates="notations")
    # Note: Relationship commented out to avoid circular import issues

    def __repr__(self):
        return f"<Notation(id={self.id}, video_id={self.video_id}, tempo={self.tempo})>"


class DrumEvent(BaseModel):
    __tablename__ = "drum_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audio_file_id = Column(
        UUID(as_uuid=True), ForeignKey("audio_files.id"), nullable=False
    )

    time_seconds = Column(Float, nullable=False)  # Time position in seconds
    instrument = Column(String(50), nullable=False)  # kick, snare, hihat, etc.
    velocity = Column(Float, nullable=True)  # 0.0-1.0 velocity/intensity
    confidence = Column(Float, nullable=True)  # 0.0-1.0 detection confidence

    # Analysis metadata
    model_version = Column(String(50), nullable=True)
    onset_time = Column(Float, nullable=True)  # More precise onset time
    duration = Column(Float, nullable=True)  # Event duration in seconds

    # Relationships
    # audio_file = relationship("AudioFile", back_populates="drum_events")
    # Note: Relationship commented out to avoid circular import issues

    def __repr__(self):
        return f"<DrumEvent(id={self.id}, time={self.time_seconds}s, instrument={self.instrument})>"


class OpenAIEnrichment(BaseModel):
    __tablename__ = "openai_enrichments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notation_id = Column(UUID(as_uuid=True), ForeignKey("notations.id"), nullable=False)

    prompt_hash = Column(String(255), nullable=False)  # Hash of the input prompt
    model = Column(String(50), nullable=False)  # OpenAI model used (e.g., gpt-4)

    input_json = Column(JSON, nullable=False)  # Original input data
    output_json = Column(JSON, nullable=False)  # OpenAI response data

    # Relationships
    # notation = relationship("Notation", back_populates="openai_enrichments")
    # Note: Relationship commented out to avoid circular import issues

    def __repr__(self):
        return f"<OpenAIEnrichment(id={self.id}, notation_id={self.notation_id}, model={self.model})>"
