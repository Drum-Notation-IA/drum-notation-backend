import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal  # type: ignore[attr-defined]
from app.modules.audio_processing.service import AudioProcessingService
from app.modules.jobs.models import ProcessingJob
from app.modules.media.repository import VideoRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobProcessor:
    """Background job processor for handling audio extraction and other async tasks"""

    def __init__(self):
        self.audio_service = AudioProcessingService()
        self.video_repository = VideoRepository()
        self.is_running = False
        self.poll_interval = 5  # seconds
        self.max_retries = 3
        self.job_timeout = 300  # 5 minutes

    async def start(self):
        """Start the job processor"""
        if self.is_running:
            logger.warning("Job processor is already running")
            return

        self.is_running = True
        logger.info("Starting job processor...")

        try:
            while self.is_running:
                await self.process_pending_jobs()
                await asyncio.sleep(self.poll_interval)
        except Exception as e:
            logger.error(f"Job processor crashed: {e}")
            self.is_running = False
            raise

    async def stop(self):
        """Stop the job processor"""
        logger.info("Stopping job processor...")
        self.is_running = False

    async def process_pending_jobs(self):
        """Process all pending jobs in the queue"""
        async with AsyncSessionLocal() as db:  # type: ignore[attr-defined]
            try:
                # Get pending jobs
                pending_jobs = await self._get_pending_jobs(db)

                if not pending_jobs:
                    return

                logger.info(f"Processing {len(pending_jobs)} pending job(s)")

                for job in pending_jobs:
                    try:
                        await self._process_job(db, job)
                    except Exception as e:
                        logger.error(f"Failed to process job {job.id}: {e}")
                        await self._handle_job_error(db, job, str(e))

            except Exception as e:
                logger.error(f"Error processing jobs: {e}")

    async def _get_pending_jobs(self, db: AsyncSession) -> list[ProcessingJob]:
        """Get all pending jobs from the database"""
        query = (
            select(ProcessingJob)
            .where(
                (ProcessingJob.status == "pending")
                & (ProcessingJob.deleted_at.is_(None))
            )
            .order_by(ProcessingJob.created_at)
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    async def _process_job(self, db: AsyncSession, job: ProcessingJob):
        """Process a single job"""
        logger.info(f"Processing job {job.id} ({job.job_type})")

        # Mark job as running
        await self._update_job_status(
            db, UUID(str(job.id)), "running", started_at=datetime.utcnow()
        )

        try:
            # Route to appropriate processor based on job type
            job_type = str(job.job_type)
            if job_type == "audio_extraction":
                await self._process_audio_extraction(db, job)
            elif job_type == "audio_analysis":
                await self._process_audio_analysis(db, job)
            elif job_type == "drum_detection":
                await self._process_drum_detection(db, job)
            else:
                raise ValueError(f"Unknown job type: {job_type}")

            # Mark job as completed
            await self._update_job_status(
                db,
                UUID(str(job.id)),
                "completed",
                finished_at=datetime.utcnow(),
                progress=100.0,
            )

            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            await self._handle_job_error(db, job, str(e))
            raise

    async def _process_audio_extraction(self, db: AsyncSession, job: ProcessingJob):
        """Process audio extraction job"""
        try:
            job_id = UUID(str(job.id))
            video_id = UUID(str(job.video_id))

            # Update progress
            await self._update_job_progress(db, job_id, 10.0)

            # Get video information
            video = await self.video_repository.get_by_id(db, video_id)
            if not video:
                raise ValueError(f"Video {video_id} not found")

            await self._update_job_progress(db, job_id, 20.0)

            # Extract audio
            audio_file = await self.audio_service.extract_audio_from_video(
                db=db,
                video_id=video_id,
                user_id=UUID(str(video.user_id)),
                sample_rate=44100,
                channels=1,
            )

            await self._update_job_progress(db, job_id, 80.0)

            # Validate extracted audio
            is_valid = await self.audio_service.validate_audio_file(
                str(audio_file.storage_path)
            )
            if not is_valid:
                raise ValueError("Extracted audio file failed validation")

            await self._update_job_progress(db, job_id, 100.0)

            logger.info(f"Audio extraction completed for video {video_id}")

        except Exception as e:
            logger.error(f"Audio extraction failed for job {job.id}: {e}")
            raise

    async def _process_audio_analysis(self, db: AsyncSession, job: ProcessingJob):
        """Process audio analysis job (placeholder for future implementation)"""
        job_id = UUID(str(job.id))

        await self._update_job_progress(db, job_id, 25.0)

        # TODO: Implement audio feature extraction
        await asyncio.sleep(1)  # Simulate processing
        await self._update_job_progress(db, job_id, 50.0)

        # TODO: Implement tempo detection
        await asyncio.sleep(1)  # Simulate processing
        await self._update_job_progress(db, job_id, 75.0)

        # TODO: Implement beat tracking
        await asyncio.sleep(1)  # Simulate processing
        await self._update_job_progress(db, job_id, 100.0)

        logger.info(f"Audio analysis completed for job {job_id}")

    async def _process_drum_detection(self, db: AsyncSession, job: ProcessingJob):
        """Process drum detection job (placeholder for future ML integration)"""
        job_id = UUID(str(job.id))

        await self._update_job_progress(db, job_id, 20.0)

        # TODO: Load audio file
        await asyncio.sleep(1)  # Simulate processing
        await self._update_job_progress(db, job_id, 40.0)

        # TODO: Run drum detection model
        await asyncio.sleep(2)  # Simulate ML processing
        await self._update_job_progress(db, job_id, 80.0)

        # TODO: Save drum events to database
        await asyncio.sleep(1)  # Simulate saving
        await self._update_job_progress(db, job_id, 100.0)

        logger.info(f"Drum detection completed for job {job_id}")

    async def _update_job_status(
        self,
        db: AsyncSession,
        job_id: UUID,
        status: str,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        progress: Optional[float] = None,
    ):
        """Update job status in database"""
        from typing import Any, Dict

        update_data: Dict[str, Any] = {"status": status}

        if started_at:
            update_data["started_at"] = started_at
        if finished_at:
            update_data["finished_at"] = finished_at
        if progress is not None:
            update_data["progress"] = progress

        query = (
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(**update_data)
        )

        await db.execute(query)
        await db.commit()

    async def _update_job_progress(
        self, db: AsyncSession, job_id: UUID, progress: float
    ):
        """Update job progress"""
        await self._update_job_status(db, job_id, "running", progress=progress)

    async def _handle_job_error(
        self, db: AsyncSession, job: ProcessingJob, error_message: str
    ):
        """Handle job errors and implement retry logic"""
        try:
            job_id = UUID(str(job.id))

            # Count current retries (you might want to add a retry_count field to the model)
            current_retries = 0  # TODO: Track this in the database

            if current_retries < self.max_retries:
                # Retry the job
                logger.info(f"Retrying job {job_id} (attempt {current_retries + 1})")
                await self._update_job_status(db, job_id, "pending", progress=0.0)
            else:
                # Mark as failed
                logger.error(f"Job {job_id} failed after {self.max_retries} retries")
                await self._update_job_status(
                    db, job_id, "failed", finished_at=datetime.utcnow()
                )

                # Update error message
                query = (
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(error_message=error_message)
                )

                await db.execute(query)
                await db.commit()

        except Exception as e:
            logger.error(f"Error handling job error for {job.id}: {e}")

    async def create_job(
        self, db: AsyncSession, video_id: UUID, job_type: str, priority: int = 0
    ) -> ProcessingJob:
        """Create a new processing job"""
        job = ProcessingJob(
            video_id=video_id, job_type=job_type, status="pending", progress=0.0
        )

        db.add(job)
        await db.flush()
        await db.refresh(job)
        await db.commit()

        logger.info(f"Created new job: {job.id} ({job_type}) for video {video_id}")
        return job

    async def initialize(self):
        """Initialize the job processor"""
        logger.info("Job processor initialized")

    async def cleanup(self):
        """Cleanup resources"""
        self.is_running = False
        logger.info("Job processor cleaned up")

    async def get_job_status(
        self, db: AsyncSession, job_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get the status of a specific job"""
        query = select(ProcessingJob).where(
            ProcessingJob.id == job_id, ProcessingJob.deleted_at.is_(None)
        )

        result = await db.execute(query)
        job = result.scalar_one_or_none()

        if not job:
            return None

        return {
            "id": str(job.id),
            "video_id": str(job.video_id),
            "job_type": str(job.job_type),
            "status": str(job.status),
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
        }

    async def cancel_job(self, db: AsyncSession, job_id: UUID) -> bool:
        """Cancel a pending or running job"""
        # Try to cancel pending job first
        query = (
            update(ProcessingJob)
            .where((ProcessingJob.id == job_id) & (ProcessingJob.status == "pending"))
            .values(status="failed", finished_at=datetime.utcnow())
        )

        result = await db.execute(query)

        # If no pending job found, try running job
        if getattr(result, "rowcount", 0) == 0:
            query = (
                update(ProcessingJob)
                .where(
                    (ProcessingJob.id == job_id) & (ProcessingJob.status == "running")
                )
                .values(status="failed", finished_at=datetime.utcnow())
            )
            result = await db.execute(query)

        await db.commit()

        affected_rows = getattr(result, "rowcount", 0) or 0
        if affected_rows > 0:
            logger.info(f"Cancelled job {job_id}")
            return True
        else:
            logger.warning(
                f"Could not cancel job {job_id} (not found or not cancellable)"
            )
            return False

    async def cleanup_old_jobs(self, db: AsyncSession, days_old: int = 30) -> int:
        """Clean up old completed/failed jobs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Clean up completed jobs
        query = (
            update(ProcessingJob)
            .where(
                (ProcessingJob.status == "completed")
                & (ProcessingJob.deleted_at.is_(None))
                & (ProcessingJob.finished_at < cutoff_date)
            )
            .values(deleted_at=datetime.utcnow())
        )

        result1 = await db.execute(query)

        # Clean up failed jobs
        query = (
            update(ProcessingJob)
            .where(
                (ProcessingJob.status == "failed")
                & (ProcessingJob.deleted_at.is_(None))
                & (ProcessingJob.finished_at < cutoff_date)
            )
            .values(deleted_at=datetime.utcnow())
        )

        result2 = await db.execute(query)

        await db.commit()

        cleaned_count = (getattr(result1, "rowcount", 0) or 0) + (
            getattr(result2, "rowcount", 0) or 0
        )
        logger.info(f"Cleaned up {cleaned_count} old jobs")

        return cleaned_count

    async def get_job_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """Get job processing statistics"""

        # Get job counts by status
        query = (
            select(ProcessingJob.status, func.count(ProcessingJob.id).label("count"))  # type: ignore[arg-type]
            .where(ProcessingJob.deleted_at.is_(None))
            .group_by(ProcessingJob.status)
        )

        result = await db.execute(query)
        status_counts = {str(row[0]): int(row[1]) for row in result}

        # Get job counts by type
        query = (
            select(ProcessingJob.job_type, func.count(ProcessingJob.id).label("count"))  # type: ignore[arg-type]
            .where(ProcessingJob.deleted_at.is_(None))
            .group_by(ProcessingJob.job_type)
        )

        result = await db.execute(query)
        type_counts = {str(row[0]): int(row[1]) for row in result}

        return {
            "status_counts": status_counts,
            "type_counts": type_counts,
            "processor_running": self.is_running,
            "poll_interval": self.poll_interval,
            "max_retries": self.max_retries,
            "job_timeout": self.job_timeout,
        }


# Global job processor instance
job_processor = JobProcessor()


async def start_job_processor():
    """Start the background job processor"""
    await job_processor.initialize()
    # Start in background task, not blocking
    asyncio.create_task(job_processor.start())


async def stop_job_processor():
    """Stop the background job processor"""
    await job_processor.stop()
    await job_processor.cleanup()
