from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AudioExtractionRequest(BaseModel):
    """Request schema for audio extraction"""

    sample_rate: int = Field(
        default=44100, ge=8000, le=192000, description="Audio sample rate in Hz"
    )
    channels: int = Field(default=1, ge=1, le=2, description="Number of audio channels")
    format: str = Field(default="wav", description="Output audio format")


class AudioExtractionResponse(BaseModel):
    """Response schema for audio extraction"""

    message: str
    job_id: str
    video_id: str
    status: str
    estimated_duration: str
    settings: Dict[str, Union[int, str]]


class AudioInfoResponse(BaseModel):
    """Response schema for audio information"""

    video_id: str
    audio_file_id: str
    basic_info: Dict[str, Union[str, int, float]]
    detailed_info: Dict[str, Union[str, int, float]]
    storage_path: str


class AudioFeaturesResponse(BaseModel):
    """Response schema for audio features"""

    video_id: str
    audio_file_id: str
    features: Dict[str, Union[float, List[float]]]
    analysis_timestamp: str
    recommended_for_drums: Dict[str, Union[bool, str, List[str], float]]


class DrumEventSchema(BaseModel):
    """Schema for a detected drum event"""

    timestamp: float = Field(description="Time of the event in seconds")
    drum_type: str = Field(description="Type of drum detected")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")
    velocity: float = Field(ge=0.0, le=1.0, description="Hit velocity")
    frequency: Optional[float] = Field(
        default=None, description="Fundamental frequency"
    )
    duration: Optional[float] = Field(default=None, description="Event duration")


class TempoAnalysisSchema(BaseModel):
    """Schema for tempo and meter analysis"""

    tempo: float = Field(description="Detected tempo in BPM")
    beat_times: List[float] = Field(description="Beat timestamps in seconds")
    meter: str = Field(description="Time signature")
    beats_per_measure: int = Field(description="Number of beats per measure")


class PatternAnalysisSchema(BaseModel):
    """Schema for rhythmic pattern analysis"""

    patterns: List[Dict[str, Union[str, int]]] = Field(description="Detected patterns")
    complexity: float = Field(ge=0.0, le=1.0, description="Rhythmic complexity score")
    quantized_events: List[DrumEventSchema] = Field(description="Quantized drum events")


class DrumStatisticsSchema(BaseModel):
    """Schema for drum detection statistics"""

    total_events: int = Field(description="Total number of detected events")
    drum_counts: Dict[str, int] = Field(description="Count of each drum type")
    average_velocity: float = Field(description="Average velocity of all events")
    duration: float = Field(description="Total duration analyzed")
    events_per_second: float = Field(description="Event rate")
    most_active_drum: Optional[str] = Field(description="Most frequently detected drum")
    velocity_range: Dict[str, float] = Field(description="Velocity statistics")


class AdvancedDrumDetectionResponse(BaseModel):
    """Response schema for advanced drum detection"""

    video_id: str
    audio_file_id: str
    detection_results: Dict[str, Union[int, List[DrumEventSchema], float, bool]]
    tempo_analysis: TempoAnalysisSchema
    pattern_analysis: PatternAnalysisSchema
    statistics: DrumStatisticsSchema
    processing_info: Dict[str, str]


class SourceSeparationRequest(BaseModel):
    """Request schema for source separation"""

    method: str = Field(default="spectral", description="Separation method")
    save_sources: bool = Field(default=True, description="Save separated sources")


class QualityMetricsSchema(BaseModel):
    """Schema for separation quality metrics"""

    sdr: Optional[float] = Field(description="Signal-to-Distortion Ratio")
    reconstruction_error: Optional[float] = Field(description="Reconstruction error")
    source_diversity: float = Field(description="Diversity between sources")


class SourceSeparationResponse(BaseModel):
    """Response schema for source separation"""

    video_id: str
    audio_file_id: str
    separation_results: Dict[str, Union[str, List[str], Dict[str, str], bool]]
    quality_metrics: QualityMetricsSchema
    processing_info: Dict[str, str]


