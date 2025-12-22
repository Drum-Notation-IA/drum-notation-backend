"""
Notation Module

This module handles drum notation generation, processing, and management.
It provides comprehensive musical notation capabilities including:

- Generation of musical notation from drum detection results
- Stroke-by-stroke timeline data for real-time playback synchronization
- Musical staff rendering data with measures, beats, and notes
- AI-powered analysis and enrichment using OpenAI
- Multi-format export (MusicXML, MIDI, SVG, PDF, JSON)
- Drum kit mappings and staff positioning
- Comprehensive validation and error handling

The module is designed to support frontend musical staff rendering with
precise timing data for stroke-by-stroke highlighting during audio playback.
"""

from .models import (
    DrumKitMapping,
    DrumNotation,
    DrumNote,
    NotationBeat,
    NotationExport,
    NotationMeasure,
    NotationTemplate,
    OpenAIEnrichment,
    StrokeEvent,
)
from .repository import (
    DrumKitMappingRepository,
    DrumNotationRepository,
    DrumNoteRepository,
    NotationBeatRepository,
    NotationExportRepository,
    NotationMeasureRepository,
    NotationTemplateRepository,
    OpenAIEnrichmentRepository,
    StrokeEventRepository,
)
from .router import router as notation_router
from .schemas import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    BatchNotationRequest,
    BatchNotationResponse,
    DetailedNotationResponse,
    DrumKitMappingResponse,
    DrumNotationResponse,
    DrumNoteResponse,
    ExportNotationRequest,
    GenerateNotationRequest,
    NotationBeatResponse,
    NotationError,
    NotationExportResponse,
    NotationHealthResponse,
    NotationListResponse,
    NotationMeasureResponse,
    NotationSearchRequest,
    NotationStatsResponse,
    NotationTimelineResponse,
    NotationValidationResponse,
    StrokeEventResponse,
    UpdateNotationRequest,
)
from .service import NotationService

__all__ = [
    # Models
    "DrumNotation",
    "NotationMeasure",
    "NotationBeat",
    "DrumNote",
    "StrokeEvent",
    "DrumKitMapping",
    "NotationExport",
    "NotationTemplate",
    "OpenAIEnrichment",
    # Repositories
    "DrumNotationRepository",
    "NotationMeasureRepository",
    "NotationBeatRepository",
    "DrumNoteRepository",
    "StrokeEventRepository",
    "DrumKitMappingRepository",
    "NotationExportRepository",
    "NotationTemplateRepository",
    "OpenAIEnrichmentRepository",
    # Service
    "NotationService",
    # Router
    "notation_router",
    # Schemas - Requests
    "GenerateNotationRequest",
    "UpdateNotationRequest",
    "ExportNotationRequest",
    "AIAnalysisRequest",
    "NotationSearchRequest",
    "BatchNotationRequest",
    # Schemas - Responses
    "DrumNotationResponse",
    "DetailedNotationResponse",
    "NotationTimelineResponse",
    "NotationMeasureResponse",
    "NotationBeatResponse",
    "DrumNoteResponse",
    "StrokeEventResponse",
    "NotationExportResponse",
    "AIAnalysisResponse",
    "NotationListResponse",
    "NotationStatsResponse",
    "NotationHealthResponse",
    "DrumKitMappingResponse",
    "NotationValidationResponse",
    "BatchNotationResponse",
    "NotationError",
]

# Module metadata
__version__ = "1.0.0"
__author__ = "Drum Notation Backend Team"
__description__ = "Complete drum notation generation and management system"
