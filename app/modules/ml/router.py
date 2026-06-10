"""
Machine Learning Router for Drum Notation Backend
================================================

Bridges the external ML service (port 8001) with the notation pipeline.

Primary flow (`run_video_analysis`):
  1. Locate the extracted audio file in the DB (auto-extracts if missing).
  2. POST it to the ML service `/analyze` endpoint.
  3. If the ML response carries classified events (instrument + velocity +
     confidence), consume them DIRECTLY — no local re-classification.
  4. If the ML response only carries onset times (legacy shape), fall back to
     the local DrumDetector to classify each onset.
  5. If the ML service is unavailable, fall back to a 100 % local pipeline.

This preserves the upstream ML quality (confidence, model probabilities,
quantization, tempo) while keeping a robust offline fallback.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.audio_processing.detection import (
    AUDIO_LIBS_AVAILABLE,
    DrumDetector,
    DrumEvent,
)
from app.modules.media.repository import AudioFileRepository
from app.modules.ml.instruments import (
    DEFAULT_INSTRUMENT_ALIASES,
    default_instrument_mapper,
)
from app.modules.ml.ml_schemas import MLAnalyzeResponse
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["machine-learning"])

# ---------------------------------------------------------------------------
# Shared detector instance
# ---------------------------------------------------------------------------
_detector = DrumDetector()
_audio_repo = AudioFileRepository()


# ---------------------------------------------------------------------------
# ML response normalisation
# ---------------------------------------------------------------------------

# Canonical instrument normalisation now lives in app.modules.ml.instruments
# (DrumInstrument Enum + InstrumentMapper). We re-export the alias table and a
# thin function wrapper here for backward compatibility with existing callers.
ML_INSTRUMENT_ALIASES: Dict[str, str] = DEFAULT_INSTRUMENT_ALIASES


def _canonical_instrument(name: Any) -> str:
    """Map any incoming drum-class label to a canonical name (safe fallback)."""
    return default_instrument_mapper.canonical(name)


def _normalise_velocity(v: Any) -> float:
    """Normalise velocity to the 0-1 range. Accepts MIDI 0-127 or already-normalised."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.5
    if f <= 1.0:                           # already normalised
        return max(0.0, min(1.0, f))
    return max(0.0, min(1.0, f / 127.0))   # MIDI 0-127 → 0-1


