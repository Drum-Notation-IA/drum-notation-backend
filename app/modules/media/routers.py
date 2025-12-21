import os
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.media.models import MediaType
from app.modules.media.schemas import (
    MediaListResponse,
    MediaRead,
    MediaUpdate,
    MediaUploadResponse,
)
from app.modules.media.service import MediaService
from app.modules.users.models import User

router = APIRouter(prefix="/media", tags=["media"])
media_service = MediaService()


@router.post("/upload", response_model=MediaUploadResponse, status_code=201)
async def upload_media_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a new media file (audio, video, or image)

    - **file**: The media file to upload
    - **description**: Optional description for the file
    """
    return await media_service.upload_file(
        db=db, upload_file=file, user_id=current_user.id, description=description
    )


@router.get("/", response_model=MediaListResponse)
async def get_media_files(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    media_type: Optional[MediaType] = Query(None, description="Filter by media type"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    owner_only: bool = Query(False, description="Show only current user's files"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a paginated list of media files

    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **media_type**: Filter by media type (audio, video, image)
    - **user_id**: Filter by specific user ID
    - **owner_only**: Show only current user's files
    """
    return await media_service.get_media_list(
        db=db,
        page=page,
        per_page=per_page,
        user_id=user_id,
        media_type=media_type,
        owner_only=owner_only,
        current_user_id=current_user.id,
    )


@router.get("/my-files", response_model=MediaListResponse)
async def get_my_media_files(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    media_type: Optional[MediaType] = Query(None, description="Filter by media type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's media files

    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **media_type**: Filter by media type (audio, video, image)
    """
    return await media_service.get_media_list(
        db=db,
        page=page,
        per_page=per_page,
        user_id=current_user.id,
        media_type=media_type,
        current_user_id=current_user.id,
    )


@router.get("/{media_id}", response_model=MediaRead)
async def get_media_file(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get media file information by ID

    - **media_id**: The UUID of the media file
    """
    return await media_service.get_media_by_id(
        db=db, media_id=media_id, user_id=current_user.id
    )


@router.put("/{media_id}", response_model=MediaRead)
async def update_media_file(
    media_id: UUID,
    media_update: MediaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update media file metadata

    - **media_id**: The UUID of the media file
    - **media_update**: Updated media information
    """
    return await media_service.update_media(
        db=db, media_id=media_id, media_update=media_update, user_id=current_user.id
    )


@router.delete("/{media_id}")
async def delete_media_file(
    media_id: UUID,
    hard_delete: bool = Query(False, description="Permanently delete file and data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a media file (soft delete by default)

    - **media_id**: The UUID of the media file
    - **hard_delete**: If True, permanently delete file and data (default: False)
    """
    return await media_service.delete_media(
        db=db, media_id=media_id, user_id=current_user.id, hard_delete=hard_delete
    )


@router.post("/{media_id}/restore", response_model=MediaRead)
async def restore_media_file(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restore a soft-deleted media file

    - **media_id**: The UUID of the media file to restore
    """
    return await media_service.restore_media(
        db=db, media_id=media_id, user_id=current_user.id
    )


@router.get("/{media_id}/download")
async def download_media_file(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the actual media file

    - **media_id**: The UUID of the media file
    """
    file_path, original_filename, content_type = await media_service.get_download_info(
        db=db, media_id=media_id, user_id=current_user.id
    )

    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Physical file not found")

    return FileResponse(
        path=file_path,
        filename=original_filename,
        media_type=content_type,
    )


@router.get("/stats/my-usage")
async def get_my_media_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's media usage statistics

    Returns information about:
    - Total number of files
    - Total storage used
    - Files by media type
    - Storage quota information
    """
    return await media_service.get_user_media_stats(db=db, user_id=current_user.id)


@router.get("/stats/storage")
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get storage system statistics (for admin users)

    Returns information about:
    - Total storage usage by media type
    - File counts
    - Directory information
    """
    # Note: In a real application, you might want to add admin role checking here
    return media_service.get_storage_stats()


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
    return await media_service.cleanup_orphaned_files(db=db)


# Public endpoints (no authentication required)
@router.get("/public/{media_id}")
async def get_public_media_info(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get public media file information (no authentication required)

    This endpoint can be used for public file sharing.
    You might want to add additional checks or permissions here.
    """
    return await media_service.get_media_by_id(db=db, media_id=media_id)


@router.get("/public/{media_id}/download")
async def download_public_media_file(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Download public media file (no authentication required)

    This endpoint can be used for public file sharing.
    You might want to add additional checks or permissions here.
    """
    file_path, original_filename, content_type = await media_service.get_download_info(
        db=db, media_id=media_id
    )

    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Physical file not found")

    return FileResponse(
        path=file_path,
        filename=original_filename,
        media_type=content_type,
    )
