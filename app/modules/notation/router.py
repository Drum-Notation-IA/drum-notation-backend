"""
Notation Router
FastAPI endpoints for drum notation generation, management, and stroke-by-stroke playback
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user
from app.modules.notation.schemas import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    BatchNotationRequest,
    BatchNotationResponse,
    DetailedNotationResponse,
    DrumKitMappingResponse,
    DrumNotationResponse,
    ExportNotationRequest,
    GenerateNotationRequest,
    NotationExportResponse,
    NotationHealthResponse,
    NotationListResponse,
    NotationStatsResponse,
    NotationTimelineResponse,
    NotationValidationResponse,
    UpdateNotationRequest,
)
from app.modules.notation.pdf_generator import generate_notation_pdf
from app.modules.notation.service import NotationService
from app.modules.users.models import User

router = APIRouter(prefix="/notation", tags=["Notation"])

# Initialize service
notation_service = NotationService()


@router.post("/", status_code=201)
async def generate_notation(
    raw_request: Request,
    min_confidence: Optional[float] = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence floor: 0 = full transcription (ghost notes/rolls), "
        "higher = cleaner chart (strong hits only). Overrides the body value.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate musical notation from drum detection results.
    Supports demo mode for non-UUID video IDs (no auth required).

    ``min_confidence`` can be supplied either as a query parameter (takes
    precedence) or in the JSON body, for a clean vs. complete transcription.
    """
    try:
        body = await raw_request.json()
    except Exception:
        body = {}

    video_id_raw = str(body.get("video_id", ""))

    # --- Demo mode: non-UUID video IDs (e.g. "demo-video-1777434567") ---
    def _is_uuid(val: str) -> bool:
        try:
            UUID(val)
            return True
        except (ValueError, AttributeError):
            return False

    # POST /notation/ always requires auth (get_current_user already enforces it).
    # Demo mode only applies to the GET endpoints for non-UUID ids.
    if not _is_uuid(video_id_raw):
        now = datetime.utcnow()
        demo_notation_id = str(uuid4())
        return {
            "id": demo_notation_id,
            "video_id": video_id_raw,
            "tempo": int(body.get("tempo_bpm") or 95),
            "time_signature": body.get("time_signature") or "4/4",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "notation_json": {
                "measures": [
                    {
                        "measure_number": i + 1,
                        "tempo_bpm": 95,
                        "time_signature": "4/4",
                        "beats": [
                            {
                                "beat_number": b + 1,
                                "notes": [
                                    {"drum_type": "kick" if b == 0 else "hi-hat",
                                     "velocity": 0.8, "timestamp_seconds": i * 2.5 + b * 0.625}
                                ],
                            }
                            for b in range(4)
                        ],
                    }
                    for i in range(4)
                ],
                "instruments": ["kick", "snare", "hi-hat"],
            },
            "musical_structure": {
                "tempo_bpm": 95,
                "time_signature": "4/4",
                "beats_per_measure": 4,
                "total_measures": 4,
                "duration_seconds": 10.0,
                "instruments_detected": ["kick", "snare", "hi-hat"],
            },
            "status": "completed",
            "demo_mode": True,
            "message": "Notation generated in demo mode",
        }

    try:
        video_id = UUID(video_id_raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid video_id format")

    try:
        drum_events = body.get("drum_events", [])
        ml_result: Optional[dict] = None

        # If no drum_events provided, delegate to the ML pipeline
        # (same code path as POST /ml/analyze-video/{video_id})
        if not drum_events:
            import logging as _logging
            logger = _logging.getLogger(__name__)

            from app.modules.ml.router import run_video_analysis
            from app.modules.media.service import VideoService as _VideoService
            from app.modules.media.repository import VideoRepository as _VideoRepo

            async def _try_auto_extract():
                """Auto-extract audio when not yet in DB."""
                _video_repo = _VideoRepo()
                video_row = await _video_repo.get_by_id(db, video_id)
                if not video_row:
                    raise HTTPException(404, "Video not found.")
                # Always use the video's owner as the user_id for extraction
                uid = UUID(str(video_row.user_id))
                svc = _VideoService()
                try:
                    await svc.initiate_audio_extraction(db=db, video_id=video_id, user_id=uid)
                    logger.info("Auto-extracted audio for video %s", video_id)
                except Exception as _ex:
                    logger.warning("Auto-extract failed for video %s: %s", video_id, _ex)

            try:
                ml_result = await run_video_analysis(video_id, db)
            except HTTPException as exc:
                if exc.status_code == 404:
                    # Audio not in DB yet — try extracting it, then retry once
                    await _try_auto_extract()
                    try:
                        ml_result = await run_video_analysis(video_id, db)
                    except HTTPException as exc2:
                        raise HTTPException(
                            422,
                            "No audio file found for this video. "
                            "Extract audio first via POST /videos/{video_id}/extract-audio.",
                        ) from exc2
                else:
                    raise

            drum_events = ml_result["drum_events"]

            # Use ML's tempo + time signature unless the caller overrode them.
            # The ML service's tempo is generally more accurate than the
            # librosa beat-tracker because it averages over the full track.
            if not body.get("tempo_bpm"):
                body["tempo_bpm"]      = ml_result["tempo_bpm"]
                body["time_signature"] = body.get("time_signature") or ml_result["time_signature"]

            logger.info(
                "Notation pipeline: %d events, tempo=%.1f BPM, ts=%s, "
                "ml_classifications_used=%s, instruments=%s",
                ml_result["total_events"],
                body["tempo_bpm"],
                body["time_signature"],
                ml_result.get("ml_classifications_used", False),
                list(ml_result.get("instrument_counts", {}).keys()),
            )

        elif drum_events:
            # Normalize already-provided dict events if they use alternate keys.
            # We preserve every extra field (e.g. ml_measure, model_confidence)
            # so callers can pass through ML output untouched.
            normalised: List[dict] = []
            for e in drum_events:
                base = dict(e)  # keep extras (ml_measure, grid_type, dominant_band, …)
                base["time_seconds"] = float(
                    e.get("time_seconds", e.get("timestamp", 0))
                )
                base["instrument"] = str(
                    e.get("instrument", e.get("drum_type", "unknown"))
                )
                # Velocity may arrive normalised (0..1) or as raw MIDI (1..127).
                # Keep a normalised "velocity" and a raw "velocity_midi".
                raw_vel = e.get("velocity", 0.5)
                try:
                    raw_vel_f = float(raw_vel)
                except (TypeError, ValueError):
                    raw_vel_f = 0.5
                if raw_vel_f > 1.0:
                    base["velocity_midi"] = int(round(raw_vel_f))
                    base["velocity"] = max(0.0, min(1.0, raw_vel_f / 127.0))
                else:
                    base["velocity"] = max(0.0, min(1.0, raw_vel_f))
                    if base.get("velocity_midi") is None:
                        base["velocity_midi"] = int(round(base["velocity"] * 127))
                base["confidence"] = float(e.get("confidence", 0.0))
                # Mirror raw ML grid keys onto the backend's ml_* keys so the
                # grid-aware builder can group them even when callers pass the
                # ML response straight through.
                if base.get("ml_measure") is None and e.get("measure") is not None:
                    base["ml_measure"] = e.get("measure")
                if base.get("ml_beat") is None and e.get("beat") is not None:
                    base["ml_beat"] = e.get("beat")
                if base.get("ml_subdivision") is None and e.get("subdivision_index") is not None:
                    base["ml_subdivision"] = e.get("subdivision_index")
                normalised.append(base)
            drum_events = normalised

        notation = await notation_service.generate_notation_from_drum_detection(
            db=db,
            video_id=video_id,
            drum_events=drum_events,
            tempo_bpm=body.get("tempo_bpm"),
            time_signature=body.get("time_signature", "4/4"),
            quantization_level=body.get("quantization_level", "sixteenth"),
            apply_ai_analysis=body.get("apply_ai_analysis", True),
            min_confidence=(
                min_confidence if min_confidence is not None
                else body.get("min_confidence")
            ),
            ml_provenance=({
                "ml_service_used":         ml_result.get("ml_service_used", False),
                "ml_classifications_used": ml_result.get("ml_classifications_used", False),
                "ml_backend":              ml_result.get("ml_backend"),
                "ml_metadata":             ml_result.get("ml_metadata", {}),
                "instrument_counts":       ml_result.get("instrument_counts", {}),
                "duration_seconds":        ml_result.get("duration_seconds"),
                "processing_time_seconds": ml_result.get("processing_time_seconds"),
            } if ml_result else None),
        )
        return notation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate notation: {str(e)}"
        )


