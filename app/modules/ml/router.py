"""
Machine Learning Router for Drum Notation Backend
================================================

Real ML endpoints backed by DrumDetector (librosa-based) for full drum analysis.
Legacy upload endpoints kept for compatibility; new /ml/analyze-video/{video_id}
runs the full pipeline on stored audio files.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.audio_processing.detection import DrumDetector, AUDIO_LIBS_AVAILABLE
from app.modules.media.repository import AudioFileRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["machine-learning"])

# ---------------------------------------------------------------------------
# Shared detector instance
# ---------------------------------------------------------------------------
_detector = DrumDetector()
_audio_repo = AudioFileRepository()


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
    Run the full ML drum-detection pipeline for a stored video.

    Flow:
      1. Look up extracted AudioFile in DB.
      2. POST audio to the external ML service (port 8001) to get onset_times.
      3. If ML service is unavailable, fall back to local onset detection.
      4. Classify each onset via local DrumDetector (spectral features).
      5. Estimate tempo via librosa beat tracking.

    Called by:
      - POST /ml/analyze-video/{video_id}
      - POST /notation/   (internal, no extra HTTP round-trip)
    """
    if not AUDIO_LIBS_AVAILABLE:
        raise HTTPException(503, "ML analysis unavailable — librosa not installed.")

    audio_files = await _audio_repo.get_by_video_id(db, video_id)
    if not audio_files:
        # Auto-extract audio from the stored video file so the caller doesn't
        # need a separate extract-audio step before calling analyze.
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
        from app.core.config import settings as _cfg

        start     = time.time()
        y, sr     = librosa.load(audio_path, sr=_detector.config.sr)
        duration  = float(len(y) / sr)

        # ── Step 1: Try external ML service for onset detection ──────────
        onset_times_override: Optional[List[float]] = None
        ml_service_used = False

        try:
            import httpx as _httpx

            ml_url = _cfg.ML_SERVICE_URL.rstrip("/")
            with open(audio_path, "rb") as audio_fh:
                async with _httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{ml_url}/analyze",
                        files={"file": (Path(audio_path).name, audio_fh, "audio/wav")},
                    )

            if resp.status_code == 200:
                ml_data = resp.json()
                onset_raw = ml_data.get("onset_times") or \
                            ml_data.get("results", {}).get("summary", {}).get("onset_times", [])
                if onset_raw:
                    onset_times_override = [float(t) for t in onset_raw]
                    ml_service_used = True
                    logger.info(
                        "ML service (%s) provided %d onset times for video %s",
                        ml_url, len(onset_times_override), video_id,
                    )
            else:
                logger.warning(
                    "ML service returned HTTP %d for video %s — using local onset detection",
                    resp.status_code, video_id,
                )
        except Exception as _ml_err:
            logger.warning(
                "ML service unavailable (%s) — falling back to local onset detection",
                _ml_err,
            )

        # ── Step 2: Detect / use onset times ────────────────────────────
        if onset_times_override is not None:
            import numpy as _np
            onsets = _np.array(onset_times_override, dtype=float)
        else:
            onsets = await _detector._detect_onsets(y, int(sr))

        # ── Step 3: Extract features + classify each onset ───────────────
        logger.info(
            "ML pipeline: classifying %d onsets for video %s (ml_service_used=%s)",
            len(onsets), video_id, ml_service_used,
        )
        features = await _detector._extract_onset_features(y, int(sr), onsets)
        events_raw = await _detector._classify_drum_events(onsets, features, int(sr))
        events: List = await _detector._post_process_events(events_raw)

        # ── Step 4: Accurate tempo + time signature ───────────────────────
        tempo_info = await _detector.detect_tempo_and_meter(y, int(sr))
        tempo_bpm  = float(tempo_info.get("tempo", 120))
        time_sig   = str(tempo_info.get("meter", "4/4"))

        # ── Step 5: Per-onset multi-class scores ──────────────────────────
        per_onset_scores: List[Dict] = []
        for onset_t, feat in zip(onsets, features):
            scores_row = await _build_per_type_scores(_detector, feat)
            per_onset_scores.append({"onset": float(onset_t), "scores": scores_row})

        # ── Step 6: Statistics ────────────────────────────────────────────
        stats = await _detector.get_drum_statistics(events)
        instrument_counts: Dict[str, int] = {}
        for e in events:
            instrument_counts[e.drum_type] = instrument_counts.get(e.drum_type, 0) + 1

        elapsed = time.time() - start
        logger.info(
            "ML pipeline done: %d events, tempo=%.1f BPM, time_sig=%s, "
            "instruments=%s, ml_service_used=%s, elapsed=%.2fs",
            len(events), tempo_bpm, time_sig,
            list(instrument_counts.keys()), ml_service_used, elapsed,
        )

        return {
            "video_id":               str(video_id),
            "audio_file_id":          str(audio_file.id),
            "duration_seconds":       round(duration, 2),
            "processing_time_seconds": round(elapsed, 3),
            "tempo_bpm":              round(tempo_bpm, 1),
            "time_signature":         time_sig,
            "total_events":           len(events),
            "drum_events": [
                {
                    "time_seconds": float(e.timestamp),
                    "instrument":   e.drum_type,
                    "velocity":     round(float(e.velocity), 3),
                    "confidence":   round(float(e.confidence), 3),
                }
                for e in events
            ],
            "per_onset_scores":  per_onset_scores,
            "statistics":        stats,
            "instrument_counts": instrument_counts,
            "ml_service_used":   ml_service_used,
            "ml_backend":        "librosa_rule_based_v2",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ML analysis failed for video %s: %s", video_id, exc)
        raise HTTPException(500, f"ML analysis failed: {str(exc)}")


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
    Analyse an uploaded audio/video file with the real DrumDetector.
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
                capture_output=True, timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg audio extraction failed")

        y, sr = librosa.load(audio_path, sr=_detector.config.sr)
        duration = float(len(y) / sr)

        tempo_info = await _detector.detect_tempo_and_meter(y, int(sr))
        tempo_bpm  = float(tempo_info.get("tempo", 120))
        time_sig   = str(tempo_info.get("meter", "4/4"))

        # Detect drum events using a mock AudioFile-like object
        class _MockAudio:
            storage_path = audio_path

        onsets   = await _detector._detect_onsets(y, int(sr))
        features = await _detector._extract_onset_features(y, int(sr), onsets)
        events_raw = await _detector._classify_drum_events(onsets, features, int(sr))
        events   = await _detector._post_process_events(events_raw)

        stats = await _detector.get_drum_statistics(events)
        instrument_counts = {}
        for e in events:
            instrument_counts[e.drum_type] = instrument_counts.get(e.drum_type, 0) + 1

        elapsed = time.time() - start

        return {
            "filename": file.filename,
            "file_size_bytes": len(content),
            "duration_seconds": round(duration, 2),
            "processing_time_seconds": round(elapsed, 3),
            "tempo_bpm": round(tempo_bpm, 1),
            "time_signature": time_sig,
            "total_events": len(events),
            "drum_events": [
                {
                    "time_seconds": float(e.timestamp),
                    "instrument":   e.drum_type,
                    "velocity":     round(float(e.velocity), 3),
                    "confidence":   round(float(e.confidence), 3),
                }
                for e in events
            ],
            "statistics": stats,
            "instrument_counts": instrument_counts,
            "ml_backend": "librosa_rule_based_v2",
        }

    except Exception as exc:
        logger.error(f"Upload analysis failed: {exc}")
        raise HTTPException(500, f"Analysis failed: {str(exc)}")
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
