from datetime import datetime
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import ProcessingJob
from app.modules.jobs.worker import job_processor
from app.modules.media.repository import VideoRepository


class JobService:
    """Service for managing processing jobs"""

    def __init__(self):
        self.video_repository = VideoRepository()

    async def create_audio_extraction_job(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> ProcessingJob:
        """Create a new audio extraction job"""

        # Verify video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to process this video"
            )

        # Check if job already exists for this video
        existing_job = await self.get_job_by_video_and_type(
            db, video_id, "audio_extraction"
        )
        if existing_job and existing_job.status in ["pending", "running"]:
            raise HTTPException(
                status_code=400,
                detail="Audio extraction job already in progress for this video",
            )

        # Create the job
        job = await job_processor.create_job(
            db=db, video_id=video_id, job_type="audio_extraction"
        )

        return job

    async def create_audio_analysis_job(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> ProcessingJob:
        """Create a new audio analysis job"""

        # Verify video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to process this video"
            )

        # Check if audio extraction is complete
        audio_job = await self.get_job_by_video_and_type(
            db, video_id, "audio_extraction"
        )
        if not audio_job or str(audio_job.status) != "completed":
            raise HTTPException(
                status_code=400,
                detail="Audio must be extracted before analysis can begin",
            )

        # Create the job
        job = await job_processor.create_job(
            db=db, video_id=video_id, job_type="audio_analysis"
        )

        return job

    async def create_drum_detection_job(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> ProcessingJob:
        """Create a new drum detection job"""

        # Verify video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to process this video"
            )

        # Check if audio extraction is complete
        audio_job = await self.get_job_by_video_and_type(
            db, video_id, "audio_extraction"
        )
        if not audio_job or str(audio_job.status) != "completed":
            raise HTTPException(
                status_code=400,
                detail="Audio must be extracted before drum detection can begin",
            )

        # Create the job
        job = await job_processor.create_job(
            db=db, video_id=video_id, job_type="drum_detection"
        )

        return job

    async def get_job_by_id(
        self, db: AsyncSession, job_id: UUID, user_id: Optional[UUID] = None
    ) -> Optional[ProcessingJob]:
        """Get a job by ID with optional user authorization check"""

        query = select(ProcessingJob).where(
            ProcessingJob.id == job_id, ProcessingJob.deleted_at.is_(None)
        )

        result = await db.execute(query)
        job = result.scalar_one_or_none()

        if not job:
            return None

        # Check authorization if user_id provided
        if user_id:
            video = await self.video_repository.get_by_id(db, UUID(str(job.video_id)))
            if not video or str(video.user_id) != str(user_id):
                raise HTTPException(
                    status_code=403, detail="Not authorized to view this job"
                )

        return job

    async def get_job_by_video_and_type(
        self, db: AsyncSession, video_id: UUID, job_type: str
    ) -> Optional[ProcessingJob]:
        """Get the most recent job for a video and job type"""

        query = (
            select(ProcessingJob)
            .where(
                ProcessingJob.video_id == video_id,
                ProcessingJob.job_type == job_type,
                ProcessingJob.deleted_at.is_(None),
            )
            .order_by(ProcessingJob.created_at.desc())
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_jobs_by_video(
        self, db: AsyncSession, video_id: UUID, user_id: Optional[UUID] = None
    ) -> List[ProcessingJob]:
        """Get all jobs for a specific video"""

        # Check authorization if user_id provided
        if user_id:
            video = await self.video_repository.get_by_id(db, video_id)
            if not video or str(video.user_id) != str(user_id):
                raise HTTPException(
                    status_code=403, detail="Not authorized to view jobs for this video"
                )

        query = (
            select(ProcessingJob)
            .where(
                ProcessingJob.video_id == video_id, ProcessingJob.deleted_at.is_(None)
            )
            .order_by(ProcessingJob.created_at.desc())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_jobs_by_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[ProcessingJob]:
        """Get all jobs for a specific user with optional filters"""

        # First get all video IDs for the user
        videos = await self.video_repository.get_all(db, user_id=user_id, limit=1000)
        video_ids = [video.id for video in videos]

        if not video_ids:
            return []

        # Build complete WHERE clause with text() to avoid type issues
        where_conditions = ["video_id IN :video_ids", "deleted_at IS NULL"]

        if status:
            where_conditions.append(f"status = '{status}'")

        if job_type:
            where_conditions.append(f"job_type = '{job_type}'")

        where_clause = " AND ".join(where_conditions)
        query = (
            select(ProcessingJob)
            .where(text(where_clause))
            .params(video_ids=tuple(video_ids))
        )

        query = query.order_by(ProcessingJob.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def cancel_job(self, db: AsyncSession, job_id: UUID, user_id: UUID) -> bool:
        """Mark a job as failed (pseudo-cancel since we don't have cancelled status)"""

        # Verify job exists and user owns it
        job = await self.get_job_by_id(db, job_id, user_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check if job can be cancelled
        job_status = str(job.status)
        if job_status not in ["pending", "running"]:
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel job with status: {job_status}"
            )

        # Mark as failed with cancellation message
        query = (
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(
                status="failed",
                error_message="Job cancelled by user",
                finished_at=datetime.utcnow(),
            )
        )

        await db.execute(query)
        await db.commit()

        return True

    async def retry_job(
        self, db: AsyncSession, job_id: UUID, user_id: UUID
    ) -> ProcessingJob:
        """Retry a failed job"""

        # Verify job exists and user owns it
        job = await self.get_job_by_id(db, job_id, user_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check if job can be retried
        job_status = str(job.status)
        if job_status != "failed":
            raise HTTPException(
                status_code=400, detail=f"Cannot retry job with status: {job_status}"
            )

        # Reset job status to pending
        query = (
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(
                status="pending",
                progress=0.0,
                error_message=None,
                started_at=None,
                finished_at=None,
            )
        )

        await db.execute(query)
        await db.commit()

        # Get updated job
        return await self.get_job_by_id(db, job_id)

    async def get_job_status(
        self, db: AsyncSession, job_id: UUID, user_id: Optional[UUID] = None
    ) -> Optional[Dict]:
        """Get detailed job status information"""

        job = await self.get_job_by_id(db, job_id, user_id)
        if not job:
            return None

        job_status = str(job.status)
        return {
            "id": str(job.id),
            "video_id": str(job.video_id),
            "job_type": str(job.job_type),
            "status": job_status,
            "progress": float(cast(float, job.progress) or 0.0),
            "error_message": cast(Optional[str], job.error_message),
            "created_at": (
                cast(Any, job.created_at).isoformat()
                if cast(Any, job.created_at) is not None
                else None
            ),
            "started_at": (
                cast(Any, job.started_at).isoformat()
                if cast(Any, job.started_at) is not None
                else None
            ),
            "finished_at": (
                cast(Any, job.finished_at).isoformat()
                if cast(Any, job.finished_at) is not None
                else None
            ),
            "duration_seconds": self._calculate_duration(job),
            "can_cancel": job_status in ["pending", "running"],
            "can_retry": job_status == "failed",
        }

    def _calculate_duration(self, job: ProcessingJob) -> Optional[float]:
        """Calculate job duration in seconds"""
        started_at = cast(Optional[datetime], job.started_at)
        if not started_at:
            return None

        finished_at = cast(Optional[datetime], job.finished_at)
        end_time = finished_at or datetime.utcnow()
        duration = (end_time - started_at).total_seconds()
        return round(duration, 2)

    async def get_processing_pipeline_status(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> Dict:
        """Get the complete processing pipeline status for a video"""

        # Verify video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video or str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to view this video's status"
            )

        # Get all jobs for this video
        jobs = await self.get_jobs_by_video(db, video_id)

        # Organize jobs by type
        jobs_by_type = {}
        for job in jobs:
            if job.job_type not in jobs_by_type:
                jobs_by_type[job.job_type] = []
            jobs_by_type[job.job_type].append(job)

        # Get the latest job for each type
        pipeline_status = {
            "video_id": str(video_id),
            "video_filename": str(video.filename),
            "pipeline_stages": {
                "audio_extraction": self._get_stage_status(
                    jobs_by_type.get("audio_extraction", [])
                ),
                "audio_analysis": self._get_stage_status(
                    jobs_by_type.get("audio_analysis", [])
                ),
                "drum_detection": self._get_stage_status(
                    jobs_by_type.get("drum_detection", [])
                ),
            },
            "overall_progress": 0.0,
            "next_available_action": None,
        }

        # Calculate overall progress and next action
        stages = pipeline_status["pipeline_stages"]

        if stages["audio_extraction"]["status"] == "completed":
            pipeline_status["overall_progress"] += 33.3
            if stages["audio_analysis"]["status"] == "not_started":
                pipeline_status["next_available_action"] = "audio_analysis"

            if stages["audio_analysis"]["status"] == "completed":
                pipeline_status["overall_progress"] += 33.3
                if stages["drum_detection"]["status"] == "not_started":
                    pipeline_status["next_available_action"] = "drum_detection"

                if stages["drum_detection"]["status"] == "completed":
                    pipeline_status["overall_progress"] = 100.0
                    pipeline_status["next_available_action"] = "notation_generation"
        else:
            if stages["audio_extraction"]["status"] == "not_started":
                pipeline_status["next_available_action"] = "audio_extraction"

        return pipeline_status

    def _get_stage_status(self, jobs: List[ProcessingJob]) -> Dict:
        """Get status information for a pipeline stage"""
        if not jobs:
            return {
                "status": "not_started",
                "progress": 0.0,
                "latest_job_id": None,
                "error_message": None,
            }

        # Get the most recent job
        latest_job = max(jobs, key=lambda j: j.created_at)

        return {
            "status": str(latest_job.status),
            "progress": float(cast(float, latest_job.progress) or 0.0),
            "latest_job_id": str(latest_job.id),
            "error_message": cast(Optional[str], latest_job.error_message),
        }

    async def get_job_statistics(self, db: AsyncSession) -> Dict:
        """Get overall job processing statistics"""
        return await job_processor.get_job_statistics(db)

    async def cleanup_old_jobs(self, db: AsyncSession, days_old: int = 30) -> int:
        """Clean up old jobs"""
        return await job_processor.cleanup_old_jobs(db, days_old)