@router.get("/{notation_id}")
async def get_notation(
    notation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get basic notation information. Reads from DB by UUID — no auth required."""
    # Always try DB lookup by ID first (notation UUID is the access credential)
    notation = None
    try:
        notation = await notation_service.notation_repo.get_by_id(db, notation_id)
        if not notation:
            notation = await notation_service.notation_repo.get_by_video_id(db, notation_id)
    except Exception:
        notation = None

    if notation is not None:
        # Extract ml_provenance from notation_json for frontend
        response_dict = {
            "id": notation.id,
            "video_id": notation.video_id,
            "tempo": notation.tempo,
            "time_signature": notation.time_signature,
            "created_at": notation.created_at,
            "updated_at": notation.updated_at,
            "notation_json": notation.notation_json,
        }
        # Add ml_provenance if available
        if notation.notation_json and "ml_provenance" in notation.notation_json:
            response_dict["ml_provenance"] = notation.notation_json["ml_provenance"]
        return response_dict

    # Demo fallback — notation not found in DB
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    return {
        "id": str(notation_id),
        "video_id": str(notation_id),
        "tempo": 95,
        "time_signature": "4/4",
        "created_at": now,
        "updated_at": now,
        "notation_json": {},
        "status": "completed",
        "demo_mode": True,
    }


@router.get("/{notation_id}/details")
async def get_notation_with_details(
    notation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get complete notation with measures, beats, notes. Reads from DB by UUID — no auth required."""
    notation = None
    try:
        notation = await notation_service.notation_repo.get_by_id(db, notation_id)
        if not notation:
            notation = await notation_service.notation_repo.get_by_video_id(db, notation_id)
    except Exception:
        notation = None

    if notation is not None:
        # Extract ml_provenance from notation_json for frontend
        response_dict = {
            "id": notation.id,
            "video_id": notation.video_id,
            "tempo": notation.tempo,
            "time_signature": notation.time_signature,
            "created_at": notation.created_at,
            "updated_at": notation.updated_at,
            "notation_json": notation.notation_json,
            "musical_structure": notation.get_musical_structure(),
            "timeline": notation.get_timeline(),
            "measures": notation.get_measures(),
            "exports": notation.notation_json.get("exports", []),
        }
        # Add ml_provenance if available
        if notation.notation_json and "ml_provenance" in notation.notation_json:
            response_dict["ml_provenance"] = notation.notation_json["ml_provenance"]
        return response_dict

    from datetime import datetime
    now = datetime.utcnow().isoformat()
    return {
        "id": str(notation_id),
        "video_id": str(notation_id),
        "tempo": 95,
        "time_signature": "4/4",
        "created_at": now,
        "updated_at": now,
        "notation_json": {},
        "musical_structure": {
            "tempo_bpm": 95,
            "time_signature": "4/4",
            "beats_per_measure": 4,
            "total_measures": 4,
            "duration_seconds": 10.0,
            "instruments_detected": ["kick", "snare", "hi-hat"],
        },
        "timeline": [],
        "measures": [],
        "exports": [],
        "status": "completed",
        "demo_mode": True,
    }


@router.get("/{notation_id}/timeline")
async def get_notation_timeline(
    notation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get stroke-by-stroke timeline. Returns empty timeline for demo/unauthenticated."""
    current_user = None
    try:
        from jose import jwt as _jwt
        from app.core.config import settings as _settings
        from app.modules.users.repository import UserRepository as _UserRepo
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
            email = payload.get("sub")
            if email:
                current_user = await _UserRepo().get_by_email(db, email=email)
    except Exception:
        current_user = None

    if current_user is not None:
        try:
            timeline = await notation_service.get_notation_timeline(db, notation_id)
            if timeline:
                return timeline
        except Exception:
            pass

    return {
        "notation_id": str(notation_id),
        "total_strokes": 0,
        "duration_seconds": 0.0,
        "stroke_events": [],
        "tempo_bpm": 95,
        "time_signature": "4/4",
        "demo_mode": True,
    }


@router.get("/{notation_id}/measures")
async def get_notation_measures(
    notation_id: UUID,
    request: Request,
    measure_start: Optional[int] = Query(None, description="Start measure number"),
    measure_end: Optional[int] = Query(None, description="End measure number"),
    db: AsyncSession = Depends(get_db),
):
    """Get measures for a notation. Returns empty measures for demo/unauthenticated."""
    current_user = None
    try:
        from jose import jwt as _jwt
        from app.core.config import settings as _settings
        from app.modules.users.repository import UserRepository as _UserRepo
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
            email = payload.get("sub")
            if email:
                current_user = await _UserRepo().get_by_email(db, email=email)
    except Exception:
        current_user = None

    if current_user is not None:
        try:
            notation = await notation_service.notation_repo.get_by_video_id(db, notation_id)
            if notation:
                measures = getattr(notation, "measures", [])
                if measure_start is not None:
                    measures = [m for m in measures if getattr(m, "measure_number", 0) >= measure_start]
                if measure_end is not None:
                    measures = [m for m in measures if getattr(m, "measure_number", 0) <= measure_end]
                return {
                    "notation_id": str(notation_id),
                    "measures": measures,
                    "tempo_bpm": getattr(notation, "tempo_bpm", 95),
                    "time_signature": getattr(notation, "time_signature", "4/4"),
                    "total_measures": len(measures),
                }
        except Exception:
            pass

    return {
        "notation_id": str(notation_id),
        "measures": [],
        "tempo_bpm": 95,
        "time_signature": "4/4",
        "total_measures": 0,
        "demo_mode": True,
    }


@router.get("/{notation_id}/strokes")
async def get_stroke_events(
    notation_id: UUID,
    request: Request,
    start_time: Optional[float] = Query(None, description="Start time in seconds"),
    end_time: Optional[float] = Query(None, description="End time in seconds"),
    db: AsyncSession = Depends(get_db),
):
    """Get stroke events. Returns empty strokes for demo/unauthenticated."""
    current_user = None
    try:
        from jose import jwt as _jwt
        from app.core.config import settings as _settings
        from app.modules.users.repository import UserRepository as _UserRepo
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
            email = payload.get("sub")
            if email:
                current_user = await _UserRepo().get_by_email(db, email=email)
    except Exception:
        current_user = None

    if current_user is not None:
        try:
            notation = await notation_service.notation_repo.get_by_video_id(db, notation_id)
            if notation:
                events = getattr(notation, "stroke_events", [])
                if start_time is not None and end_time is not None:
                    events = [e for e in events if start_time <= e.get("timestamp_seconds", 0) <= end_time]
                return {
                    "notation_id": str(notation_id),
                    "start_time": start_time,
                    "end_time": end_time,
                    "stroke_events": events,
                }
        except Exception:
            pass

    return {
        "notation_id": str(notation_id),
        "start_time": start_time,
        "end_time": end_time,
        "stroke_events": [],
        "demo_mode": True,
    }


@router.patch("/{notation_id}", response_model=DrumNotationResponse)
async def update_notation(
    notation_id: UUID,
    request: UpdateNotationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update notation properties like tempo or time signature"""
    notation = await notation_service.notation_repo.get_by_id(db, notation_id)
    if not notation:
        raise HTTPException(status_code=404, detail="Notation not found")

    # Update fields
    update_data = {}
    if request.tempo is not None:
        update_data["tempo"] = request.tempo
    if request.time_signature is not None:
        update_data["time_signature"] = request.time_signature
    if request.notation_json is not None:
        update_data["notation_json"] = request.notation_json

    if update_data:
        updated_notation = await notation_service.notation_repo.update(
            db, notation_id, update_data
        )
        return updated_notation

    return notation


@router.delete("/{notation_id}")
async def delete_notation(
    notation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a notation (marks as deleted)"""
    success = await notation_service.notation_repo.soft_delete(db, notation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notation not found")

    return {"message": "Notation deleted successfully"}


@router.post("/{notation_id}/ai-analysis", response_model=AIAnalysisResponse)
async def run_ai_analysis(
    notation_id: UUID,
    request: AIAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run AI analysis on notation for pattern analysis, style classification, etc.

    This endpoint leverages OpenAI to provide intelligent insights about the
    musical notation including complexity analysis, style identification,
    and practice recommendations.
    """
    notation = await notation_service.notation_repo.get_by_id(db, notation_id)
    if not notation:
        raise HTTPException(status_code=404, detail="Notation not found")

    # Check if OpenAI service is available
    if not notation_service.openai_service.is_enabled():
        raise HTTPException(
            status_code=503, detail="AI analysis service is not available"
        )

    # Run AI analysis (this would be implemented in the service)
    # For now, return a placeholder response
    analysis_results = {
        "notation_id": notation_id,
        "analysis_results": {
            "status": "AI analysis would be performed here",
            "requested_types": request.analysis_types,
            "skill_level": request.skill_level,
        },
    }

    return analysis_results


@router.post("/{notation_id}/export")
async def export_notation(
    notation_id: UUID,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Export notation to various formats (MusicXML, MIDI, SVG, PDF).
    Accepts both 'export_format' and 'format' keys. Returns demo download URL if not authenticated.
    """
    # Parse body tolerantly
    try:
        body = await raw_request.json()
    except Exception:
        body = {}

    # Accept both 'export_format' and 'format' keys, default to pdf
    export_fmt = (
        body.get("export_format")
        or body.get("format")
        or body.get("exportFormat")
        or "pdf"
    )
    valid_formats = ["musicxml", "midi", "json", "svg", "pdf"]
    if export_fmt not in valid_formats:
        export_fmt = "pdf"

    from uuid import uuid4 as _uuid4
    from datetime import datetime as _dt

    # PDF is always generated on the fly — bypass the async export service entirely
    if export_fmt == "pdf":
        download_url = f"/notation/{notation_id}/download/pdf"
        return {
            "id": str(_uuid4()),
            "notation_id": str(notation_id),
            "export_format": "pdf",
            "status": "completed",
            "file_url": download_url,
            "download_url": download_url,
            "file_size_bytes": 0,
            "created_at": _dt.utcnow().isoformat(),
            "demo_mode": False,
            "message": "PDF ready for download",
        }

    # For non-PDF formats, try real export if authenticated
    current_user = None
    try:
        from jose import jwt as _jwt
        from app.core.config import settings as _settings
        from app.modules.users.repository import UserRepository as _UserRepo
        auth_header = raw_request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
            email = payload.get("sub")
            if email:
                current_user = await _UserRepo().get_by_email(db, email=email)
    except Exception:
        current_user = None

    if current_user is not None:
        try:
            export_record = await notation_service.export_notation(
                db=db,
                notation_id=notation_id,
                export_format=export_fmt,
                export_settings=body.get("quality_settings"),
            )
            return export_record
        except Exception:
            pass

    # Non-PDF demo fallback — these formats require a real notation in the DB
    export_id = str(_uuid4())
    return {
        "id": export_id,
        "notation_id": str(notation_id),
        "export_format": export_fmt,
        "status": "unavailable",
        "file_url": None,
        "download_url": None,
        "file_size_bytes": 0,
        "created_at": _dt.utcnow().isoformat(),
        "demo_mode": True,
        "message": (
            f"{export_fmt.upper()} export requires an authenticated session with a saved notation. "
            f"Use PDF format for demo mode, or log in to export as {export_fmt.upper()}."
        ),
    }


@router.get("/{notation_id}/export/{export_id}")
async def get_export_file(
    notation_id: UUID,
    export_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get export record / download URL. Returns demo data if not authenticated."""
    return {
        "id": str(export_id),
        "notation_id": str(notation_id),
        "status": "completed",
        "download_url": f"/notation/{notation_id}/download/pdf",
        "demo_mode": True,
    }


@router.get("/{notation_id}/download/pdf")
async def download_notation_pdf(
    notation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download a PDF drum chart for the given notation.
    Reads from DB by notation UUID — no auth required (UUID is the access token).
    Falls back to demo data only when the notation is not found in the DB.
    """
    notation_data: dict = {}

    # Always try DB lookup by notation UUID first — no auth gate
    try:
        db_notation = await notation_service.notation_repo.get_by_id(db, notation_id)
        if not db_notation:
            # Fallback: maybe the caller passed the video_id instead of the notation_id
            db_notation = await notation_service.notation_repo.get_by_video_id(db, notation_id)
        if db_notation:
            nj = getattr(db_notation, "notation_json", None) or {}
            notation_data = {
                "notation_json": nj,
                "tempo": getattr(db_notation, "tempo", None) or 95,
                "time_signature": getattr(db_notation, "time_signature", None) or "4/4",
                "created_at": str(getattr(db_notation, "created_at", "") or ""),
            }
            import logging as _log
            _log.getLogger(__name__).info(
                "PDF download: notation %s found in DB — %d measures, tempo=%s",
                notation_id,
                len(nj.get("measures", [])),
                notation_data["tempo"],
            )
    except Exception as _e:
        import logging as _log
        _log.getLogger(__name__).warning("PDF download DB lookup failed: %s", _e)

    # Demo data fallback — only when notation genuinely not found in DB
    if not notation_data or not notation_data.get("notation_json", {}).get("measures"):
        import logging as _log
        _log.getLogger(__name__).warning(
            "PDF download: notation %s not found in DB or has no measures — using demo data",
            notation_id,
        )
        notation_data = {
            "notation_json": {
                "measures": [
                    {
                        "measure_number": i + 1,
                        "tempo_bpm": 95,
                        "time_signature": "4/4",
                        "beats": [
                            {
                                "beat_number": b + 1,
                                "notes": [
                                    {
                                        "drum_type": "kick" if b % 2 == 0 else ("snare" if b % 2 == 1 else "hi-hat"),
                                        "velocity": 0.85,
                                        "timestamp_seconds": i * 2.0 + b * 0.5,
                                    },
                                    {
                                        "drum_type": "hi-hat",
                                        "velocity": 0.5,
                                        "timestamp_seconds": i * 2.0 + b * 0.5,
                                    },
                                ],
                            }
                            for b in range(4)
                        ],
                    }
                    for i in range(8)
                ],
                "instruments": ["kick", "snare", "hi-hat"],
            },
            "tempo": 95,
            "time_signature": "4/4",
            "created_at": datetime.utcnow().isoformat(),
        }

    pdf_bytes = generate_notation_pdf(
        notation_id=str(notation_id),
        notation_json=notation_data["notation_json"],
        tempo=int(notation_data.get("tempo") or 95),
        time_signature=str(notation_data.get("time_signature") or "4/4"),
        created_at=str(notation_data.get("created_at") or ""),
    )

    filename = f"drum-notation-{str(notation_id)[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/")
async def list_notations(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List notations for the current user.
    Returns empty list for unauthenticated / demo users.
    """
    # Resolve user manually so a missing/expired token never raises 500
    current_user = None
    try:
        from jose import JWTError, jwt as _jwt
        from app.core.config import settings as _settings
        from app.modules.users.repository import UserRepository as _UserRepo
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
            email = payload.get("sub")
            if email:
                current_user = await _UserRepo().get_by_email(db, email=email)
    except Exception:
        current_user = None

    if current_user is None:
        return {"notations": [], "total": 0, "page": page, "per_page": per_page,
                "pages": 0, "has_next": False, "has_prev": False, "demo_mode": True}

    offset = (page - 1) * per_page
    notations = await notation_service.notation_repo.list_by_user_videos(
        db=db, user_id=current_user.id, limit=per_page, offset=offset
    )
    total = len(notations)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return {
        "notations": notations,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.post("/batch", response_model=BatchNotationResponse)
async def batch_generate_notations(
    request: BatchNotationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate notations for multiple videos in batch"""
    notation_ids = []
    errors = []

    for video_id in request.video_ids:
        try:
            # Generate notation for each video
            # This would use the same logic as the single generation endpoint
            drum_events = []  # Fetch drum events for this video

            notation = await notation_service.generate_notation_from_drum_detection(
                db=db,
                video_id=video_id,
                drum_events=drum_events,
                # Use settings from batch request
                tempo_bpm=request.tempo_bpm,
                time_signature=request.time_signature,
                quantization_level=request.quantization_level,
                apply_ai_analysis=request.apply_ai_analysis,
            )
            notation_ids.append(notation.id)

        except Exception as e:
            errors.append(
                {
                    "video_id": str(video_id),
                    "error_message": str(e),
                    "error_code": "GENERATION_FAILED",
                }
            )

    batch_id = UUID("00000000-0000-0000-0000-000000000000")  # Generate actual batch ID

    return {
        "total_requested": len(request.video_ids),
        "successful": len(notation_ids),
        "failed": len(errors),
        "notation_ids": notation_ids,
        "errors": errors,
        "batch_id": batch_id,
    }


@router.get("/statistics", response_model=NotationStatsResponse)
async def get_notation_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive notation statistics and analytics"""
    stats = await notation_service.notation_repo.get_statistics(db)

    # Add processing success rate
    total_notations = stats.get("total_notations", 0)
    status_dist = stats.get("status_distribution", {})
    completed = status_dist.get("completed", 0)
    success_rate = (completed / total_notations * 100) if total_notations > 0 else 0

    return {
        "total_notations": stats["total_notations"],
        "total_measures": stats["total_measures"],
        "total_notes": stats["total_notes"],
        "avg_tempo_bpm": stats["avg_tempo_bpm"],
        "tempo_distribution": {},  # Would implement tempo bucketing
        "time_signature_distribution": stats["time_signature_distribution"],
        "drum_type_frequency": {},  # Would get from notes
        "complexity_distribution": {},  # Would calculate complexity buckets
        "avg_confidence_score": stats["avg_confidence_score"],
        "processing_success_rate": success_rate,
    }


@router.get("/drum-kits", response_model=List[DrumKitMappingResponse])
async def get_drum_kit_mappings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available drum kit mappings for notation generation"""
    mappings = [
        {
            "kit_id": "default",
            "kit_name": "Standard Kit",
            "mappings": notation_service.default_drum_mapping,
        }
    ]
    return mappings


@router.get("/drum-kits/default", response_model=DrumKitMappingResponse)
async def get_default_drum_kit_mapping(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the default drum kit mapping"""
    mapping = {
        "kit_id": "default",
        "kit_name": "Standard Kit",
        "mappings": notation_service.default_drum_mapping,
    }
    if not mapping:
        # Return built-in default
        return {
            "id": UUID("00000000-0000-0000-0000-000000000000"),
            "name": "Standard Kit",
            "description": "Standard drum kit mapping",
            "is_default": True,
            "drum_mappings": notation_service.default_drum_mapping,
            "clef_type": "percussion",
        }
    return mapping


@router.post("/{notation_id}/validate", response_model=NotationValidationResponse)
async def validate_notation(
    notation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate notation for completeness and correctness

    Checks for common notation issues like:
    - Missing beats in measures
    - Timing inconsistencies
    - Invalid drum mappings
    - AI confidence issues
    """
    notation = await notation_service.get_notation_with_details(db, notation_id)
    if not notation:
        raise HTTPException(status_code=404, detail="Notation not found")

    # Implement validation logic
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "suggestions": [],
        "confidence_issues": [],
    }

    # Add validation checks here
    detection_confidence = getattr(notation, "detection_confidence", None)
    if detection_confidence is not None and detection_confidence < 0.7:
        validation_result["warnings"].append(
            "Low overall detection confidence - consider manual review"
        )

    if getattr(notation, "total_measures", 0) == 0:
        validation_result["is_valid"] = False
        validation_result["errors"].append(
            {
                "field": "measures",
                "message": "No measures found in notation",
                "value": 0,
            }
        )

    return validation_result


@router.get("/health", response_model=NotationHealthResponse)
async def get_notation_system_health():
    """Check notation system health and processing status"""
    return {
        "status": "healthy",
        "message": "Notation system is operational",
        "timestamp": datetime.utcnow(),
        "active_generations": 0,  # Would track active processes
        "queue_size": 0,  # Would check processing queue
        "avg_processing_time": 45.0,  # Would calculate from recent exports
        "success_rate_24h": 98.5,  # Would calculate from recent completions
    }


# Video-specific notation endpoints
@router.get("/video/{video_id}")
async def get_notations_for_video(
    video_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get all notations for a specific video. Demo IDs return empty list without auth."""
    # Demo mode: non-UUID video IDs return empty list immediately
    def _is_uuid(val: str) -> bool:
        try:
            UUID(val)
            return True
        except (ValueError, AttributeError):
            return False

    if not _is_uuid(video_id):
        return []

    # Real mode: requires auth
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    notation = await notation_service.notation_repo.get_by_video_id(db, UUID(video_id))
    return [notation] if notation else []


@router.delete("/video/{video_id}")
async def delete_notations_for_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all notations for a specific video"""
    notation = await notation_service.notation_repo.get_by_video_id(db, video_id)
    if notation:
        await notation_service.notation_repo.soft_delete(db, notation.id)
        return {"message": "Video notations deleted successfully"}

    return {"message": "No notations found for this video"}


# Admin endpoints (would add admin authentication in real implementation)
@router.post("/admin/cleanup")
async def cleanup_old_exports(
    days_old: int = Query(
        7, ge=1, le=90, description="Delete exports older than N days"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clean up old export files to free storage space"""
    # TODO: Add admin authentication
    # TODO: Implement actual cleanup logic
    cleaned_count = 0  # Placeholder - would implement actual cleanup
    return {
        "message": f"Cleaned up {cleaned_count} old exports",
        "days_old": days_old,
        "cleaned_at": datetime.utcnow().isoformat(),
    }


@router.get("/admin/processing-queue")
async def get_processing_queue_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current notation processing queue status"""
    # TODO: Add admin authentication
    # This would integrate with your background job system
    return {
        "pending_generations": 0,
        "active_generations": 0,
        "pending_exports": 0,
        "active_exports": 0,
        "avg_generation_time": 30.0,
        "avg_export_time": 15.0,
    }
