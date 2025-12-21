import os
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.media.schemas import (
    VideoListResponse,
    VideoRead,
    VideoStatsResponse,
    VideoUpdate,
    VideoUploadResponse,
)
from app.modules.media.service import VideoService
from app.modules.users.models import User

router = APIRouter(prefix="/videos", tags=["videos"])
video_service = VideoService()


@router.post("/upload", response_model=VideoUploadResponse, status_code=201)
async def upload_video_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a new video file (drum performance recording)

    - **file**: The video file to upload (mp4, mov, avi, mkv, webm)
    - Supported formats: MP4, MOV, AVI, MKV, WebM
    - Maximum file size: 500MB
    """
    return await video_service.upload_video(
        db=db, upload_file=file, user_id=UUID(str(current_user.id))
    )


@router.get("/", response_model=VideoListResponse)
async def get_videos(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    owner_only: bool = Query(False, description="Show only current user's videos"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a paginated list of videos

    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **user_id**: Filter by specific user ID
    - **owner_only**: Show only current user's videos
    """
    return await video_service.get_video_list(
        db=db,
        page=page,
        per_page=per_page,
        user_id=user_id,
        owner_only=owner_only,
        current_user_id=UUID(str(current_user.id)),
    )


@router.get("/my-videos", response_model=VideoListResponse)
async def get_my_videos(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's videos

    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    """
    return await video_service.get_video_list(
        db=db,
        page=page,
        per_page=per_page,
        user_id=UUID(str(current_user.id)),
        current_user_id=UUID(str(current_user.id)),
    )


@router.get("/{video_id}", response_model=VideoRead)
async def get_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get video information by ID

    - **video_id**: The UUID of the video
    """
    return await video_service.get_video_by_id(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )


@router.put("/{video_id}", response_model=VideoRead)
async def update_video(
    video_id: UUID,
    video_update: VideoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update video metadata

    - **video_id**: The UUID of the video
    - **video_update**: Updated video information (filename)
    """
    return await video_service.update_video(
        db=db,
        video_id=video_id,
        video_update=video_update,
        user_id=UUID(str(current_user.id)),
    )


@router.delete("/{video_id}")
async def delete_video(
    video_id: UUID,
    hard_delete: bool = Query(False, description="Permanently delete file and data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a video (soft delete by default)

    - **video_id**: The UUID of the video
    - **hard_delete**: If True, permanently delete file and data (default: False)
    """
    return await video_service.delete_video(
        db=db,
        video_id=video_id,
        user_id=UUID(str(current_user.id)),
        hard_delete=hard_delete,
    )


@router.post("/{video_id}/restore", response_model=VideoRead)
async def restore_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restore a soft-deleted video

    - **video_id**: The UUID of the video to restore
    """
    return await video_service.restore_video(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )


@router.get("/{video_id}/download")
async def download_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the actual video file

    - **video_id**: The UUID of the video
    """
    storage_path, filename, content_type = await video_service.get_download_info(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )

    # Check if file exists
    if not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Physical file not found")

    return FileResponse(
        path=storage_path,
        filename=filename,
        media_type=content_type,
    )


@router.get("/stats/my-usage", response_model=VideoStatsResponse)
async def get_my_video_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's video usage statistics

    Returns information about:
    - Total number of videos
    - Total storage used
    - Total video duration
    - Videos with extracted audio
    - Videos with generated notation
    - Storage quota information
    """
    return await video_service.get_user_video_stats(
        db=db, user_id=UUID(str(current_user.id))
    )


@router.get("/stats/storage")
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get storage system statistics

    Returns information about:
    - Total storage usage for videos and audio
    - File counts by type
    - Directory information
    """
    return video_service.get_storage_stats()


@router.get("/info/supported-formats")
async def get_supported_formats():
    """
    Get information about supported video formats

    Returns details about:
    - Supported file extensions
    - MIME types
    - File size limits
    - Format descriptions
    """
    return video_service.get_supported_formats()


# Video Processing Endpoints
@router.post("/{video_id}/extract-audio")
async def extract_audio_from_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Initiate audio extraction from video

    This will create a background job to extract audio from the video file.
    The extracted audio will be used for drum detection and notation generation.

    - **video_id**: The UUID of the video to process
    """
    return await video_service.initiate_audio_extraction(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )


@router.get("/{video_id}/processing-status")
async def get_video_processing_status(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get processing status for a video

    Returns information about:
    - Whether audio has been extracted
    - Processing job status
    - Available processed files

    - **video_id**: The UUID of the video
    """
    return await video_service.get_video_processing_status(
        db=db, video_id=video_id, user_id=UUID(str(current_user.id))
    )


# Admin endpoints (you might want to add role-based access control)
@router.post("/admin/cleanup-orphaned")
async def cleanup_orphaned_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clean up orphaned files that are no longer referenced in the database

    This endpoint removes physical files that exist in storage but are not
    referenced by any database records.

    **Note**: This should be restricted to admin users in production.
    """
    # Note: Add admin role check here in production
    return await video_service.cleanup_orphaned_files(db=db)


# Public endpoints (no authentication required)
@router.get("/public/{video_id}")
async def get_public_video_info(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get public video information (no authentication required)

    This endpoint can be used for public video sharing.
    You might want to add additional checks or permissions here.
    """
    return await video_service.get_video_by_id(db=db, video_id=video_id)


@router.get("/public/{video_id}/download")
async def download_public_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Download public video file (no authentication required)

    This endpoint can be used for public video sharing.
    You might want to add additional checks or permissions here.
    """
    storage_path, filename, content_type = await video_service.get_download_info(
        db=db, video_id=video_id
    )

    # Check if file exists
    if not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Physical file not found")

    return FileResponse(
        path=storage_path,
        filename=filename,
        media_type=content_type,
    )


# Bulk Operations
@router.get("/bulk/my-videos/stats")
async def get_bulk_video_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get bulk statistics for all user's videos

    Useful for dashboard displays and overview information.
    """
    stats = await video_service.get_user_video_stats(
        db=db, user_id=UUID(str(current_user.id))
    )
    storage_info = video_service.get_storage_stats()
    formats_info = video_service.get_supported_formats()

    return {
        "user_stats": stats,
        "system_storage": storage_info,
        "supported_formats": formats_info,
    }


@router.post("/bulk/delete")
async def bulk_delete_videos(
    video_ids: List[UUID],
    hard_delete: bool = Query(False, description="Permanently delete files and data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete multiple videos at once

    - **video_ids**: List of video UUIDs to delete
    - **hard_delete**: If True, permanently delete files and data (default: False)
    """
    if len(video_ids) > 50:
        raise HTTPException(
            status_code=400, detail="Cannot delete more than 50 videos at once"
        )

    results = []
    for video_id in video_ids:
        try:
            result = await video_service.delete_video(
                db=db,
                video_id=video_id,
                user_id=UUID(str(current_user.id)),
                hard_delete=hard_delete,
            )
            results.append(
                {
                    "video_id": str(video_id),
                    "status": "success",
                    "message": result["message"],
                }
            )
        except HTTPException as e:
            results.append(
                {"video_id": str(video_id), "status": "error", "message": e.detail}
            )
        except Exception as e:
            results.append(
                {"video_id": str(video_id), "status": "error", "message": str(e)}
            )

    successful_deletions = len([r for r in results if r["status"] == "success"])

    return {
        "message": f"Bulk deletion completed: {successful_deletions}/{len(video_ids)} videos processed",
        "results": results,
    }