def _parse_ml_events(ml_data: Dict[str, Any]) -> Tuple[
    List[Dict[str, Any]], Optional[float], Optional[str], Dict[str, Any]
]:
    """
    Parse the ML service /analyze response into the backend's drum_events format.

    Returns:
        events:         list of {time_seconds, instrument, velocity, confidence, ...}
        tempo_bpm:      float or None
        time_signature: str or None
        ml_metadata:    dict with provenance/quantization info for the frontend
    """
    from app.core.config import settings as _cfg

    # ------------------------------------------------------------------
    # 0) Validate the envelope with the Pydantic model when possible. This
    #    gives us a typed, forward-compatible view (new fields are optional).
    #    On any validation hiccup we fall back to tolerant dict access so a
    #    single odd field never sinks the whole response.
    # ------------------------------------------------------------------
    parsed: Optional[MLAnalyzeResponse] = None
    try:
        parsed = MLAnalyzeResponse.model_validate(ml_data)
    except Exception as exc:  # noqa: BLE001 — defensive, never fatal
        logger.debug("ML response did not validate against MLAnalyzeResponse: %s", exc)

    # ------------------------------------------------------------------
    # 1) Locate the events list. The ML service exposes them at the top level
    #    AND under results.events for compatibility.
    # ------------------------------------------------------------------
    raw_events = (
        ml_data.get("events")
        or ml_data.get("results", {}).get("events")
        or ml_data.get("drum_events")
        or []
    )

    # Size guard: keep ingestion bounded (the enriched ML service can emit
    # thousands of events). We cap rather than reject so big-but-valid charts
    # still work; the cap is configurable via settings.
    max_events = int(getattr(_cfg, "MAX_ML_EVENTS", 100_000))
    if len(raw_events) > max_events:
        logger.warning(
            "ML response carried %d events; truncating to MAX_ML_EVENTS=%d",
            len(raw_events), max_events,
        )
        raw_events = raw_events[:max_events]

    # ------------------------------------------------------------------
    # 2) Tempo + time signature: prefer the quantization block, fall back to
    #    top-level tempo_estimate.
    # ------------------------------------------------------------------
    quant = ml_data.get("quantization") or ml_data.get("results", {}).get("quantization") or {}
    tempo_bpm = (
        quant.get("tempo_bpm")
        or ml_data.get("tempo_estimate")
        or ml_data.get("results", {}).get("summary", {}).get("tempo_estimate")
    )
    try:
        tempo_bpm = float(tempo_bpm) if tempo_bpm is not None else None
    except (TypeError, ValueError):
        tempo_bpm = None

    time_signature = quant.get("time_signature") or "4/4"

    # ------------------------------------------------------------------
    # 3) Convert each ML event to the backend's drum_event shape.
    #    Existing keys are preserved verbatim; NEW ML fields are added
    #    additively (dominant_band, grid_type, velocity_midi, strength,
    #    peak_rel, quantized_time, subdivision_index).
    # ------------------------------------------------------------------
    drum_events: List[Dict[str, Any]] = []
    for ev in raw_events:
        if not isinstance(ev, dict):
            continue

        # Use quantized_time when available so the local re-quantization in
        # the notation service lands in the same slot as the ML's grid.
        t_quant = ev.get("quantized_time")
        t_raw   = ev.get("time", ev.get("timestamp"))
        time_seconds = float(t_quant if t_quant is not None else (t_raw or 0.0))

        instrument = _canonical_instrument(ev.get("instrument") or ev.get("drum_type"))

        # Raw MIDI velocity (1..127) drives accents / ghost notes; we keep the
        # normalised 0..1 value under the historical "velocity" key.
        velocity_midi_raw = ev.get("velocity")
        try:
            velocity_midi = int(velocity_midi_raw) if velocity_midi_raw is not None else None
        except (TypeError, ValueError):
            velocity_midi = None
        velocity = _normalise_velocity(velocity_midi_raw if velocity_midi_raw is not None else 0.7)

        try:
            confidence = float(ev.get("confidence", ev.get("model_confidence", 0.5)))
        except (TypeError, ValueError):
            confidence = 0.5

        drum_events.append({
            "time_seconds": time_seconds,
            "instrument":   instrument,
            "velocity":     round(velocity, 3),
            "confidence":   round(confidence, 3),
            # Preserve the rich ML metadata for downstream consumers
            "raw_time":          float(t_raw) if t_raw is not None else time_seconds,
            "model_confidence":  float(ev.get("model_confidence", confidence) or 0.0),
            "max_probability":   float(ev.get("max_probability", 0.0) or 0.0),
            "heuristic":         bool(ev.get("heuristic", False)),
            "ml_measure":        ev.get("measure"),
            "ml_beat":           ev.get("beat"),
            "ml_subdivision":    ev.get("subdivision_index"),
            "ml_grid_index":     ev.get("grid_index"),
            "quant_error_ms":    ev.get("quant_error_ms"),
            # --- NEW additive ML fields ---
            "dominant_band":     ev.get("dominant_band"),
            "grid_type":         ev.get("grid_type"),
            "velocity_midi":     velocity_midi,
            "strength":          ev.get("strength"),
            "peak_rel":          ev.get("peak_rel"),
            "quantized_time":    t_quant,
        })

    # Stable sort by time; secondary key keeps stacks (same time) deterministic.
    drum_events.sort(key=lambda e: (e["time_seconds"], e["instrument"]))

    # ------------------------------------------------------------------
    # 4) Build a metadata block (kept separate so it doesn't pollute events).
    #    The quantization sub-block now carries the new tempo/grid fields.
    # ------------------------------------------------------------------
    ml_metadata: Dict[str, Any] = {
        "predicted_class":       ml_data.get("predicted_class"),
        "dominant_drum":         ml_data.get("dominant_drum"),
        "overall_confidence":    ml_data.get("confidence"),
        "confidence_level":      ml_data.get("confidence_level"),
        "avg_event_confidence":  ml_data.get("avg_event_confidence"),
        "raw_onset_count":       ml_data.get("raw_onset_count"),
        "onset_count":           ml_data.get("onset_count"),
        "ml_event_count":        ml_data.get("event_count") or len(drum_events),
        "quantization": {
            "enabled":              quant.get("enabled"),
            "profile":              quant.get("profile"),
            "subdivision":          quant.get("subdivision"),
            "grid_step_seconds":    quant.get("grid_step_seconds"),
            # --- NEW additive quantization fields ---
            "tempo_bpm":            quant.get("tempo_bpm"),
            "triplet_step_seconds": quant.get("triplet_step_seconds"),
            "time_signature":       quant.get("time_signature"),
            "num_events":           quant.get("num_events"),
        },
        "ml_processing_time_seconds": ml_data.get("processing_time_seconds"),
    }

    return drum_events, tempo_bpm, time_signature, ml_metadata


