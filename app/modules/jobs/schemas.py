from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Base schemas
class JobBase(BaseModel):
    job_type: str = Field(
        ...,
        description="Type of job (audio_extraction, audio_analysis, drum_detection, etc.)",
    )


class JobCreate(JobBase):
    video_id: UUID = Field(..., description="ID of the video to process")


class JobUpdate(BaseModel):
    progress: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Job progress percentage"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if job failed"
    )


# Read schemas
class JobRead(JobBase):
    id: UUID
    video_id: UUID
    status: str = Field(
        ..., description="Job status: pending, running, completed, failed"
    )
    progress: float = Field(
        0.0, ge=0.0, le=100.0, description="Job progress percentage"
    )
    error_message: Optional[str] = None

    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class JobReadWithDetails(JobRead):
    duration_seconds: Optional[float] = Field(
        None, description="Job duration in seconds"
    )
    can_cancel: bool = Field(False, description="Whether the job can be cancelled")
    can_retry: bool = Field(False, description="Whether the job can be retried")

    # Add video information for context
    video_filename: Optional[str] = None


# Pipeline status schemas
class PipelineStageStatus(BaseModel):
    status: str = Field(
        ...,
        description="Stage status: not_started, pending, running, completed, failed",
    )
    progress: float = Field(
        0.0, ge=0.0, le=100.0, description="Stage progress percentage"
    )
    latest_job_id: Optional[UUID] = None
    error_message: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    video_id: UUID
    video_filename: str
    pipeline_stages: Dict[str, PipelineStageStatus] = Field(
        ..., description="Status of each pipeline stage"
    )
    overall_progress: float = Field(
        0.0, ge=0.0, le=100.0, description="Overall pipeline progress"
    )
    next_available_action: Optional[str] = Field(
        None, description="Next action that can be performed"
    )


# Statistics schemas
class JobStatistics(BaseModel):
    status_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of jobs by status"
    )
    type_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of jobs by type"
    )
    total_jobs: int = Field(0, description="Total number of jobs")

    # Performance metrics
    average_processing_time: Optional[float] = Field(
        None, description="Average job processing time in seconds"
    )
    success_rate: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Job success rate percentage"
    )

    # Queue metrics
    pending_jobs: int = Field(0, description="Number of pending jobs")
    running_jobs: int = Field(0, description="Number of running jobs")


# Job list responses
class JobListResponse(BaseModel):
    jobs: List[JobRead]
    total: int = Field(..., description="Total number of jobs (before pagination)")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(50, description="Number of jobs per page")
    pages: int = Field(1, description="Total number of pages")


# Queue status schemas
class QueueStatus(BaseModel):
    pending_jobs: Dict[str, int] = Field(
        default_factory=dict, description="Number of pending jobs by type"
    )
    estimated_wait_time_minutes: int = Field(
        0, description="Estimated wait time in minutes"
    )
    workers_active: int = Field(0, description="Number of active workers")
    processing_capacity: Optional[int] = Field(
        None, description="Maximum concurrent jobs"
    )


# Health check schemas
class JobSystemHealth(BaseModel):
    status: str = Field(
        ..., description="System health status: healthy, degraded, unhealthy"
    )
    message: str = Field(..., description="Health status message")
    timestamp: datetime = Field(..., description="Health check timestamp")

    # Detailed health metrics
    database_connected: bool = Field(True, description="Database connection status")
    worker_active: bool = Field(True, description="Worker process status")
    queue_size: int = Field(0, description="Current queue size")
    last_job_processed: Optional[datetime] = Field(
        None, description="Timestamp of last processed job"
    )


# Error response schemas
class JobError(BaseModel):
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict] = Field(None, description="Additional error details")
    job_id: Optional[UUID] = Field(None, description="Related job ID if applicable")


# Batch operation schemas
class BatchJobCreate(BaseModel):
    video_ids: List[UUID] = Field(..., description="List of video IDs to process")
    job_type: str = Field(..., description="Type of job to create for all videos")


class BatchJobResponse(BaseModel):
    created_jobs: List[JobRead] = Field(..., description="Successfully created jobs")
    failed_videos: List[Dict] = Field(
        default_factory=list, description="Videos that failed to create jobs"
    )
    total_created: int = Field(0, description="Number of jobs successfully created")
    total_failed: int = Field(0, description="Number of jobs that failed to create")


# Job progress update schema (for internal use)
class JobProgressUpdate(BaseModel):
    progress: float = Field(
        ..., ge=0.0, le=100.0, description="Updated progress percentage"
    )
    status: Optional[str] = Field(None, description="Updated status if changed")
    error_message: Optional[str] = Field(
        None, description="Error message if job failed"
    )


# Job retry schema
class JobRetryResponse(BaseModel):
    job: JobRead
    message: str = Field(
        "Job queued for retry", description="Retry confirmation message"
    )
    retry_count: int = Field(1, description="Number of times this job has been retried")


# Admin schemas
class AdminJobStatistics(JobStatistics):
    """Extended statistics for admin users"""

    jobs_by_user: Dict[str, int] = Field(
        default_factory=dict, description="Job counts by user ID"
    )
    processing_times_by_type: Dict[str, float] = Field(
        default_factory=dict, description="Average processing times by job type"
    )
    error_rates_by_type: Dict[str, float] = Field(
        default_factory=dict, description="Error rates by job type"
    )
    peak_processing_hours: List[int] = Field(
        default_factory=list, description="Hours of day with highest processing load"
    )


class CleanupJobsResponse(BaseModel):
    message: str = Field(..., description="Cleanup completion message")
    jobs_deleted: int = Field(..., description="Number of jobs deleted")
    days_old: int = Field(..., description="Age threshold used for cleanup")
    cleanup_timestamp: datetime = Field(..., description="When cleanup was performed")