class StemExportRequest(BaseModel):
    """Request schema for stem export"""

    export_format: str = Field(default="wav", description="Export format")
    bit_depth: int = Field(default=24, description="Bit depth")
    normalize: bool = Field(default=True, description="Normalize levels")


class StemExportResponse(BaseModel):
    """Response schema for stem export"""

    video_id: str
    audio_file_id: str
    stem_export: Dict[str, Union[List[str], Dict[str, str], str, int, bool]]
    daw_import_info: Dict[str, str]
    processing_info: Dict[str, str]


class DrumEnhancementRequest(BaseModel):
    """Request schema for drum enhancement"""

    drum_type: str = Field(default="all", description="Type of drums to enhance")
    enhancement_strength: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Enhancement strength"
    )


class DrumEnhancementResponse(BaseModel):
    """Response schema for drum enhancement"""

    video_id: str
    audio_file_id: str
    enhancement_results: Dict[str, Union[str, float, int]]
    processing_info: Dict[str, str]


class ComprehensiveAnalysisRequest(BaseModel):
    """Request schema for comprehensive analysis"""

    include_detection: bool = Field(default=True, description="Include drum detection")
    include_separation: bool = Field(
        default=False, description="Include source separation"
    )
    include_patterns: bool = Field(default=True, description="Include pattern analysis")


class ComprehensiveAnalysisResponse(BaseModel):
    """Response schema for comprehensive analysis"""

    video_id: str
    audio_file_id: str
    basic_info: Dict[str, Union[str, int, float]]
    audio_features: Dict[str, Union[float, List[float]]]
    tempo_analysis: TempoAnalysisSchema
    drum_detection: Optional[
        Dict[str, Union[int, DrumStatisticsSchema, List[DrumEventSchema]]]
    ]
    pattern_analysis: Optional[PatternAnalysisSchema]
    source_separation: Optional[Dict[str, Union[List[str], QualityMetricsSchema, str]]]
    drum_suitability: Dict[str, Union[bool, float, List[str], str]]
    processing_info: Dict[str, Union[Dict[str, bool], str]]


class AudioJobStatusResponse(BaseModel):
    """Response schema for audio job status"""

    video_id: str
    extraction_status: Dict[str, Union[str, float, Optional[str]]]
    audio_available: bool
    next_steps: List[str]


class PipelineStatusResponse(BaseModel):
    """Response schema for processing pipeline status"""

    video_id: str
    pipeline_stages: Dict[str, Dict[str, Union[str, float, bool]]]
    overall_progress: float
    current_stage: str
    estimated_completion: Optional[str]


class AudioJobListResponse(BaseModel):
    """Response schema for user's audio jobs list"""

    jobs: List[Dict[str, Union[str, float, Optional[str]]]]
    total: int
    filters: Dict[str, Union[str, int, None]]


class JobActionResponse(BaseModel):
    """Response schema for job actions (cancel/retry)"""

    message: str
    job_id: str
    status: Optional[str] = None


class RecommendedSettingsResponse(BaseModel):
    """Response schema for recommended settings"""

    sample_rate: int
    channels: int
    format: str
    bit_depth: int
    normalization: bool


class SupportedFormatsResponse(BaseModel):
    """Response schema for supported audio formats"""

    formats: List[Dict[str, Union[str, bool]]]


class CleanupResponse(BaseModel):
    """Response schema for cleanup operations"""

    message: str
    cleaned_count: int


class AudioProcessingStatistics(BaseModel):
    """Response schema for audio processing statistics"""

    job_statistics: Dict[str, Union[Dict[str, int], bool, int, float]]
    audio_service_info: Dict[str, Union[str, int, Dict[str, Union[str, int, bool]]]]


