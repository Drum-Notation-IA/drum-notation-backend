"""
Notation Schemas
Pydantic models for notation API requests and responses
"""

from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator


class DrumEventBase(BaseModel):
    """Base schema for drum events"""

    time_seconds: float = Field(..., description="Time position in seconds", ge=0)
    instrument: str = Field(..., description="Drum instrument name")
    velocity: Optional[float] = Field(
        None, description="Event velocity 0.0-1.0", ge=0, le=1
    )
    confidence: Optional[float] = Field(
        None, description="Detection confidence 0.0-1.0", ge=0, le=1
    )


class DrumEventCreate(DrumEventBase):
    """Schema for creating drum events"""

    audio_file_id: UUID = Field(..., description="Associated audio file ID")
    model_version: Optional[str] = Field(None, description="Analysis model version")
    onset_time: Optional[float] = Field(None, description="Precise onset time")
    duration: Optional[float] = Field(None, description="Event duration in seconds")


class DrumEventResponse(DrumEventBase):
    """Schema for drum event responses"""

    id: UUID
    audio_file_id: UUID
    model_version: Optional[str]
    onset_time: Optional[float]
    duration: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotationBase(BaseModel):
    """Base schema for notation"""

    tempo: Optional[int] = Field(None, description="Tempo in BPM", gt=0, le=300)
    time_signature: Optional[str] = Field(
        None, description="Time signature (e.g., 4/4)"
    )
    notation_json: Dict = Field(..., description="Notation data")


class NotationCreate(NotationBase):
    """Schema for creating notation"""

    video_id: UUID = Field(..., description="Associated video ID")
    model_version: Optional[str] = Field(None, description="Analysis model version")
    confidence_score: Optional[float] = Field(
        None, description="Overall confidence", ge=0, le=1
    )

    @validator("time_signature")
    def validate_time_signature(cls, v):
        if v and "/" not in v:
            raise ValueError(
                'Time signature must be in format "beats/note_value" (e.g., "4/4")'
            )
        return v


class NotationUpdate(BaseModel):
    """Schema for updating notation"""

    tempo: Optional[int] = Field(None, description="Tempo in BPM", gt=0, le=300)
    time_signature: Optional[str] = Field(None, description="Time signature")
    notation_json: Optional[Dict] = Field(None, description="Notation data")

    @validator("time_signature")
    def validate_time_signature(cls, v):
        if v and "/" not in v:
            raise ValueError(
                'Time signature must be in format "beats/note_value" (e.g., "4/4")'
            )
        return v


class NotationResponse(NotationBase):
    """Schema for notation responses"""

    id: UUID
    video_id: UUID
    model_version: Optional[str]
    confidence_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OpenAIEnrichmentResponse(BaseModel):
    """Schema for OpenAI enrichment responses"""

    id: UUID
    notation_id: UUID
    model: str
    enhancement: Dict
    created_at: datetime

    class Config:
        from_attributes = True


class NotationWithEnhancements(BaseModel):
    """Schema for notation with AI enhancements"""

    notation: NotationResponse
    ai_enhancements: List[OpenAIEnrichmentResponse]


class NotationFromEventsRequest(BaseModel):
    """Schema for creating notation from drum events"""

    video_id: UUID = Field(..., description="Associated video ID")
    tempo: Optional[int] = Field(None, description="Tempo in BPM", gt=0, le=300)
    time_signature: str = Field(default="4/4", description="Time signature")

    @validator("time_signature")
    def validate_time_signature(cls, v):
        if "/" not in v:
            raise ValueError(
                'Time signature must be in format "beats/note_value" (e.g., "4/4")'
            )
        return v


class NotationEnhancementRequest(BaseModel):
    """Schema for requesting AI enhancements"""

    enhancement_type: str = Field(
        default="full_analysis", description="Type of enhancement to perform"
    )

    @validator("enhancement_type")
    def validate_enhancement_type(cls, v):
        valid_types = [
            "full_analysis",
            "pattern_analysis",
            "style_classification",
            "practice_instructions",
        ]
        if v not in valid_types:
            raise ValueError(
                f"Enhancement type must be one of: {', '.join(valid_types)}"
            )
        return v


class NotationExportRequest(BaseModel):
    """Schema for notation export requests"""

    format_type: str = Field(default="musicxml", description="Export format")

    @validator("format_type")
    def validate_format_type(cls, v):
        valid_formats = ["musicxml", "midi", "json"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Format must be one of: {', '.join(valid_formats)}")
        return v.lower()


class PracticeVariationsRequest(BaseModel):
    """Schema for practice variation requests"""

    difficulty_level: str = Field(
        default="intermediate", description="Difficulty level"
    )

    @validator("difficulty_level")
    def validate_difficulty_level(cls, v):
        valid_levels = ["beginner", "intermediate", "advanced", "expert"]
        if v.lower() not in valid_levels:
            raise ValueError(
                f"Difficulty level must be one of: {', '.join(valid_levels)}"
            )
        return v.lower()


class NotationAnalysisResponse(BaseModel):
    """Schema for notation analysis results"""

    pattern_analysis: Optional[Dict] = None
    style_classification: Optional[Dict] = None
    practice_instructions: Optional[Dict] = None
    variations: Optional[List[Dict]] = None
    metadata: Dict = Field(default_factory=dict)


class NotationSearchRequest(BaseModel):
    """Schema for notation search requests"""

    video_id: Optional[UUID] = Field(None, description="Filter by video ID")
    tempo_min: Optional[int] = Field(None, description="Minimum tempo", gt=0)
    tempo_max: Optional[int] = Field(None, description="Maximum tempo", gt=0)
    time_signature: Optional[str] = Field(None, description="Filter by time signature")
    limit: int = Field(default=50, description="Maximum results", gt=0, le=100)
    offset: int = Field(default=0, description="Results offset", ge=0)


class NotationListResponse(BaseModel):
    """Schema for notation list responses"""

    notations: List[NotationResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class NotationStatsResponse(BaseModel):
    """Schema for notation statistics"""

    total_notations: int
    total_events: int
    avg_tempo: Optional[float]
    common_time_signatures: List[Dict[str, Union[str, int]]]
    instruments_detected: List[str]
    confidence_distribution: Dict[str, int]


class MeasureData(BaseModel):
    """Schema for individual measure data"""

    measure_number: int
    beats: List[Dict]
    total_events: int


class NotationMetadata(BaseModel):
    """Schema for notation metadata"""

    tempo: int
    time_signature: str
    total_measures: int
    total_events: int
    duration_seconds: float


class DetailedNotationResponse(BaseModel):
    """Schema for detailed notation with measures"""

    id: UUID
    video_id: UUID
    measures: List[MeasureData]
    metadata: NotationMetadata
    confidence_score: Optional[float]
    model_version: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotationValidationError(BaseModel):
    """Schema for notation validation errors"""

    field: str
    message: str
    value: Optional[Union[str, int, float]]


class NotationValidationResponse(BaseModel):
    """Schema for notation validation results"""

    is_valid: bool
    errors: List[NotationValidationError]
    warnings: List[str]
    suggestions: List[str]
