"""
Pydantic models for the external ML service ``/analyze`` response.

The ML service was enriched to return a much denser, "stroke-by-stroke"
transcription. Crucially the change was **additive**: existing fields keep
their names and meaning, and new fields were added on top. These models mirror
that contract:

* every *new* field is ``Optional`` with a sane default, so old ML responses
  (and the local fallback) still validate;
* unknown / future fields are ignored (``extra="ignore"``) instead of raising,
  keeping the backend forward-compatible;
* the models are intentionally lenient so a single malformed event never sinks
  the whole response — callers can still fall back to raw-dict parsing.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MLEvent(BaseModel):
    """A single classified drum stroke from the ML service."""

    model_config = ConfigDict(extra="ignore")

    # --- pre-existing fields (unchanged) ---------------------------------
    index: Optional[int] = None
    time: Optional[float] = None
    instrument: Optional[str] = None
    confidence: Optional[float] = None
    model_confidence: Optional[float] = None
    max_probability: Optional[float] = None
    strength: Optional[float] = None
    peak_rel: Optional[float] = None
    heuristic: Optional[bool] = False

    # --- NEW additive fields ---------------------------------------------
    dominant_band: Optional[str] = Field(
        default=None, description='"low" | "mid" | "high"'
    )
    grid_type: Optional[str] = Field(
        default=None, description='"straight" | "triplet"'
    )
    velocity: Optional[int] = Field(
        default=None, description="MIDI velocity 1..127 (dynamics / accents / ghosts)"
    )
    quantized_time: Optional[float] = None
    quant_error_ms: Optional[float] = None
    grid_index: Optional[int] = None
    measure: Optional[int] = None
    beat: Optional[int] = None
    subdivision_index: Optional[int] = None


class MLQuantization(BaseModel):
    """The ``quantization`` block of the ML response."""

    model_config = ConfigDict(extra="ignore")

    enabled: Optional[bool] = None
    profile: Optional[str] = None
    subdivision: Optional[int] = None
    time_signature: Optional[str] = None
    num_events: Optional[int] = None

    # --- NEW additive fields ---------------------------------------------
    tempo_bpm: Optional[float] = None
    grid_step_seconds: Optional[float] = None
    triplet_step_seconds: Optional[float] = None


class MLAnalyzeResponse(BaseModel):
    """Top-level ``/analyze`` response envelope."""

    model_config = ConfigDict(extra="ignore")

    success: Optional[bool] = None
    filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    processing_time_seconds: Optional[float] = None

    predicted_class: Optional[str] = None
    dominant_drum: Optional[str] = None
    confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    avg_event_confidence: Optional[float] = None
    tempo_estimate: Optional[float] = None

    onset_count: Optional[int] = None
    raw_onset_count: Optional[int] = None
    event_count: Optional[int] = None

    quantization: Optional[MLQuantization] = None
    onset_times: List[float] = Field(default_factory=list)
    events: List[MLEvent] = Field(default_factory=list)
