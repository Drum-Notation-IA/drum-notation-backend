import math
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import MediaType
from app.modules.media.repository import MediaRepository
from app.modules.media.schemas import (
    MediaCreate,
    MediaListResponse,
    MediaRead,
    MediaUpdate,
    MediaUploadResponse,
)
from app.modules.media.storage import FileStorage


class MediaService:
    def __init__(self):
        self.repository = MediaRepository()
        self.storage = FileStorage()

    async def upload_file(
        self,
        db: AsyncSession,
        upload_file: UploadFile,
        user_id: UUID,
        description: Optional[str] = None,
    ) -> MediaUploadResponse:
        """Upload a new media file"""

        # Validate file
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Validate content type
        if not self.storage.is_allowed_file_type(
            upload_file.content_type, upload_file.filename
        ):
            raise HTTPException(
                status_code=400,
                detail=f"File type {upload_file.content_type} is not allowed",
            )

        # Get media type
        media_type = self.storage.get_media_type_from_content_type(
            upload_file.content_type
        )
        if not media_type:
            raise HTTPException(
                status_code=400, detail="Unable to determine media type"
            )

        # Read file to get size (we need this for validation)
        content = await upload_file.read()
        file_size = len(content)
        await upload_file.seek(0)  # Reset file pointer

        # Validate file size
        if not self.storage.validate_file_size(file_size, media_type):
            max_sizes = {
                MediaType.VIDEO: "100MB",
                MediaType.AUDIO: "50MB",
                MediaType.IMAGE: "10MB",
            }
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size for {media_type.value} files ({max_sizes[media_type]})",
            )

        # Check user storage quota (optional - can be implemented later)
        user_total_size = await self.repository.get_user_media_size(db, user_id)
        max_user_storage = 1024 * 1024 * 1024  # 1GB per user
        if user_total_size + file_size > max_user_storage:
            raise HTTPException(
                status_code=400,
                detail="Storage quota exceeded. Please delete some files first.",
            )

        try:
            # Save file to storage
            stored_filename, file_path, actual_file_size = await self.storage.save_file(
                upload_file, media_type
            )

            # Create media record
            media_create = MediaCreate(
                original_filename=upload_file.filename,
                content_type=upload_file.content_type,
                media_type=media_type,
                file_size=actual_file_size,
                description=description,
            )

            media = await self.repository.create(
                db, media_create, user_id, stored_filename, file_path
            )
            await db.commit()

            return MediaUploadResponse(
                message="File uploaded successfully",
                media=MediaRead.model_validate(media),
            )

        except Exception as e:
            # Rollback database changes
            await db.rollback()

            # Clean up file if it was saved
            if "file_path" in locals():
                self.storage.delete_file(file_path)

            raise HTTPException(
                status_code=500, detail=f"Failed to upload file: {str(e)}"
            )

    async def get_media_by_id(
        self, db: AsyncSession, media_id: UUID, user_id: Optional[UUID] = None
    ) -> MediaRead:
        """Get media file by ID"""
        media = await self.repository.get_by_id(db, media_id)

        if not media:
            raise HTTPException(status_code=404, detail="Media file not found")

        # Check ownership if user_id is provided
        if user_id and media.uploaded_by != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this media file"
            )

        return MediaRead.model_validate(media)

    async def get_media_list(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        user_id: Optional[UUID] = None,
        media_type: Optional[MediaType] = None,
        owner_only: bool = False,
        current_user_id: Optional[UUID] = None,
    ) -> MediaListResponse:
        """Get paginated list of media files"""

        # Validate pagination parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20

        skip = (page - 1) * per_page

        # If owner_only is True, filter by current_user_id
        filter_user_id = current_user_id if owner_only else user_id

        # Get media files and total count
        media_files = await self.repository.get_all(
            db, skip=skip, limit=per_page, user_id=filter_user_id, media_type=media_type
        )

        total = await self.repository.count(
            db, user_id=filter_user_id, media_type=media_type
        )

        # Calculate pagination info
        pages = math.ceil(total / per_page) if total > 0 else 1

        return MediaListResponse(
            media=[MediaRead.model_validate(media) for media in media_files],
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    async def update_media(
        self, db: AsyncSession, media_id: UUID, media_update: MediaUpdate, user_id: UUID
    ) -> MediaRead:
        """Update media metadata"""

        # Check if media exists and user owns it
        media = await self.repository.get_by_id(db, media_id)
        if not media:
            raise HTTPException(status_code=404, detail="Media file not found")

        if media.uploaded_by != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this media file"
            )

        # Update media
        updated_media = await self.repository.update(db, media_id, media_update)
        if not updated_media:
            raise HTTPException(status_code=500, detail="Failed to update media")

        await db.commit()
        return MediaRead.model_validate(updated_media)

    async def delete_media(
        self, db: AsyncSession, media_id: UUID, user_id: UUID, hard_delete: bool = False
    ) -> dict:
        """Delete media file (soft or hard delete)"""

        # Check if media exists and user owns it
        media = await self.repository.get_by_id(db, media_id)
        if not media:
            raise HTTPException(status_code=404, detail="Media file not found")

        if media.uploaded_by != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this media file"
            )

        try:
            if hard_delete:
                # Delete physical file
                self.storage.delete_file(media.file_path)

                # Hard delete from database
                success = await self.repository.hard_delete(db, media_id)
            else:
                # Soft delete only
                success = await self.repository.soft_delete(db, media_id)

            if not success:
                raise HTTPException(status_code=500, detail="Failed to delete media")

            await db.commit()

            delete_type = "permanently deleted" if hard_delete else "deleted"
            return {"message": f"Media file {delete_type} successfully"}

        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to delete media: {str(e)}"
            )

    async def get_download_info(
        self, db: AsyncSession, media_id: UUID, user_id: Optional[UUID] = None
    ) -> Tuple[str, str, str]:
        """Get media file download information"""

        media = await self.repository.get_by_id(db, media_id)
        if not media:
            raise HTTPException(status_code=404, detail="Media file not found")

        # Check ownership if user_id is provided
        if user_id and media.uploaded_by != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to download this media file"
            )

        # Check if physical file exists
        if not self.storage.file_exists(media.file_path):
            raise HTTPException(status_code=404, detail="Physical file not found")

        return media.file_path, media.original_filename, media.content_type

    async def get_user_media_stats(self, db: AsyncSession, user_id: UUID) -> dict:
        """Get media statistics for a user"""

        total_files = await self.repository.count(db, user_id=user_id)
        total_size = await self.repository.get_user_media_size(db, user_id)

        # Get counts by media type
        type_stats = {}
        for media_type in MediaType:
            count = await self.repository.count(
                db, user_id=user_id, media_type=media_type
            )
            type_stats[media_type.value] = count

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files_by_type": type_stats,
            "storage_quota_bytes": 1024 * 1024 * 1024,  # 1GB
            "storage_quota_mb": 1024,
            "storage_used_percentage": round(
                (total_size / (1024 * 1024 * 1024)) * 100, 2
            ),
        }

    async def restore_media(
        self, db: AsyncSession, media_id: UUID, user_id: UUID
    ) -> MediaRead:
        """Restore a soft-deleted media file"""

        # First, check if the media exists (even if deleted)
        media = await self.repository.restore(db, media_id)
        if not media:
            raise HTTPException(
                status_code=404, detail="Media file not found or not deleted"
            )

        # Check ownership
        if media.uploaded_by != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to restore this media file"
            )

        await db.commit()
        return MediaRead.model_validate(media)

    def get_storage_stats(self) -> dict:
        """Get storage system statistics"""
        return self.storage.get_storage_info()

    async def cleanup_orphaned_files(self, db: AsyncSession) -> dict:
        """Clean up orphaned files that are no longer in the database"""

        # Get all stored filenames from database
        all_media = await self.repository.get_all(db, limit=10000, include_deleted=True)
        stored_filenames = [media.stored_filename for media in all_media]

        # Clean up orphaned files
        orphaned_count = self.storage.cleanup_orphaned_files(stored_filenames)

        return {
            "message": f"Cleanup completed",
            "orphaned_files_removed": orphaned_count,
        }