async def _post_audio_to_ml(audio_path: str) -> Optional[Dict[str, Any]]:
    """POST a stored audio file to the ML service /analyze endpoint."""
    from app.core.config import settings as _cfg
    import httpx as _httpx

    ml_url = _cfg.ML_SERVICE_URL.rstrip("/")
    try:
        with open(audio_path, "rb") as fh:
            async with _httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{ml_url}/analyze",
                    files={"file": (Path(audio_path).name, fh, "audio/wav")},
                )
        if resp.status_code != 200:
            logger.warning(
                "ML service %s returned HTTP %d (body=%s)",
                ml_url, resp.status_code, resp.text[:200],
            )
            return None
        return resp.json()
    except Exception as exc:
        logger.warning("ML service request failed (%s): %s", ml_url, exc)
        return None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def ml_health_check():
    """Health check: reports whether real librosa-based analysis is available."""
    return {
        "status": "healthy",
        "service": "ml",
        "timestamp": time.time(),
        "demo_mode": not AUDIO_LIBS_AVAILABLE,
        "librosa_available": AUDIO_LIBS_AVAILABLE,
        "message": "Full ML analysis available" if AUDIO_LIBS_AVAILABLE
                   else "Running in demo mode (librosa not available)",
    }


# ---------------------------------------------------------------------------
# Shared core — reused by the HTTP endpoint AND the notation router
# ---------------------------------------------------------------------------

