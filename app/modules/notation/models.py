"""
Notation Models
Database models for drum notation system aligned with actual database schema
"""

import uuid
from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.shared.base_model import BaseModel


class DrumNotation(BaseModel):
    """
    Main notation record that represents a complete drum transcription
    Aligned with the 'notations' table in the database schema
    """

    __tablename__ = "notations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(
        UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True
    )

    # Musical metadata (aligned with database schema)
    tempo = Column(Integer, nullable=True)  # BPM as integer
    time_signature = Column(String(10), nullable=True)  # e.g., "4/4", "3/4"

    # Structured notation data (JSONB in database)
    notation_json = Column(JSONB, nullable=False, default=dict)

    # Timestamps are handled by BaseModel (created_at, updated_at, deleted_at)

    # Relationships
    openai_enrichments = relationship(
        "OpenAIEnrichment", back_populates="notation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<DrumNotation(id={self.id}, video_id={self.video_id}, tempo={self.tempo})>"

    @property
    def tempo_bpm(self) -> Optional[float]:
        """Convenience property for backward compatibility"""
        if isinstance(self.tempo, int) and self.tempo is not None:
            return float(self.tempo)
        return None

    @tempo_bpm.setter
    def tempo_bpm(self, value: Optional[float]) -> None:
        """Convenience setter for backward compatibility"""
        if value is not None and isinstance(value, (int, float)):
            self.tempo = int(value)
        else:
            self.tempo = None

    def get_measures(self) -> list:
        """Extract measures from notation_json"""
        return self.notation_json.get("measures", [])

    def get_timeline(self) -> list:
        """Extract stroke timeline from notation_json"""
        return self.notation_json.get("timeline", [])

    def get_musical_structure(self) -> dict:
        """Extract musical structure from notation_json"""
        return self.notation_json.get("musical_structure", {})

    def set_measures(self, measures: list) -> None:
        """Update measures in notation_json"""
        if self.notation_json is None:
            self.notation_json = {}
        if isinstance(self.notation_json, dict):
            self.notation_json["measures"] = measures

    def set_timeline(self, timeline: list) -> None:
        """Update timeline in notation_json"""
        if self.notation_json is None:
            self.notation_json = {}
        if isinstance(self.notation_json, dict):
            self.notation_json["timeline"] = timeline

    def set_musical_structure(self, structure: dict) -> None:
        """Update musical structure in notation_json"""
        if self.notation_json is None:
            self.notation_json = {}
        if isinstance(self.notation_json, dict):
            self.notation_json["musical_structure"] = structure


class OpenAIEnrichment(BaseModel):
    """
    AI-powered analysis and enrichment of drum notation
    Aligned with 'openai_enrichments' table in database schema
    """

    __tablename__ = "openai_enrichments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notation_id = Column(
        UUID(as_uuid=True), ForeignKey("notations.id"), nullable=False, index=True
    )

    # Request information
    prompt_hash = Column(Text, nullable=False, index=True)  # Hash of input for caching
    model = Column(Text, nullable=False)  # gpt-4, gpt-3.5-turbo, etc.

    # Input and output data (JSONB in database)
    input_json = Column(JSONB, nullable=False)  # Original input sent to AI
    output_json = Column(JSONB, nullable=False)  # AI response

    # Timestamps are handled by BaseModel (created_at, updated_at, deleted_at)

    # Relationships
    notation = relationship("DrumNotation", back_populates="openai_enrichments")

    def __repr__(self):
        return f"<OpenAIEnrichment(id={self.id}, notation_id={self.notation_id}, model={self.model})>"


# Data structures for JSON content (not database tables)
class StrokeEvent:
    """
    Timeline-based stroke event for JSON storage
    """

    def __init__(
        self,
        timestamp_seconds: float,
        drum_type: str,
        velocity: float,
        measure_number: int,
        beat_number: float,
        staff_position: str,
        note_head_type: str = "normal",
        accent: Optional[str] = None,
        ghost_note: bool = False,
        confidence_score: Optional[float] = None,
    ):
        self.timestamp_seconds = timestamp_seconds
        self.drum_type = drum_type
        self.velocity = velocity
        self.measure_number = measure_number
        self.beat_number = beat_number
        self.staff_position = staff_position
        self.note_head_type = note_head_type
        self.accent = accent
        self.ghost_note = ghost_note
        self.confidence_score = confidence_score

    def to_dict(self) -> dict:
        return {
            "timestamp_seconds": self.timestamp_seconds,
            "drum_type": self.drum_type,
            "velocity": self.velocity,
            "measure_number": self.measure_number,
            "beat_number": self.beat_number,
            "staff_position": self.staff_position,
            "note_head_type": self.note_head_type,
            "accent": self.accent,
            "ghost_note": self.ghost_note,
            "confidence_score": self.confidence_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrokeEvent":
        return cls(**data)


class NotationExport:
    """
    Export metadata for JSON storage
    """

    def __init__(
        self,
        export_format: str,
        file_path: Optional[str] = None,
        status: str = "pending",
        generated_at: Optional[float] = None,
        error_message: Optional[str] = None,
    ):
        self.export_format = export_format
        self.file_path = file_path
        self.status = status
        self.generated_at = generated_at
        self.error_message = error_message

    def to_dict(self) -> dict:
        return {
            "export_format": self.export_format,
            "file_path": self.file_path,
            "status": self.status,
            "generated_at": self.generated_at,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NotationExport":
        return cls(**data)
