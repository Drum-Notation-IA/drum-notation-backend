"""
Notation Schemas
Pydantic schemas for drum notation API requests and responses
Updated to align with simplified JSON-based database schema
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# Base schemas for nested data structures
class StrokeEventSchema(BaseModel):
    """Schema for individual stroke events in the timeline"""

    timestamp_seconds: float = Field(
        ..., ge=0, description="Absolute timestamp in audio"
    )
    drum_type: str = Field(..., description="Type of drum/instrument")
    velocity: float = Field(..., ge=0, le=1, description="Hit velocity (0.0-1.0)")
    measure_number: int = Field(..., ge=1, description="Measure number (1-based)")
    beat_number: float = Field(..., ge=1, description="Beat number within measure")
    staff_position: str = Field(
        ..., description="Musical staff position (e.g., 'F4', 'D5')"
    )
    note_head_type: str = Field(default="normal", description="Note head type")
    accent: Optional[str] = Field(None, description="Accent type if any")
    ghost_note: bool = Field(default=False, description="Is this a ghost note")
    confidence_score: Optional[float] = Field(
        None, ge=0, le=1, description="Detection confidence"
    )


class DrumNoteSchema(BaseModel):
    """Schema for individual drum notes within beats"""

    drum_type: str = Field(..., description="Type of drum/instrument")
    staff_position: str = Field(..., description="Musical staff position")
    note_duration: str = Field(default="quarter", description="Note duration")
    note_head_type: str = Field(default="normal", description="Note head type")
    velocity: float = Field(..., ge=0, le=1, description="Hit velocity")
    accent: Optional[str] = Field(None, description="Accent type")
    ghost_note: bool = Field(default=False, description="Is this a ghost note")
    confidence_score: Optional[float] = Field(
        None, ge=0, le=1, description="Detection confidence"
    )
    timestamp_seconds: float = Field(..., ge=0, description="Absolute timestamp")


class NotationBeatSchema(BaseModel):
    """Schema for beats within measures"""

    beat_number: int = Field(..., ge=1, description="Beat number within measure")
    start_time_seconds: float = Field(..., ge=0, description="Beat start time")
    end_time_seconds: float = Field(..., ge=0, description="Beat end time")
    notes: List[DrumNoteSchema] = Field(
        default_factory=list, description="Notes in this beat"
    )
    note_count: int = Field(default=0, ge=0, description="Number of notes in beat")


class NotationMeasureSchema(BaseModel):
    """Schema for measures within notation"""

    measure_number: int = Field(..., ge=1, description="Measure number (1-based)")
    start_time_seconds: float = Field(..., ge=0, description="Measure start time")
    end_time_seconds: float = Field(..., ge=0, description="Measure end time")
    time_signature: str = Field(..., description="Time signature for this measure")
    tempo_bpm: float = Field(..., gt=0, description="Tempo for this measure")
    beats: List[NotationBeatSchema] = Field(
        default_factory=list, description="Beats in measure"
    )
    complexity_score: float = Field(
        default=0.0, ge=0, le=1, description="Measure complexity"
    )


class MusicalStructureSchema(BaseModel):
    """Schema for musical structure metadata"""

    tempo_bpm: float = Field(..., gt=0, description="Overall tempo")
    time_signature: str = Field(..., description="Time signature")
    beats_per_measure: int = Field(..., gt=0, description="Beats per measure")
    total_measures: int = Field(..., ge=0, description="Total number of measures")
    duration_seconds: float = Field(..., ge=0, description="Total duration")
    quantization: Dict[str, Any] = Field(
        default_factory=dict, description="Quantization settings"
    )
    complexity: Dict[str, Any] = Field(
        default_factory=dict, description="Complexity metrics"
    )
    instruments_detected: List[str] = Field(
        default_factory=list, description="Detected instruments"
    )


class NotationExportSchema(BaseModel):
    """Schema for notation export metadata"""

    export_format: str = Field(
        ..., description="Export format (musicxml, midi, json, svg)"
    )
    status: str = Field(..., description="Export status")
    file_path: Optional[str] = Field(None, description="Path to exported file")
    created_at: str = Field(..., description="Creation timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    failed_at: Optional[str] = Field(None, description="Failure timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="File size in bytes")


# Request schemas
class GenerateNotationRequest(BaseModel):
    """Request to generate notation from drum detection results"""

    video_id: UUID = Field(..., description="Video ID for the notation")
    drum_events: List[Dict[str, Any]] = Field(..., description="Drum detection results")
    tempo_bpm: Optional[float] = Field(
        None, gt=0, le=300, description="Manual tempo override"
    )
    time_signature: str = Field(default="4/4", description="Time signature")
    quantization_level: str = Field(
        default="sixteenth", description="Quantization level"
    )
    apply_ai_analysis: bool = Field(default=True, description="Apply AI analysis")

    @validator("time_signature")
    def validate_time_signature(cls, v):
        if not v or "/" not in v:
            raise ValueError("Time signature must be in format 'X/Y'")
        try:
            num, den = v.split("/")
            int(num)
            int(den)
        except ValueError:
            raise ValueError("Invalid time signature format")
        return v

    @validator("quantization_level")
    def validate_quantization_level(cls, v):
        valid_levels = [
            "whole",
            "half",
            "quarter",
            "eighth",
            "sixteenth",
            "thirty_second",
        ]
        if v not in valid_levels:
            raise ValueError(f"Quantization level must be one of: {valid_levels}")
        return v


class UpdateNotationRequest(BaseModel):
    """Request to update notation properties"""

    tempo: Optional[int] = Field(None, gt=0, le=300, description="Tempo in BPM")
    time_signature: Optional[str] = Field(None, description="Time signature")
    notation_json: Optional[Dict[str, Any]] = Field(
        None, description="Updated notation data"
    )

    @validator("time_signature")
    def validate_time_signature(cls, v):
        if v and "/" not in v:
            raise ValueError("Time signature must be in format 'X/Y'")
        return v


class ExportNotationRequest(BaseModel):
    """Request to export notation to specific format"""

    export_format: str = Field(..., description="Export format")
    include_metadata: bool = Field(
        default=True, description="Include metadata in export"
    )
    quality_settings: Optional[Dict[str, Any]] = Field(
        None, description="Quality settings"
    )

    @validator("export_format")
    def validate_format(cls, v):
        valid_formats = ["musicxml", "midi", "json", "svg", "pdf"]
        if v not in valid_formats:
            raise ValueError(f"Export format must be one of: {valid_formats}")
        return v


class AIAnalysisRequest(BaseModel):
    """Request for AI analysis of notation"""

    analysis_types: List[str] = Field(
        default=["pattern_analysis", "style_classification"],
        description="Types of AI analysis to perform",
    )
    include_practice_tips: bool = Field(
        default=True, description="Include practice recommendations"
    )
    skill_level: str = Field(default="intermediate", description="Target skill level")
    focus_areas: List[str] = Field(
        default_factory=lambda: ["timing", "dynamics"],
        description="Areas to focus analysis on",
    )

    @validator("analysis_types")
    def validate_analysis_types(cls, v):
        valid_types = [
            "pattern_analysis",
            "style_classification",
            "difficulty_assessment",
            "tempo_analysis",
            "practice_recommendations",
            "technique_suggestions",
        ]
        invalid = [t for t in v if t not in valid_types]
        if invalid:
            raise ValueError(f"Invalid analysis types: {invalid}")
        return v

    @validator("skill_level")
    def validate_skill_level(cls, v):
        valid_levels = ["beginner", "intermediate", "advanced", "professional"]
        if v not in valid_levels:
            raise ValueError(f"Skill level must be one of: {valid_levels}")
        return v


# Response schemas
class DrumNotationResponse(BaseModel):
    """Basic notation response"""

    id: UUID = Field(..., description="Notation ID")
    video_id: UUID = Field(..., description="Associated video ID")
    tempo: Optional[int] = Field(None, description="Tempo in BPM")
    time_signature: Optional[str] = Field(None, description="Time signature")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class DetailedNotationResponse(DrumNotationResponse):
    """Detailed notation response with full JSON data"""

    notation_json: Dict[str, Any] = Field(..., description="Complete notation data")
    musical_structure: Optional[MusicalStructureSchema] = Field(
        None, description="Musical structure"
    )
    timeline: List[StrokeEventSchema] = Field(
        default_factory=list, description="Stroke timeline"
    )
    measures: List[NotationMeasureSchema] = Field(
        default_factory=list, description="Measures"
    )
    exports: List[NotationExportSchema] = Field(
        default_factory=list, description="Export history"
    )


class NotationTimelineResponse(BaseModel):
    """Response for notation timeline data"""

    notation_id: UUID = Field(..., description="Notation ID")
    timeline: List[StrokeEventSchema] = Field(..., description="Stroke events timeline")
    total_events: int = Field(..., ge=0, description="Total number of events")
    duration_seconds: float = Field(..., ge=0, description="Total duration")
    tempo: Optional[int] = Field(None, description="Tempo in BPM")
    time_signature: Optional[str] = Field(None, description="Time signature")


class NotationMeasuresResponse(BaseModel):
    """Response for notation measures data"""

    notation_id: UUID = Field(..., description="Notation ID")
    measures: List[NotationMeasureSchema] = Field(..., description="Measures")
    total_measures: int = Field(..., ge=0, description="Total number of measures")


class OpenAIEnrichmentResponse(BaseModel):
    """Response for OpenAI enrichment data"""

    id: UUID = Field(..., description="Enrichment ID")
    notation_id: UUID = Field(..., description="Associated notation ID")
    model: str = Field(..., description="AI model used")
    input_json: Dict[str, Any] = Field(..., description="Input data sent to AI")
    output_json: Dict[str, Any] = Field(..., description="AI response data")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class NotationExportResponse(BaseModel):
    """Response for notation export operations"""

    export_format: str = Field(..., description="Export format")
    status: str = Field(..., description="Export status")
    file_path: Optional[str] = Field(None, description="Path to exported file")
    file_size_bytes: Optional[int] = Field(None, description="File size")
    created_at: str = Field(..., description="Export creation time")
    completed_at: Optional[str] = Field(None, description="Export completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")


# List and search schemas
class NotationListResponse(BaseModel):
    """Response for notation lists"""

    notations: List[DrumNotationResponse] = Field(..., description="List of notations")
    total: int = Field(..., ge=0, description="Total number of notations")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")


class NotationSearchRequest(BaseModel):
    """Request for searching notations"""

    video_id: Optional[UUID] = Field(None, description="Filter by video ID")
    tempo_min: Optional[int] = Field(None, gt=0, description="Minimum tempo filter")
    tempo_max: Optional[int] = Field(None, gt=0, description="Maximum tempo filter")
    time_signature: Optional[str] = Field(None, description="Filter by time signature")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=50, ge=1, le=100, description="Items per page")
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order")

    @validator("sort_by")
    def validate_sort_by(cls, v):
        valid_fields = ["created_at", "updated_at", "tempo", "time_signature"]
        if v not in valid_fields:
            raise ValueError(f"Sort field must be one of: {valid_fields}")
        return v

    @validator("sort_order")
    def validate_sort_order(cls, v):
        if v not in ["asc", "desc"]:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v


# Statistics and health schemas
class NotationStatsResponse(BaseModel):
    """Response for notation statistics"""

    total_notations: int = Field(..., ge=0, description="Total number of notations")
    total_measures: int = Field(
        ..., ge=0, description="Total measures across all notations"
    )
    total_events: int = Field(..., ge=0, description="Total stroke events")
    avg_tempo: Optional[float] = Field(None, description="Average tempo")
    tempo_range: Dict[str, Optional[float]] = Field(
        ..., description="Tempo range (min, max)"
    )
    time_signature_distribution: Dict[str, int] = Field(
        ..., description="Time signature usage"
    )
    complexity_stats: Dict[str, float] = Field(..., description="Complexity statistics")


class NotationHealthResponse(BaseModel):
    """Response for notation service health check"""

    status: str = Field(..., description="Service status")
    database_connected: bool = Field(..., description="Database connection status")
    openai_available: bool = Field(..., description="OpenAI service availability")
    recent_notation_count: int = Field(
        ..., ge=0, description="Recent notations created"
    )
    avg_processing_time: Optional[float] = Field(
        None, description="Average processing time"
    )
    error_rate: float = Field(..., ge=0, le=1, description="Recent error rate")


# Error schemas
class NotationError(BaseModel):
    """Error response for notation operations"""

    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    notation_id: Optional[UUID] = Field(
        None, description="Related notation ID if applicable"
    )


class ValidationError(BaseModel):
    """Validation error response"""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Any = Field(..., description="Invalid value")


class NotationValidationResponse(BaseModel):
    """Response for notation validation"""

    is_valid: bool = Field(..., description="Whether notation is valid")
    errors: List[ValidationError] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")


# Batch operation schemas
class BatchNotationRequest(BaseModel):
    """Request for batch notation operations"""

    video_ids: List[UUID] = Field(
        ..., min_length=1, max_length=10, description="Video IDs to process"
    )
    tempo_bpm: Optional[float] = Field(None, gt=0, description="Default tempo for all")
    time_signature: str = Field(default="4/4", description="Default time signature")
    quantization_level: str = Field(
        default="sixteenth", description="Quantization level"
    )
    apply_ai_analysis: bool = Field(
        default=True, description="Apply AI analysis to all"
    )

    @validator("video_ids")
    def validate_video_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("Duplicate video IDs not allowed")
        return v


class BatchNotationResponse(BaseModel):
    """Response for batch notation operations"""

    total_requested: int = Field(..., ge=0, description="Total notations requested")
    successful: List[UUID] = Field(..., description="Successfully created notation IDs")
    failed: List[Dict[str, Any]] = Field(
        ..., description="Failed operations with errors"
    )
    processing_time_seconds: float = Field(
        ..., ge=0, description="Total processing time"
    )


# Export format specific schemas
class MusicXMLExportOptions(BaseModel):
    """Options for MusicXML export"""

    include_dynamics: bool = Field(default=True, description="Include dynamic markings")
    include_articulations: bool = Field(
        default=True, description="Include articulation marks"
    )
    software_name: str = Field(
        default="Drum Notation Backend", description="Software identifier"
    )


class MIDIExportOptions(BaseModel):
    """Options for MIDI export"""

    track_name: str = Field(default="Drums", description="MIDI track name")
    channel: int = Field(
        default=9, ge=0, le=15, description="MIDI channel (9 for drums)"
    )
    velocity_scaling: float = Field(
        default=1.0, ge=0.1, le=2.0, description="Velocity scaling factor"
    )


class SVGExportOptions(BaseModel):
    """Options for SVG export"""

    width: int = Field(default=800, gt=0, description="SVG width in pixels")
    height: int = Field(default=600, gt=0, description="SVG height in pixels")
    staff_size: int = Field(default=20, gt=0, description="Staff size")
    show_measure_numbers: bool = Field(default=True, description="Show measure numbers")


# Missing schemas required by router
class AIAnalysisResponse(BaseModel):
    """Response schema for AI analysis"""

    pattern_analysis: Dict[str, Any] = Field(
        ..., description="Pattern analysis results"
    )
    style_classification: Dict[str, Any] = Field(
        ..., description="Style classification"
    )
    practice_instructions: Dict[str, Any] = Field(
        ..., description="Practice recommendations"
    )
    technical_analysis: str = Field(..., description="Technical analysis text")
    complexity: str = Field(..., description="Complexity level")
    confidence: float = Field(..., description="Analysis confidence")


class DrumKitMappingResponse(BaseModel):
    """Response schema for drum kit mapping"""

    kit_id: UUID = Field(..., description="Kit mapping ID")
    kit_name: str = Field(..., description="Drum kit name")
    mappings: Dict[str, str] = Field(..., description="Instrument mappings")
    created_at: datetime = Field(..., description="Creation timestamp")