async def run_video_analysis(
    video_id: UUID,
    db: AsyncSession,
    save_events: bool = False,
) -> Dict[str, Any]:
    """
    Run the full drum-detection pipeline for a stored video.

    Flow:
      1. Look up extracted AudioFile in DB (auto-extract if absent).
      2. POST audio to the external ML service (port 8001).
      3a. If the ML response carries fully classified events, USE THEM directly:
           instrument, velocity, confidence, quantized time, measure/beat —
           everything the frontend and PDF need.
      3b. If only onset times come back (legacy shape), classify locally.
      3c. If the ML service is unreachable, run a 100 % local pipeline.
      4. Compute statistics and return a stable response shape.

    Called by:
      - POST /ml/analyze-video/{video_id}
      - POST /notation/   (internal, no extra HTTP round-trip)
    """
    if not AUDIO_LIBS_AVAILABLE:
        raise HTTPException(503, "ML analysis unavailable — librosa not installed.")

    # ── Locate / auto-extract audio ──────────────────────────────────────
    audio_files = await _audio_repo.get_by_video_id(db, video_id)
    if not audio_files:
        try:
            from app.modules.media.service import VideoService as _VideoService
            from app.modules.media.repository import VideoRepository as _VideoRepo
            from uuid import UUID as _UUID
            _vrepo = _VideoRepo()
            _video = await _vrepo.get_by_id(db, video_id)
            if _video:
                _svc = _VideoService()
                await _svc.initiate_audio_extraction(
                    db=db, video_id=video_id, user_id=_UUID(str(_video.user_id))
                )
                audio_files = await _audio_repo.get_by_video_id(db, video_id)
        except Exception as _ex:
            logger.warning(
                "run_video_analysis: auto-extract failed for video %s: %s", video_id, _ex
            )

    if not audio_files:
        raise HTTPException(
            404,
            "No audio file found for this video. "
            "Use POST /videos/{video_id}/extract-audio first.",
        )

    audio_file = audio_files[0]
    audio_path = str(audio_file.storage_path)

    try:
        import librosa

        start    = time.time()
        y, sr    = librosa.load(audio_path, sr=_detector.config.sr)
        duration = float(len(y) / sr)

        # ── 1. Call ML service ──────────────────────────────────────────
        ml_data           = await _post_audio_to_ml(audio_path)
        ml_service_used   = ml_data is not None
        ml_classifications_used = False
        ml_metadata: Dict[str, Any] = {}

        drum_events_dicts: List[Dict[str, Any]] = []
        tempo_bpm: Optional[float] = None
        time_sig:  Optional[str]   = None

        # ── 2a. Full ML classification path ─────────────────────────────
        if ml_data:
            parsed_events, ml_tempo, ml_ts, ml_metadata = _parse_ml_events(ml_data)
            if parsed_events:
                drum_events_dicts       = parsed_events
                tempo_bpm               = ml_tempo
                time_sig                = ml_ts
                ml_classifications_used = True
                logger.info(
                    "ML service supplied %d classified events for video %s "
                    "(tempo=%.1f, ts=%s)",
                    len(parsed_events), video_id, tempo_bpm or 0.0, time_sig,
                )

        # ── 2b. ML responded but only with onsets (legacy) ──────────────
        if not drum_events_dicts and ml_data:
            onset_raw = (
                ml_data.get("onset_times")
                or ml_data.get("results", {}).get("summary", {}).get("onset_times")
                or []
            )
            if onset_raw:
                logger.info(
                    "ML service returned %d onsets without classification for "
                    "video %s — classifying locally",
                    len(onset_raw), video_id,
                )
                onsets   = np.array([float(t) for t in onset_raw], dtype=float)
                features = await _detector._extract_onset_features(y, int(sr), onsets)
                evt_raw  = await _detector._classify_drum_events(onsets, features, int(sr))
                evt_pp   = await _detector._post_process_events(evt_raw)
                drum_events_dicts = [
                    _drum_event_to_dict(e) for e in evt_pp
                ]

        # ── 2c. Pure local fallback (ML offline or empty) ───────────────
        if not drum_events_dicts:
            logger.info(
                "Falling back to fully local pipeline for video %s "
                "(ml_service_used=%s)",
                video_id, ml_service_used,
            )
            onsets   = await _detector._detect_onsets(y, int(sr))
            features = await _detector._extract_onset_features(y, int(sr), onsets)
            evt_raw  = await _detector._classify_drum_events(onsets, features, int(sr))
            evt_pp   = await _detector._post_process_events(evt_raw)
            drum_events_dicts = [_drum_event_to_dict(e) for e in evt_pp]

        # ── 3. Tempo / time-signature: prefer ML, fall back to librosa ──
        if tempo_bpm is None or time_sig is None:
            tempo_info = await _detector.detect_tempo_and_meter(y, int(sr))
            if tempo_bpm is None:
                tempo_bpm = float(tempo_info.get("tempo", 120))
            if time_sig is None:
                time_sig = str(tempo_info.get("meter", "4/4"))
        tempo_bpm = float(tempo_bpm or 120.0)
        time_sig  = str(time_sig or "4/4")

        # ── 4. Aggregate statistics for the frontend ────────────────────
        instrument_counts: Dict[str, int] = {}
        for e in drum_events_dicts:
            inst = e["instrument"]
            instrument_counts[inst] = instrument_counts.get(inst, 0) + 1

        confidences = [float(e.get("confidence") or 0) for e in drum_events_dicts]
        velocities  = [float(e.get("velocity")   or 0) for e in drum_events_dicts]
        avg_conf    = float(np.mean(confidences)) if confidences else 0.0
        avg_vel     = float(np.mean(velocities))  if velocities  else 0.0

        statistics: Dict[str, Any] = {
            "total_events":         len(drum_events_dicts),
            "duration_seconds":     duration,
            "events_per_second":    (len(drum_events_dicts) / duration) if duration > 0 else 0.0,
            "average_confidence":   round(avg_conf, 3),
            "average_velocity":     round(avg_vel,  3),
            "drum_counts":          dict(instrument_counts),
            "most_active_drum":     max(instrument_counts, key=instrument_counts.get)
                                    if instrument_counts else None,
        }

        elapsed = time.time() - start
        logger.info(
            "Pipeline done: %d events, tempo=%.1f BPM, ts=%s, "
            "instruments=%s, ml_service_used=%s, ml_classifications_used=%s, "
            "elapsed=%.2fs",
            len(drum_events_dicts), tempo_bpm, time_sig,
            list(instrument_counts.keys()),
            ml_service_used, ml_classifications_used, elapsed,
        )

        return {
            "video_id":                str(video_id),
            "audio_file_id":           str(audio_file.id),
            "duration_seconds":        round(duration, 2),
            "processing_time_seconds": round(elapsed, 3),
            "tempo_bpm":               round(tempo_bpm, 1),
            "time_signature":          time_sig,
            "total_events":            len(drum_events_dicts),
            "drum_events":             drum_events_dicts,
            "statistics":              statistics,
            "instrument_counts":       instrument_counts,
            "ml_service_used":         ml_service_used,
            "ml_classifications_used": ml_classifications_used,
            "ml_metadata":             ml_metadata,
            "ml_backend": (
                "ml_service_v1" if ml_classifications_used
                else ("ml_onsets+local_classify" if ml_service_used
                      else "librosa_rule_based_v2")
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ML analysis failed for video %s", video_id)
        raise HTTPException(500, f"ML analysis failed: {exc!s}")


def _drum_event_to_dict(e: DrumEvent) -> Dict[str, Any]:
    """Serialise a local DrumEvent to the unified drum_event shape."""
    instrument = _canonical_instrument(e.drum_type)
    return {
        "time_seconds":     float(e.timestamp),
        "instrument":       instrument,
        "velocity":         round(_normalise_velocity(e.velocity), 3),
        "confidence":       round(float(e.confidence), 3),
        "raw_time":         float(e.timestamp),
        "model_confidence": float(e.confidence),
        "max_probability":  float(e.confidence),
        "heuristic":        True,
        "ml_measure":       None,
        "ml_beat":          None,
        "ml_subdivision":   None,
        "ml_grid_index":    None,
        "quant_error_ms":   None,
        # NEW additive fields — None for the local (non-ML) path
        "dominant_band":    None,
        "grid_type":        None,
        "velocity_midi":    int(round(_normalise_velocity(e.velocity) * 127)),
        "strength":         None,
        "peak_rel":         None,
        "quantized_time":   None,
    }


# ---------------------------------------------------------------------------
# Core ML — analyse a stored video/audio by DB video_id
# ---------------------------------------------------------------------------

@router.post("/analyze-video/{video_id}")
async def ml_analyze_video(
    video_id: UUID,
    save_events: bool = Query(False, description="Persist detected events to DB"),
    db: AsyncSession = Depends(get_db),
):
    """
    Full ML drum analysis on a video already uploaded to the backend.

    Returns every detected drum event with per-type confidence scores,
    ready to be fed to POST /notation/.
    """
    return await run_video_analysis(video_id, db, save_events=save_events)


# ---------------------------------------------------------------------------
# Core ML — file upload (kept for backward compat, now uses real DrumDetector)
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_audio_upload(
    file: UploadFile = File(..., description="Audio or video file"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse an uploaded audio/video file.

    Pipeline:
      1. If the upload is a video, extract its audio via FFmpeg.
      2. Forward the audio to the ML service /analyze (port 8001).
      3. If the ML response carries classified events, return them.
      4. Otherwise fall back to the local librosa pipeline.

    No DB lookup required — works without auth for quick testing.
    """
    SUPPORTED_AUDIO = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
    SUPPORTED_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    ALL_SUPPORTED   = SUPPORTED_AUDIO | SUPPORTED_VIDEO

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALL_SUPPORTED:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    if not AUDIO_LIBS_AVAILABLE:
        raise HTTPException(503, "librosa not available — cannot run ML analysis")

    content = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    audio_path = tmp_path
    try:
        import librosa

        start = time.time()

        # If video → extract audio via ffmpeg
        if ext in SUPPORTED_VIDEO:
            audio_path = tmp_path + ".wav"
            result = subprocess.run(
                ["ffmpeg", "-i", tmp_path, "-vn", "-acodec", "pcm_s16le",
                 "-ar", "44100", "-ac", "1", audio_path, "-y"],
                capture_output=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg audio extraction failed")

        y, sr    = librosa.load(audio_path, sr=_detector.config.sr)
        duration = float(len(y) / sr)

        # ── 1. Try ML service ──────────────────────────────────────────
        ml_data           = await _post_audio_to_ml(audio_path)
        ml_service_used   = ml_data is not None
        ml_classifications_used = False
        ml_metadata: Dict[str, Any] = {}

        drum_events_dicts: List[Dict[str, Any]] = []
        tempo_bpm: Optional[float] = None
        time_sig:  Optional[str]   = None

        if ml_data:
            parsed_events, ml_tempo, ml_ts, ml_metadata = _parse_ml_events(ml_data)
            if parsed_events:
                drum_events_dicts       = parsed_events
                tempo_bpm               = ml_tempo
                time_sig                = ml_ts
                ml_classifications_used = True

        # ── 2. Local fallback ──────────────────────────────────────────
        if not drum_events_dicts:
            onsets   = await _detector._detect_onsets(y, int(sr))
            features = await _detector._extract_onset_features(y, int(sr), onsets)
            evt_raw  = await _detector._classify_drum_events(onsets, features, int(sr))
            evt_pp   = await _detector._post_process_events(evt_raw)
            drum_events_dicts = [_drum_event_to_dict(e) for e in evt_pp]

        # ── 3. Tempo / time-signature ──────────────────────────────────
        if tempo_bpm is None or time_sig is None:
            tempo_info = await _detector.detect_tempo_and_meter(y, int(sr))
            if tempo_bpm is None:
                tempo_bpm = float(tempo_info.get("tempo", 120))
            if time_sig is None:
                time_sig = str(tempo_info.get("meter", "4/4"))
        tempo_bpm = float(tempo_bpm or 120.0)
        time_sig  = str(time_sig or "4/4")

        # ── 4. Stats ────────────────────────────────────────────────────
        instrument_counts: Dict[str, int] = {}
        for e in drum_events_dicts:
            instrument_counts[e["instrument"]] = instrument_counts.get(e["instrument"], 0) + 1

        elapsed = time.time() - start

        return {
            "filename": file.filename,
            "file_size_bytes": len(content),
            "duration_seconds": round(duration, 2),
            "processing_time_seconds": round(elapsed, 3),
            "tempo_bpm": round(tempo_bpm, 1),
            "time_signature": time_sig,
            "total_events": len(drum_events_dicts),
            "drum_events":   drum_events_dicts,
            "instrument_counts": instrument_counts,
            "ml_service_used":         ml_service_used,
            "ml_classifications_used": ml_classifications_used,
            "ml_metadata":             ml_metadata,
            "ml_backend": (
                "ml_service_v1" if ml_classifications_used
                else "librosa_rule_based_v2"
            ),
        }

    except Exception as exc:
        logger.exception("Upload analysis failed")
        raise HTTPException(500, f"Analysis failed: {exc!s}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        if audio_path != tmp_path:
            Path(audio_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Helper — build per-type score dict from a single feature dict
# ---------------------------------------------------------------------------

async def _build_per_type_scores(detector: DrumDetector, features: Dict) -> Dict[str, float]:
    """Return normalised scores for all drum types for a single onset."""
    drum_type, confidence = await detector._classify_single_event(features)
    # We only have the winner + confidence from the current classifier.
    # Build a plausible distribution: winner gets `confidence`, rest share remainder.
    all_types = ["kick", "snare", "hi-hat", "hihat_open", "ride",
                 "crash", "tom1", "tom2", "floor_tom", "foot_hihat"]
    remainder = max(0.0, 1.0 - confidence) / max(1, len(all_types) - 1)
    return {
        t: round(confidence if t == drum_type else remainder, 3)
        for t in all_types
    }


# ---------------------------------------------------------------------------
# Models / Datasets / Analytics  (metadata endpoints, kept as-is)
# ---------------------------------------------------------------------------

@router.get("/models")
async def get_available_models():
    return {
        "models": [
            {
                "name": "LibrosaRuleBased",
                "type": "rule_based",
                "description": "Multi-feature spectral classifier (centroid, ZCR, band energy)",
                "status": "active",
                "accuracy": 0.82,
                "drum_types": ["kick", "snare", "hi-hat", "hihat_open", "ride",
                               "crash", "tom1", "tom2", "floor_tom", "foot_hihat"],
            }
        ],
        "current_model": "LibrosaRuleBased",
        "demo_mode": False,
        "librosa_available": AUDIO_LIBS_AVAILABLE,
        "timestamp": time.time(),
    }


@router.get("/datasets")
async def get_datasets():
    return {
        "datasets": [],
        "note": "No pre-trained datasets — classifier uses rule-based spectral features.",
        "timestamp": time.time(),
    }


@router.get("/stats")
async def get_stats():
    return {
        "ml_backend": "librosa_rule_based_v2",
        "audio_libs_available": AUDIO_LIBS_AVAILABLE,
        "onset_threshold": _detector.config.onset_threshold,
        "classification_threshold": _detector.config.classification_threshold,
        "timestamp": time.time(),
    }


@router.get("/analytics/performance")
async def get_performance_analytics():
    return {
        "note": "Real-time performance metrics not yet persisted.",
        "librosa_available": AUDIO_LIBS_AVAILABLE,
        "timestamp": time.time(),
    }


@router.get("/analytics/usage")
async def get_usage_analytics():
    return {
        "note": "Usage analytics not yet persisted.",
        "timestamp": time.time(),
    }


@router.post("/debug-upload")
async def debug_upload(file: UploadFile = File(...)):
    content = await file.read()
    ext = Path(file.filename or "").suffix.lower()
    SUPPORTED = {".wav", ".mp3", ".flac", ".m4a", ".ogg",
                 ".mp4", ".avi", ".mov", ".mkv", ".webm"}
    return {
        "filename": file.filename,
        "extension": ext,
        "file_size_bytes": len(content),
        "file_size_mb": round(len(content) / 1048576, 2),
        "is_supported": ext in SUPPORTED,
        "content_type": file.content_type,
        "librosa_available": AUDIO_LIBS_AVAILABLE,
        "timestamp": time.time(),
    }