class AudioProcessingError(BaseModel):
    """Schema for audio processing errors"""

    error_type: str = Field(description="Type of error")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Union[str, int, float]]] = Field(
        description="Error details"
    )
    timestamp: str = Field(description="When the error occurred")
    video_id: Optional[str] = Field(description="Related video ID if applicable")
    audio_file_id: Optional[str] = Field(
        description="Related audio file ID if applicable"
    )


class ProcessingProgress(BaseModel):
    """Schema for processing progress updates"""

    job_id: str = Field(description="Job identifier")
    stage: str = Field(description="Current processing stage")
    progress: float = Field(ge=0.0, le=100.0, description="Progress percentage")
    message: str = Field(description="Progress message")
    estimated_remaining: Optional[int] = Field(
        description="Estimated seconds remaining"
    )


class AudioValidationResult(BaseModel):
    """Schema for audio file validation results"""

    is_valid: bool = Field(description="Whether the audio file is valid")
    file_size_bytes: int = Field(description="File size in bytes")
    duration_seconds: float = Field(description="Audio duration")
    sample_rate: int = Field(description="Sample rate")
    channels: int = Field(description="Number of channels")
    format: str = Field(description="Audio format")
    issues: List[str] = Field(description="Any validation issues found")
    recommendations: List[str] = Field(description="Recommendations for improvement")


class AudioConversionRequest(BaseModel):
    """Request schema for audio format conversion"""

    target_format: str = Field(description="Target audio format")
    target_sample_rate: Optional[int] = Field(
        default=None, description="Target sample rate"
    )
    target_channels: Optional[int] = Field(
        default=None, description="Target number of channels"
    )
    normalize: bool = Field(default=False, description="Normalize audio levels")


class AudioConversionResponse(BaseModel):
    """Response schema for audio format conversion"""

    success: bool = Field(description="Whether conversion was successful")
    input_file: str = Field(description="Input file path")
    output_file: str = Field(description="Output file path")
    conversion_details: Dict[str, Union[str, int, float]] = Field(
        description="Conversion details"
    )
    processing_time_seconds: float = Field(description="Time taken for conversion")


class AdvancedAnalysisConfig(BaseModel):
    """Configuration schema for advanced audio analysis"""

    onset_threshold: float = Field(
        default=0.3, ge=0.1, le=1.0, description="Onset detection threshold"
    )
    classification_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Classification confidence threshold"
    )
    min_event_distance_ms: int = Field(
        default=50, ge=10, le=500, description="Minimum distance between events in ms"
    )
    frequency_analysis: bool = Field(
        default=True, description="Enable frequency analysis"
    )
    pattern_detection: bool = Field(
        default=True, description="Enable pattern detection"
    )
    velocity_analysis: bool = Field(
        default=True, description="Enable velocity analysis"
    )


class DrumKitMapping(BaseModel):
    """Schema for drum kit sound mapping"""

    kick: List[str] = Field(description="Kick drum sound identifiers")
    snare: List[str] = Field(description="Snare drum sound identifiers")
    hihat: List[str] = Field(description="Hi-hat sound identifiers")
    crash: List[str] = Field(description="Crash cymbal sound identifiers")
    ride: List[str] = Field(description="Ride cymbal sound identifiers")
    tom_low: List[str] = Field(description="Low tom sound identifiers")
    tom_mid: List[str] = Field(description="Mid tom sound identifiers")
    tom_high: List[str] = Field(description="High tom sound identifiers")
    other: List[str] = Field(description="Other percussion sound identifiers")


class ExportSettings(BaseModel):
    """Schema for audio export settings"""

    format: str = Field(description="Export audio format")
    sample_rate: int = Field(description="Export sample rate")
    bit_depth: int = Field(description="Export bit depth")
    channels: int = Field(description="Number of channels")
    normalize: bool = Field(description="Normalize audio levels")
    fade_in_ms: int = Field(default=0, description="Fade in duration in milliseconds")
    fade_out_ms: int = Field(default=0, description="Fade out duration in milliseconds")
    trim_silence: bool = Field(
        default=False, description="Trim leading/trailing silence"
    )
