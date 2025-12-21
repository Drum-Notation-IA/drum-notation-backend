import math
from pathlib import Path
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.repository import AudioFileRepository, VideoRepository
from app.modules.media.schemas import (
    VideoCreate,
    VideoListResponse,
    VideoRead,
    VideoStatsResponse,
    VideoUpdate,
    VideoUploadResponse,
)
from app.modules.media.storage import VideoStorage


class VideoService:
    def __init__(self):
        self.video_repository = VideoRepository()
        self.audio_repository = AudioFileRepository()
        self.storage = VideoStorage()

    async def upload_video(
        self,
        db: AsyncSession,
        upload_file: UploadFile,
        user_id: UUID,
    ) -> VideoUploadResponse:
        """Upload a new video file"""

        # Validate file
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Validate content type and file extension
        content_type = upload_file.content_type or "application/octet-stream"
        if not self.storage.is_allowed_video_type(content_type, upload_file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"File type {content_type} is not allowed. Only video files (mp4, mov, avi, mkv, webm) are supported.",
            )

        # Read file to get size for validation
        content = await upload_file.read()
        file_size = len(content)
        await upload_file.seek(0)  # Reset file pointer

        # Validate file size
        if not self.storage.validate_video_file_size(file_size):
            raise HTTPException(
                status_code=400,
                detail="Video file size exceeds maximum allowed size (500MB)",
            )

        # Check if filename already exists for this user
        if await self.video_repository.filename_exists_for_user(
            db, upload_file.filename, user_id
        ):
            raise HTTPException(
                status_code=400,
                detail=f"A video with filename '{upload_file.filename}' already exists",
            )

        # Check user storage quota
        user_total_size = await self.video_repository.get_user_storage_size(db, user_id)
        max_user_storage = 5 * 1024 * 1024 * 1024  # 5GB per user
        if user_total_size + file_size > max_user_storage:
            raise HTTPException(
                status_code=400,
                detail="Storage quota exceeded. Please delete some videos first.",
            )

        try:
            # Save video file to storage
            (
                stored_filename,
                storage_path,
                actual_file_size,
            ) = await self.storage.save_video_file(upload_file, str(user_id))

            # Estimate duration (rough approximation until we implement ffmpeg)
            estimated_duration = self.storage.get_video_duration_estimate(
                actual_file_size
            )

            # Create video record
            video_create = VideoCreate(filename=upload_file.filename)

            video = await self.video_repository.create(
                db, video_create, user_id, storage_path, estimated_duration
            )
            await db.commit()

            return VideoUploadResponse(
                message="Video uploaded successfully",
                video=VideoRead.model_validate(video),
            )

        except Exception as e:
            # Rollback database changes
            await db.rollback()

            # Clean up file if it was saved
            try:
                storage_path_var = locals().get("storage_path")
                if storage_path_var:
                    self.storage.delete_video_file(storage_path_var)
            except Exception:
                pass  # Ignore cleanup errors

            raise HTTPException(
                status_code=500, detail=f"Failed to upload video: {str(e)}"
            )

    async def get_video_by_id(
        self, db: AsyncSession, video_id: UUID, user_id: Optional[UUID] = None
    ) -> VideoRead:
        """Get video by ID"""
        video = await self.video_repository.get_by_id(db, video_id)

        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Check ownership if user_id is provided
        if user_id is not None and str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to access this video"
            )

        return VideoRead.model_validate(video)

    async def get_video_list(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        user_id: Optional[UUID] = None,
        owner_only: bool = False,
        current_user_id: Optional[UUID] = None,
    ) -> VideoListResponse:
        """Get paginated list of videos"""

        # Validate pagination parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20

        skip = (page - 1) * per_page

        # If owner_only is True, filter by current_user_id
        filter_user_id = current_user_id if owner_only else user_id

        # Get videos and total count
        videos = await self.video_repository.get_all(
            db, skip=skip, limit=per_page, user_id=filter_user_id
        )

        total = await self.video_repository.count(db, user_id=filter_user_id)

        # Calculate pagination info
        pages = math.ceil(total / per_page) if total > 0 else 1

        return VideoListResponse(
            videos=[VideoRead.model_validate(video) for video in videos],
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    async def update_video(
        self, db: AsyncSession, video_id: UUID, video_update: VideoUpdate, user_id: UUID
    ) -> VideoRead:
        """Update video metadata"""

        # Check if video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to update this video"
            )

        # Check if new filename conflicts with existing videos
        if (
            video_update.filename
            and video_update.filename != video.filename
            and await self.video_repository.filename_exists_for_user(
                db, video_update.filename, user_id, exclude_video_id=video_id
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=f"A video with filename '{video_update.filename}' already exists",
            )

        # Update video
        updated_video = await self.video_repository.update(db, video_id, video_update)
        if not updated_video:
            raise HTTPException(status_code=500, detail="Failed to update video")

        await db.commit()
        return VideoRead.model_validate(updated_video)

    async def delete_video(
        self, db: AsyncSession, video_id: UUID, user_id: UUID, hard_delete: bool = False
    ) -> dict:
        """Delete video (soft or hard delete)"""

        # Check if video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this video"
            )

        try:
            if hard_delete:
                # Delete physical files
                self.storage.delete_video_file(str(video.storage_path))

                # Delete associated audio files if any
                audio_files = await self.audio_repository.get_by_video_id(db, video_id)
                for audio_file in audio_files:
                    self.storage.delete_audio_file(str(audio_file.storage_path))

                # Hard delete from database (cascades to related records)
                success = await self.video_repository.hard_delete(db, video_id)
            else:
                # Soft delete only
                success = await self.video_repository.soft_delete(db, video_id)

            if not success:
                raise HTTPException(status_code=500, detail="Failed to delete video")

            await db.commit()

            delete_type = "permanently deleted" if hard_delete else "deleted"
            return {"message": f"Video {delete_type} successfully"}

        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to delete video: {str(e)}"
            )

    async def get_download_info(
        self, db: AsyncSession, video_id: UUID, user_id: Optional[UUID] = None
    ) -> Tuple[str, str, str]:
        """Get video file download information"""

        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Check ownership if user_id is provided
        if user_id is not None and str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to download this video"
            )

        # Check if physical file exists
        if not self.storage.file_exists(str(video.storage_path)):
            raise HTTPException(status_code=404, detail="Physical file not found")

        # Determine content type from filename
        extension = self.storage.get_file_extension(str(video.filename)).lower()
        content_type_map = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
        }
        content_type = content_type_map.get(extension, "application/octet-stream")

        return str(video.storage_path), str(video.filename), content_type

    async def get_user_video_stats(
        self, db: AsyncSession, user_id: UUID
    ) -> VideoStatsResponse:
        """Get video statistics for a user"""

        total_videos = await self.video_repository.count(db, user_id=user_id)
        total_size = await self.video_repository.get_user_storage_size(db, user_id)
        total_duration = await self.video_repository.get_user_total_duration(
            db, user_id
        )
        videos_with_audio = await self.video_repository.get_videos_with_audio(
            db, user_id
        )

        # Try to get notation count (may fail if notation module not implemented yet)
        try:
            videos_with_notation = await self.video_repository.get_videos_with_notation(
                db, user_id
            )
        except Exception:
            videos_with_notation = 0

        storage_quota_bytes = 5 * 1024 * 1024 * 1024  # 5GB
        storage_used_percentage = (
            round((total_size / storage_quota_bytes) * 100, 2)
            if storage_quota_bytes > 0
            else 0
        )

        return VideoStatsResponse(
            total_videos=total_videos,
            total_size_bytes=total_size,
            total_size_mb=round(total_size / (1024 * 1024), 2),
            total_duration_seconds=total_duration if total_duration > 0 else None,
            total_duration_minutes=round(total_duration / 60, 2)
            if total_duration > 0
            else None,
            videos_with_audio=videos_with_audio,
            videos_with_notation=videos_with_notation,
            storage_quota_bytes=storage_quota_bytes,
            storage_quota_mb=5 * 1024,  # 5GB in MB
            storage_used_percentage=storage_used_percentage,
        )

    async def restore_video(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> VideoRead:
        """Restore a soft-deleted video"""

        # First, check if the video exists (even if deleted)
        video = await self.video_repository.restore(db, video_id)
        if not video:
            raise HTTPException(
                status_code=404, detail="Video not found or not deleted"
            )

        # Check ownership
        if video is not None and str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to restore this video"
            )

        await db.commit()
        return VideoRead.model_validate(video)

    def get_storage_stats(self) -> dict:
        """Get storage system statistics"""
        return self.storage.get_storage_info()

    def get_supported_formats(self) -> dict:
        """Get supported video formats information"""
        return self.storage.get_supported_formats_info()

    async def cleanup_orphaned_files(self, db: AsyncSession) -> dict:
        """Clean up orphaned files that are no longer in the database"""

        # Get all stored filenames from database
        all_videos = await self.video_repository.get_all(
            db, limit=10000, include_deleted=True
        )
        video_filenames = [Path(str(video.storage_path)).name for video in all_videos]

        # Get audio files (simplified approach since get_all_audio_files doesn't exist)
        audio_filenames = []
        for video in all_videos:
            audio_files = await self.audio_repository.get_by_video_id(
                db, UUID(str(video.id))
            )
            for audio_file in audio_files:
                audio_filenames.append(Path(str(audio_file.storage_path)).name)

        # Clean up orphaned files
        orphaned_videos = self.storage.cleanup_orphaned_video_files(video_filenames)
        orphaned_audio = self.storage.cleanup_orphaned_audio_files(audio_filenames)

        return {
            "message": "Cleanup completed",
            "orphaned_video_files_removed": orphaned_videos,
            "orphaned_audio_files_removed": orphaned_audio,
            "total_orphaned_files_removed": orphaned_videos + orphaned_audio,
        }

    async def initiate_audio_extraction(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> dict:
        """
        Initiate audio extraction from video (placeholder for future implementation)
        This would typically create a background job for processing
        """

        # Check if video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to process this video"
            )

        # Check if audio already exists
        existing_audio = await self.audio_repository.get_by_video_id(db, video_id)
        if existing_audio:
            raise HTTPException(
                status_code=400,
                detail="Audio has already been extracted from this video",
            )

        # TODO: Create a processing job for audio extraction
        # This would be implemented when the jobs module is ready

        return {
            "message": "Audio extraction initiated",
            "video_id": str(video_id),
            "status": "pending",
            "note": "Audio extraction will be implemented with the jobs module",
        }

    async def get_video_processing_status(
        self, db: AsyncSession, video_id: UUID, user_id: UUID
    ) -> dict:
        """
        Get processing status for a video (placeholder for future implementation)
        """

        # Check if video exists and user owns it
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to access this video's status"
            )

        # Get associated audio files
        audio_files = await self.audio_repository.get_by_video_id(db, video_id)

        return {
            "video_id": str(video_id),
            "filename": str(video.filename),
            "has_audio_extracted": len(audio_files) > 0,
            "audio_files_count": len(audio_files),
            "processing_status": "completed" if audio_files else "pending",
            "note": "Full processing status will be available with the jobs module",
        }
