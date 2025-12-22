from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.jobs.schemas import (
    JobCreate,
    JobRead,
    JobReadWithDetails,
    JobStatistics,
    JobUpdate,
    PipelineStatusResponse,
)
from app.modules.jobs.service import JobService
from app.modules.users.models import User

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Initialize service
job_service = JobService()


@router.post("/", response_model=JobRead)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new processing job"""
    user_id = UUID(str(getattr(current_user, "id")))

    if job_data.job_type == "audio_extraction":
        return await job_service.create_audio_extraction_job(
            db,
            job_data.video_id,
            user_id,
        )
    elif job_data.job_type == "audio_analysis":
        return await job_service.create_audio_analysis_job(
            db,
            job_data.video_id,
            user_id,
        )
    elif job_data.job_type == "drum_detection":
        return await job_service.create_drum_detection_job(
            db,
            job_data.video_id,
            user_id,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid job type")


@router.get("/", response_model=List[JobRead])
async def get_user_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by job status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(50, le=100, description="Maximum number of jobs to return"),
):
    """Get all jobs for the current user"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.get_jobs_by_user(
        db,
        user_id,
        status=status,
        job_type=job_type,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobReadWithDetails)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about a specific job"""
    user_id = UUID(str(getattr(current_user, "id")))

    job_status = await job_service.get_job_status(
        db,
        job_id,
        user_id,
    )
    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_status


@router.patch("/{job_id}", response_model=JobRead)
async def update_job(
    job_id: UUID,
    job_update: JobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a job (limited to certain fields)"""
    user_id = UUID(str(getattr(current_user, "id")))

    # For now, this is mainly used internally, but keeping it for future extensibility
    job = await job_service.get_job_by_id(db, job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Add any update logic here if needed
    return job


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retry a failed job"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.retry_job(db, job_id, user_id)


@router.delete("/{job_id}")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a running or pending job"""
    user_id = UUID(str(getattr(current_user, "id")))

    success = await job_service.cancel_job(db, job_id, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel job")
    return {"message": "Job cancelled successfully"}


@router.get("/video/{video_id}", response_model=List[JobRead])
async def get_jobs_by_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all jobs for a specific video"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.get_jobs_by_video(db, video_id, user_id)


@router.get("/video/{video_id}/pipeline", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the complete processing pipeline status for a video"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.get_processing_pipeline_status(
        db,
        video_id,
        user_id,
    )


@router.get("/admin/statistics", response_model=JobStatistics)
async def get_job_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get job processing statistics (admin only)"""
    # TODO: Add admin role check
    # if not await is_admin(current_user):
    #     raise HTTPException(status_code=403, detail="Admin access required")
    return await job_service.get_job_statistics(db)


@router.post("/admin/cleanup")
async def cleanup_old_jobs(
    days_old: int = Query(
        30, ge=1, le=365, description="Delete jobs older than N days"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clean up old completed/failed jobs (admin only)"""
    # TODO: Add admin role check
    # if not await is_admin(current_user):
    #     raise HTTPException(status_code=403, detail="Admin access required")

    cleaned_count = await job_service.cleanup_old_jobs(db, days_old)
    return {"message": f"Cleaned up {cleaned_count} old jobs"}


# Job Type specific endpoints for easier access


@router.post("/audio-extraction/{video_id}", response_model=JobRead)
async def create_audio_extraction_job(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an audio extraction job for a video"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.create_audio_extraction_job(db, video_id, user_id)


@router.post("/audio-analysis/{video_id}", response_model=JobRead)
async def create_audio_analysis_job(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an audio analysis job for a video"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.create_audio_analysis_job(db, video_id, user_id)


@router.post("/drum-detection/{video_id}", response_model=JobRead)
async def create_drum_detection_job(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a drum detection job for a video"""
    user_id = UUID(str(getattr(current_user, "id")))

    return await job_service.create_drum_detection_job(db, video_id, user_id)


# Health and monitoring endpoints


@router.get("/health")
async def job_system_health():
    """Check if the job processing system is healthy"""
    # TODO: Implement actual health checks
    # - Check worker status
    # - Check job queue size
    # - Check database connection
    # - Check processing times

    return {
        "status": "healthy",
        "message": "Job processing system is operational",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/queue-status")
async def get_queue_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current job queue status"""
    # TODO: Implement queue status
    # - Pending jobs count by type
    # - Average processing time
    # - Worker status
    # - Estimated wait times

    return {
        "pending_jobs": {
            "audio_extraction": 0,
            "audio_analysis": 0,
            "drum_detection": 0,
        },
        "estimated_wait_time_minutes": 0,
        "workers_active": 1,
    }
