from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.audio_processing.detection import DrumDetector, DrumPatternAnalyzer
from app.modules.audio_processing.separation import (
    AudioStemExporter,
    DrumSourceSeparator,
)
from app.modules.audio_processing.service import AudioProcessingService
from app.modules.jobs.service import JobService
from app.modules.media.repository import AudioFileRepository
from app.modules.users.models import User

router = APIRouter(prefix="/audio", tags=["audio-processing"])
audio_service = AudioProcessingService()
job_service = JobService()
drum_detector = DrumDetector()
pattern_analyzer = DrumPatternAnalyzer()
source_separator = DrumSourceSeparator()
stem_exporter = AudioStemExporter()
audio_repository = AudioFileRepository()


@router.post("/extract/{video_id}")
async def extract_audio_from_video(
    video_id: UUID,
    sample_rate: int = Query(
        44100, ge=8000, le=192000, description="Audio sample rate in Hz"
    ),
    channels: int = Query(
        1, ge=1, le=2, description="Number of audio channels (1=mono, 2=stereo)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extract audio from a video file

    This creates a background job to extract audio from the specified video.
    The process uses FFmpeg to convert video to high-quality WAV audio.

    - **video_id**: UUID of the video to process
    - **sample_rate**: Target sample rate (default: 44100 Hz, recommended for drum analysis)
    - **channels**: Number of channels (default: 1 for mono, recommended for drum detection)
    """
    # Create audio extraction job
    job = await job_service.create_audio_extraction_job(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )

    return {
        "message": "Audio extraction job created successfully",
        "job_id": str(job.id),
        "video_id": str(video_id),
        "status": job.status,
        "estimated_duration": "2-5 minutes",
        "settings": {"sample_rate": sample_rate, "channels": channels, "format": "wav"},
    }


@router.get("/extract/{video_id}/status")
async def get_audio_extraction_status(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of audio extraction for a video

    Returns detailed information about the audio extraction process,
    including progress, completion status, and any errors.

    - **video_id**: UUID of the video being processed
    """
    # Get the latest audio extraction job for this video
    job = await job_service.get_job_by_video_and_type(db, video_id, "audio_extraction")

    if not job:
        raise HTTPException(
            status_code=404, detail="No audio extraction job found for this video"
        )

    # Get detailed job status
    job_status = await job_service.get_job_status(
        db, UUID(str(job.id)), UUID(str(current_user.id))
    )

    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "video_id": str(video_id),
        "extraction_status": job_status,
        "audio_available": job_status["status"] == "completed",
        "next_steps": _get_next_steps(job_status["status"]),
    }


@router.get("/info/{video_id}")
async def get_audio_info(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get information about extracted audio file

    Returns detailed metadata about the audio file extracted from the video,
    including duration, sample rate, file size, and audio features.

    - **video_id**: UUID of the video with extracted audio
    """
    from app.modules.media.repository import AudioFileRepository

    audio_repo = AudioFileRepository()
    audio_files = await audio_repo.get_by_video_id(db, video_id)

    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]  # Get the first/primary audio file

    # Get detailed audio information
    try:
        audio_info = await audio_service.get_audio_info(str(audio_file.storage_path))

        return {
            "video_id": str(video_id),
            "audio_file_id": str(audio_file.id),
            "basic_info": {
                "duration_seconds": audio_file.duration_seconds,
                "sample_rate": audio_file.sample_rate,
                "channels": audio_file.channels,
                "created_at": audio_file.created_at.isoformat(),
            },
            "detailed_info": audio_info,
            "storage_path": str(audio_file.storage_path),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get audio information: {str(e)}"
        )


@router.get("/features/{video_id}")
async def get_audio_features(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extract audio features for analysis

    Analyzes the extracted audio and returns features useful for drum detection
    and music analysis, including tempo, spectral features, and energy patterns.

    - **video_id**: UUID of the video with extracted audio
    """
    from app.modules.media.repository import AudioFileRepository

    audio_repo = AudioFileRepository()
    audio_files = await audio_repo.get_by_video_id(db, video_id)

    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]

    try:
        # Extract audio features
        features = await audio_service.get_audio_features(str(audio_file.storage_path))

        if not features:
            raise HTTPException(
                status_code=500, detail="Failed to extract audio features"
            )

        return {
            "video_id": str(video_id),
            "audio_file_id": str(audio_file.id),
            "features": features,
            "analysis_timestamp": _get_current_timestamp(),
            "recommended_for_drums": _evaluate_drum_suitability(features),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to extract audio features: {str(e)}"
        )


@router.post("/analyze/{video_id}")
async def start_audio_analysis(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start comprehensive audio analysis

    Creates a background job to perform detailed audio analysis including
    tempo detection, beat tracking, and spectral analysis preparation
    for drum detection.

    - **video_id**: UUID of the video to analyze
    """
    # Create audio analysis job
    job = await job_service.create_audio_analysis_job(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )

    return {
        "message": "Audio analysis job created successfully",
        "job_id": str(job.id),
        "video_id": str(video_id),
        "status": job.status,
        "estimated_duration": "3-7 minutes",
        "analysis_includes": [
            "Tempo detection",
            "Beat tracking",
            "Spectral analysis",
            "Energy pattern analysis",
            "Onset detection preparation",
        ],
    }


@router.post("/detect-drums/{video_id}")
async def start_drum_detection(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start drum detection analysis

    Creates a background job to detect drum events in the extracted audio.
    This uses machine learning models to identify drum hits, classify
    instruments, and determine timing and velocity.

    - **video_id**: UUID of the video to process
    """
    # Create drum detection job
    job = await job_service.create_drum_detection_job(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )

    return {
        "message": "Drum detection job created successfully",
        "job_id": str(job.id),
        "video_id": str(video_id),
        "status": job.status,
        "estimated_duration": "5-15 minutes",
        "detection_includes": [
            "Kick drum detection",
            "Snare drum detection",
            "Hi-hat detection",
            "Crash cymbal detection",
            "Tom-tom detection",
            "Velocity estimation",
            "Timing precision",
        ],
    }


@router.get("/pipeline/{video_id}")
async def get_processing_pipeline_status(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete processing pipeline status

    Returns the status of all audio processing stages for a video,
    including audio extraction, analysis, and drum detection progress.

    - **video_id**: UUID of the video to check
    """
    pipeline_status = await job_service.get_processing_pipeline_status(
        db, video_id, UUID(str(current_user.id))
    )

    return pipeline_status


@router.get("/jobs/my-jobs")
async def get_my_audio_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(20, ge=1, le=100, description="Number of jobs to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's audio processing jobs

    Returns a list of all audio processing jobs belonging to the current user,
    with optional filtering by status and job type.
    """
    jobs = await job_service.get_jobs_by_user(
        db=db,
        user_id=UUID(str(current_user.id)),
        status=status,
        job_type=job_type,
        limit=limit,
    )

    job_list = []
    for job in jobs:
        job_status = await job_service.get_job_status(db, UUID(str(job.id)))
        if job_status:
            job_list.append(job_status)

    return {
        "jobs": job_list,
        "total": len(job_list),
        "filters": {"status": status, "job_type": job_type, "limit": limit},
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_audio_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a running audio processing job

    Cancels a pending or running job. Completed jobs cannot be cancelled.

    - **job_id**: UUID of the job to cancel
    """
    success = await job_service.cancel_job(db, job_id, UUID(str(current_user.id)))

    if success:
        return {"message": "Job cancelled successfully", "job_id": str(job_id)}
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.post("/jobs/{job_id}/retry")
async def retry_audio_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retry a failed audio processing job

    Resets a failed job back to pending status so it can be processed again.
    Only failed jobs can be retried.

    - **job_id**: UUID of the job to retry
    """
    job = await job_service.retry_job(db, job_id, UUID(str(current_user.id)))

    return {
        "message": "Job reset for retry successfully",
        "job_id": str(job_id),
        "status": job.status,
    }


@router.get("/settings/recommended")
async def get_recommended_settings():
    """
    Get recommended audio processing settings

    Returns the recommended settings for audio extraction and processing
    optimized for drum detection and analysis.
    """
    return audio_service.get_recommended_settings()


@router.get("/settings/supported-formats")
async def get_supported_audio_formats():
    """
    Get supported audio formats

    Returns information about supported audio formats for processing
    and their characteristics.
    """
    return audio_service.get_supported_audio_formats()


@router.post("/admin/cleanup-temp")
async def cleanup_temp_files(
    current_user: User = Depends(get_current_user),
):
    """
    Clean up temporary audio processing files

    Removes temporary files created during audio processing.
    This endpoint should be restricted to admin users in production.
    """
    # Note: Add admin role check here in production
    cleaned_count = await audio_service.cleanup_temp_files()

    return {
        "message": f"Cleaned up {cleaned_count} temporary files",
        "cleaned_count": cleaned_count,
    }


@router.get("/admin/statistics")
async def get_audio_processing_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get audio processing statistics

    Returns system-wide statistics about audio processing jobs and performance.
    This endpoint should be restricted to admin users in production.
    """
    # Note: Add admin role check here in production
    stats = await job_service.get_job_statistics(db)

    return {
        "job_statistics": stats,
        "audio_service_info": {
            "temp_directory": str(audio_service.temp_dir),
            "supported_formats": len(audio_service.get_supported_audio_formats()),
            "recommended_settings": audio_service.get_recommended_settings(),
        },
    }


# Helper functions
def _get_next_steps(status: str) -> List[str]:
    """Get suggested next steps based on current job status"""
    if status == "completed":
        return ["Start audio analysis", "Begin drum detection", "View audio features"]
    elif status == "failed":
        return [
            "Check error message",
            "Retry extraction",
            "Contact support if issue persists",
        ]
    elif status in ["pending", "running"]:
        return [
            "Wait for processing to complete",
            "Check status again in a few minutes",
        ]
    else:
        return ["Extract audio from video"]


def _get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    from datetime import datetime

    return datetime.utcnow().isoformat()


@router.post("/detect-drums-advanced/{video_id}")
async def detect_drums_advanced(
    video_id: UUID,
    save_events: bool = Query(True, description="Save detected events to database"),
    confidence_threshold: float = Query(
        0.6, ge=0.0, le=1.0, description="Minimum confidence threshold"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Advanced drum detection using machine learning algorithms

    Performs sophisticated drum detection including:
    - Multi-algorithm onset detection
    - Frequency-based drum classification
    - Velocity and timing analysis
    - Pattern recognition

    - **video_id**: UUID of the video with extracted audio
    - **save_events**: Whether to save detected events to database
    - **confidence_threshold**: Minimum confidence for event detection
    """
    # Get audio file
    audio_files = await audio_repository.get_by_video_id(db, video_id)
    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]

    try:
        # Configure detector
        drum_detector.config.classification_threshold = confidence_threshold

        # Detect drum events
        drum_events = await drum_detector.detect_drums_from_audio_file(
            db, audio_file, save_events=save_events
        )

        # Get tempo and meter information
        import librosa

        y, sr = librosa.load(str(audio_file.storage_path), sr=44100)
        tempo_info = await drum_detector.detect_tempo_and_meter(y, int(sr))

        # Analyze patterns
        pattern_analysis = await pattern_analyzer.analyze_patterns(
            drum_events, tempo_info
        )

        # Calculate statistics
        stats = await drum_detector.get_drum_statistics(drum_events)

        return {
            "video_id": str(video_id),
            "audio_file_id": str(audio_file.id),
            "detection_results": {
                "total_events": len(drum_events),
                "events": [event.to_dict() for event in drum_events],
                "confidence_threshold": confidence_threshold,
                "saved_to_database": save_events,
            },
            "tempo_analysis": tempo_info,
            "pattern_analysis": pattern_analysis,
            "statistics": stats,
            "processing_info": {
                "algorithm": "multi-algorithm onset detection with ML classification",
                "processed_at": _get_current_timestamp(),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Advanced drum detection failed: {str(e)}"
        )


@router.post("/separate-sources/{video_id}")
async def separate_audio_sources(
    video_id: UUID,
    method: str = Query(
        "spectral", description="Separation method: 'nmf', 'ica', 'spectral'"
    ),
    save_sources: bool = Query(True, description="Save separated sources to disk"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Separate drum sources from mixed audio

    Uses advanced source separation algorithms to isolate:
    - Kick drum
    - Snare drum
    - Hi-hats
    - Cymbals
    - Toms
    - Other percussion

    - **video_id**: UUID of the video with extracted audio
    - **method**: Separation algorithm ('nmf', 'ica', 'spectral')
    - **save_sources**: Whether to save separated sources to disk
    """
    if method not in ["nmf", "ica", "spectral"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid separation method. Choose from: 'nmf', 'ica', 'spectral'",
        )

    # Get audio file
    audio_files = await audio_repository.get_by_video_id(db, video_id)
    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]

    try:
        # Separate sources
        separated_paths = await source_separator.separate_drum_sources(
            db, audio_file, method=method, save_separated=save_sources
        )

        # Calculate quality metrics if sources were separated
        if separated_paths:
            try:
                import librosa

                y_original, sr = librosa.load(str(audio_file.storage_path), sr=None)
                separated_audio = {}

                for source_name, path in separated_paths.items():
                    y_separated, _ = librosa.load(path, sr=sr)
                    separated_audio[source_name] = y_separated

                quality_metrics = await source_separator.get_separation_quality_metrics(
                    y_original, separated_audio
                )
            except Exception as e:
                quality_metrics = {
                    "error": f"Quality metrics calculation failed: {str(e)}"
                }
        else:
            quality_metrics = {}

        return {
            "video_id": str(video_id),
            "audio_file_id": str(audio_file.id),
            "separation_results": {
                "method": method,
                "separated_sources": list(separated_paths.keys()),
                "source_paths": separated_paths if save_sources else {},
                "sources_saved": save_sources,
            },
            "quality_metrics": quality_metrics,
            "processing_info": {
                "algorithm": f"{method.upper()} source separation",
                "processed_at": _get_current_timestamp(),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Source separation failed: {str(e)}"
        )


@router.post("/create-stems/{video_id}")
async def create_drum_stems(
    video_id: UUID,
    export_format: str = Query(
        "wav", description="Export format: 'wav', 'flac', 'aiff'"
    ),
    bit_depth: int = Query(24, description="Bit depth: 16, 24, or 32"),
    normalize: bool = Query(True, description="Normalize stem levels"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create professional drum stems for DAW import

    Creates separated drum stems suitable for use in Digital Audio Workstations:
    - Kick stem
    - Snare stem
    - Hi-hat stem
    - Cymbals stem
    - Toms stem
    - Percussion stem

    - **video_id**: UUID of the video with extracted audio
    - **export_format**: Audio format for export
    - **bit_depth**: Bit depth for professional quality
    - **normalize**: Whether to normalize stem levels
    """
    if export_format not in ["wav", "flac", "aiff"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid export format. Choose from: 'wav', 'flac', 'aiff'",
        )

    if bit_depth not in [16, 24, 32]:
        raise HTTPException(
            status_code=400, detail="Invalid bit depth. Choose from: 16, 24, 32"
        )

    # Get audio file
    audio_files = await audio_repository.get_by_video_id(db, video_id)
    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]

    try:
        # Create stems
        stem_paths = await stem_exporter.create_drum_stems(
            db, audio_file, export_format, bit_depth, normalize
        )

        # Calculate total file size
        total_size = 0
        for path in stem_paths.values():
            try:
                from pathlib import Path

                total_size += Path(path).stat().st_size
            except Exception:
                pass

        return {
            "video_id": str(video_id),
            "audio_file_id": str(audio_file.id),
            "stem_export": {
                "stems_created": list(stem_paths.keys()),
                "stem_paths": stem_paths,
                "export_format": export_format,
                "bit_depth": bit_depth,
                "normalized": normalize,
                "total_size_bytes": total_size,
            },
            "daw_import_info": {
                "recommended_tempo": "Detect tempo first using /features endpoint",
                "stem_organization": "Each stem contains related drum elements",
                "usage_note": "Import stems as separate tracks in your DAW",
            },
            "processing_info": {
                "processed_at": _get_current_timestamp(),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stem creation failed: {str(e)}")


@router.post("/enhance-drums/{video_id}")
async def enhance_drum_audio(
    video_id: UUID,
    drum_type: str = Query(
        "all", description="Drum type to enhance: 'kick', 'snare', 'hihat', 'all'"
    ),
    enhancement_strength: float = Query(
        0.3, ge=0.0, le=1.0, description="Enhancement strength"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enhance specific drum elements in the audio

    Applies frequency-specific enhancement to improve drum clarity:
    - Kick drum: Low-frequency boost and compression
    - Snare drum: Mid-frequency emphasis and transient enhancement
    - Hi-hat: High-frequency clarity and presence
    - All: Multi-band enhancement for overall improvement

    - **video_id**: UUID of the video with extracted audio
    - **drum_type**: Type of drums to enhance
    - **enhancement_strength**: Strength of enhancement effect
    """
    if drum_type not in ["kick", "snare", "hihat", "all"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid drum type. Choose from: 'kick', 'snare', 'hihat', 'all'",
        )

    # Get audio file
    audio_files = await audio_repository.get_by_video_id(db, video_id)
    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]

    try:
        # Enhance audio
        enhanced_audio = await source_separator.enhance_drum_track(
            str(audio_file.storage_path), drum_type
        )

        # Save enhanced version
        from pathlib import Path

        import soundfile as sf

        enhanced_dir = Path("uploads") / "enhanced" / str(audio_file.id)
        enhanced_dir.mkdir(parents=True, exist_ok=True)
        enhanced_path = enhanced_dir / f"enhanced_{drum_type}.wav"

        if len(enhanced_audio) > 0:
            # Apply enhancement strength
            import librosa

            y_original, sr = librosa.load(str(audio_file.storage_path), sr=None)

            # Mix enhanced with original based on strength
            min_length = min(len(y_original), len(enhanced_audio))
            mixed_audio = (1 - enhancement_strength) * y_original[
                :min_length
            ] + enhancement_strength * enhanced_audio[:min_length]

            # Save enhanced audio
            sf.write(str(enhanced_path), mixed_audio, sr, subtype="PCM_24")

            return {
                "video_id": str(video_id),
                "audio_file_id": str(audio_file.id),
                "enhancement_results": {
                    "drum_type": drum_type,
                    "enhancement_strength": enhancement_strength,
                    "enhanced_file_path": str(enhanced_path),
                    "original_length": len(y_original),
                    "enhanced_length": len(mixed_audio),
                },
                "processing_info": {
                    "algorithm": f"{drum_type} frequency enhancement",
                    "processed_at": _get_current_timestamp(),
                },
            }
        else:
            raise HTTPException(
                status_code=500, detail="Enhancement failed - no audio output generated"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Audio enhancement failed: {str(e)}"
        )


@router.get("/analysis/comprehensive/{video_id}")
async def get_comprehensive_analysis(
    video_id: UUID,
    include_detection: bool = Query(
        True, description="Include drum detection analysis"
    ),
    include_separation: bool = Query(
        False, description="Include source separation analysis"
    ),
    include_patterns: bool = Query(True, description="Include pattern analysis"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive audio analysis combining multiple techniques

    Provides a complete analysis including:
    - Basic audio features and characteristics
    - Drum detection and classification
    - Rhythmic pattern analysis
    - Tempo and meter detection
    - Optional source separation analysis

    - **video_id**: UUID of the video to analyze
    - **include_detection**: Whether to include drum detection
    - **include_separation**: Whether to include separation analysis
    - **include_patterns**: Whether to include pattern analysis
    """
    # Get audio file
    audio_files = await audio_repository.get_by_video_id(db, video_id)
    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="No audio file found for this video. Please extract audio first.",
        )

    audio_file = audio_files[0]

    try:
        import librosa

        # Load audio
        y, sr = librosa.load(str(audio_file.storage_path), sr=44100)

        analysis_results = {
            "video_id": str(video_id),
            "audio_file_id": str(audio_file.id),
            "basic_info": {
                "duration_seconds": len(y) / sr,
                "sample_rate": sr,
                "channels": 1 if y.ndim == 1 else y.shape[0],
            },
        }

        # Basic audio features
        audio_features = await audio_service.get_audio_features(
            str(audio_file.storage_path)
        )
        analysis_results["audio_features"] = audio_features

        # Tempo and meter analysis
        tempo_info = await drum_detector.detect_tempo_and_meter(y, int(sr))
        analysis_results["tempo_analysis"] = tempo_info

        # Drum detection analysis
        if include_detection:
            drum_events = await drum_detector.detect_drums_from_audio_file(
                db, audio_file, save_events=False
            )

            detection_stats = await drum_detector.get_drum_statistics(drum_events)

            analysis_results["drum_detection"] = {
                "total_events": len(drum_events),
                "statistics": detection_stats,
                "events_sample": [
                    event.to_dict() for event in drum_events[:10]
                ],  # First 10 events
            }

            # Pattern analysis
            if include_patterns:
                pattern_analysis = await pattern_analyzer.analyze_patterns(
                    drum_events, tempo_info
                )
                analysis_results["pattern_analysis"] = pattern_analysis

        # Source separation analysis
        if include_separation:
            try:
                separated_sources = await source_separator.separate_drum_sources(
                    db, audio_file, method="spectral", save_separated=False
                )

                # Calculate separation quality
                separated_audio = {}
                for source_name, audio_data in separated_sources.items():
                    if len(audio_data) > 0:
                        separated_audio[source_name] = audio_data

                if separated_audio:
                    quality_metrics = (
                        await source_separator.get_separation_quality_metrics(
                            y, separated_audio
                        )
                    )

                    analysis_results["source_separation"] = {
                        "separated_sources": list(separated_audio.keys()),
                        "quality_metrics": quality_metrics,
                        "method": "spectral",
                    }
            except Exception as e:
                analysis_results["source_separation"] = {
                    "error": f"Separation analysis failed: {str(e)}"
                }

        # Overall assessment
        suitability = _evaluate_drum_suitability(audio_features)
        analysis_results["drum_suitability"] = suitability

        # Processing summary
        analysis_results["processing_info"] = {
            "analysis_components": {
                "basic_features": True,
                "tempo_detection": True,
                "drum_detection": include_detection,
                "pattern_analysis": include_patterns and include_detection,
                "source_separation": include_separation,
            },
            "processed_at": _get_current_timestamp(),
        }

        return analysis_results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Comprehensive analysis failed: {str(e)}"
        )


def _evaluate_drum_suitability(features: dict) -> dict:
    """Evaluate how suitable the audio is for drum detection"""
    if not features:
        return {"suitable": False, "reason": "No features available"}

    # Simple heuristics for drum suitability
    tempo = features.get("tempo", 0)
    rms_energy = features.get("rms_energy", 0)

    suitable = True
    issues = []
    suggestions = []

    if tempo < 60 or tempo > 200:
        suitable = False
        issues.append(f"Unusual tempo: {tempo} BPM")
        suggestions.append("Verify this is a drum performance recording")

    if rms_energy < 0.01:
        suitable = False
        issues.append("Very low audio energy")
        suggestions.append("Check audio levels and recording quality")

    if suitable:
        suggestions.append("Audio appears suitable for drum detection")

    return {
        "suitable": suitable,
        "confidence": 0.8 if suitable else 0.3,
        "issues": issues,
        "suggestions": suggestions,
        "tempo_bpm": tempo,
        "energy_level": "high"
        if rms_energy > 0.1
        else "medium"
        if rms_energy > 0.01
        else "low",
    }
