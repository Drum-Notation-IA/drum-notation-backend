from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.media.models import AudioFile, Video
from app.modules.media.schemas import VideoCreate, VideoUpdate


class VideoRepository:
    async def get_by_id(self, db: AsyncSession, video_id: UUID) -> Optional[Video]:
        """Get video by ID (excluding soft deleted)"""
        query = (
            select(Video)
            .where(and_(Video.id == video_id, Video.deleted_at.is_(None)))
            .options(
                selectinload(Video.user),
                selectinload(Video.audio_files),
                selectinload(Video.processing_jobs),
                # selectinload(Video.notations),  # Commented out - relationship not active
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_filename_and_user(
        self, db: AsyncSession, filename: str, user_id: UUID
    ) -> Optional[Video]:
        """Get video by filename and user (excluding soft deleted)"""
        query = (
            select(Video)
            .where(
                and_(
                    Video.filename == filename,
                    Video.user_id == user_id,
                    Video.deleted_at.is_(None),
                )
            )
            .options(selectinload(Video.user))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[UUID] = None,
        include_deleted: bool = False,
    ) -> List[Video]:
        """Get all videos with pagination and filtering"""
        query = select(Video).options(
            selectinload(Video.user),
            selectinload(Video.audio_files),
        )

        # Apply filters
        filters = []
        if not include_deleted:
            filters.append(Video.deleted_at.is_(None))
        if user_id:
            filters.append(Video.user_id == user_id)

        if filters:
            query = query.where(and_(*filters))

        query = query.offset(skip).limit(limit).order_by(Video.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        video_in: VideoCreate,
        user_id: UUID,
        storage_path: str,
        duration_seconds: Optional[float] = None,
    ) -> Video:
        """Create a new video record"""
        video = Video(
            user_id=user_id,
            filename=video_in.filename,
            storage_path=storage_path,
            duration_seconds=duration_seconds,
        )
        db.add(video)
        await db.flush()
        await db.refresh(video)
        return video

    async def update(
        self, db: AsyncSession, video_id: UUID, video_update: VideoUpdate
    ) -> Optional[Video]:
        """Update video metadata by ID"""
        # Build update data
        update_data = {}
        if video_update.filename is not None:
            update_data["filename"] = video_update.filename

        if not update_data:
            # No updates to make, return current video
            return await self.get_by_id(db, video_id)

        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(Video)
            .where(and_(Video.id == video_id, Video.deleted_at.is_(None)))
            .values(**update_data)
            .returning(Video)
        )

        result = await db.execute(query)
        updated_video = result.scalar_one_or_none()

        if updated_video:
            # Reload the video with relationships
            return await self.get_by_id(db, video_id)
        return updated_video

    async def soft_delete(self, db: AsyncSession, video_id: UUID) -> bool:
        """Soft delete video by setting deleted_at timestamp"""
        # First check if video exists
        video = await self.get_by_id(db, video_id)
        if not video:
            return False

        query = (
            update(Video)
            .where(and_(Video.id == video_id, Video.deleted_at.is_(None)))
            .values(deleted_at=datetime.utcnow())
        )

        await db.execute(query)
        await db.flush()
        return True

    async def hard_delete(self, db: AsyncSession, video_id: UUID) -> bool:
        """Permanently delete video (use with caution)"""
        video = await self.get_by_id(db, video_id)
        if video:
            await db.delete(video)
            return True
        return False

    async def restore(self, db: AsyncSession, video_id: UUID) -> Optional[Video]:
        """Restore a soft-deleted video"""
        query = (
            update(Video)
            .where(and_(Video.id == video_id, Video.deleted_at.is_not(None)))
            .values(deleted_at=None, updated_at=datetime.utcnow())
            .returning(Video)
        )

        result = await db.execute(query)
        restored_video = result.scalar_one_or_none()

        if restored_video:
            # Reload the video with relationships
            return await self.get_by_id(db, video_id)
        return restored_video

    async def count(
        self,
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        include_deleted: bool = False,
    ) -> int:
        """Count total videos with filters"""
        query = select(func.count(Video.id))

        # Apply filters
        filters = []
        if not include_deleted:
            filters.append(Video.deleted_at.is_(None))
        if user_id:
            filters.append(Video.user_id == user_id)

        if filters:
            query = query.where(and_(*filters))

        result = await db.execute(query)
        return result.scalar() or 0

    async def get_by_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Video]:
        """Get all videos for a specific user"""
        return await self.get_all(db, skip=skip, limit=limit, user_id=user_id)

    async def filename_exists_for_user(
        self,
        db: AsyncSession,
        filename: str,
        user_id: UUID,
        exclude_video_id: Optional[UUID] = None,
    ) -> bool:
        """Check if filename already exists for a user (excluding soft deleted)"""
        query = select(Video.id).where(
            and_(
                Video.filename == filename,
                Video.user_id == user_id,
                Video.deleted_at.is_(None),
            )
        )

        if exclude_video_id:
            query = query.where(Video.id != exclude_video_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_user_storage_size(self, db: AsyncSession, user_id: UUID) -> int:
        """Get total storage size for a user's videos (in bytes, estimated)"""
        # Note: This is an estimation based on duration
        # In a real implementation, you'd track actual file sizes
        query = select(func.sum(Video.duration_seconds)).where(
            and_(Video.user_id == user_id, Video.deleted_at.is_(None))
        )
        result = await db.execute(query)
        total_duration = result.scalar() or 0

        # Estimate: ~1MB per second of video (very rough approximation)
        estimated_bytes = int(total_duration * 1024 * 1024) if total_duration else 0
        return estimated_bytes

    async def get_user_total_duration(self, db: AsyncSession, user_id: UUID) -> float:
        """Get total duration of all videos for a user"""
        query = select(func.sum(Video.duration_seconds)).where(
            and_(Video.user_id == user_id, Video.deleted_at.is_(None))
        )
        result = await db.execute(query)
        return result.scalar() or 0.0

    async def get_videos_with_audio(self, db: AsyncSession, user_id: UUID) -> int:
        """Count videos that have associated audio files"""
        query = (
            select(func.count(Video.id.distinct()))
            .join(AudioFile, Video.id == AudioFile.video_id)
            .where(
                and_(
                    Video.user_id == user_id,
                    Video.deleted_at.is_(None),
                    AudioFile.deleted_at.is_(None),
                )
            )
        )
        result = await db.execute(query)
        return result.scalar() or 0

    async def get_videos_with_notation(self, db: AsyncSession, user_id: UUID) -> int:
        """Count videos that have associated notations"""
        # Import here to avoid circular imports
        from app.modules.notation.models import DrumNotation

        query = (
            select(func.count(Video.id.distinct()))
            .join(DrumNotation, Video.id == DrumNotation.video_id)
            .where(
                and_(
                    Video.user_id == user_id,
                    Video.deleted_at.is_(None),
                    DrumNotation.deleted_at.is_(None),
                )
            )
        )
        result = await db.execute(query)
        return result.scalar() or 0


class AudioFileRepository:
    async def get_by_id(
        self, db: AsyncSession, audio_file_id: UUID
    ) -> Optional[AudioFile]:
        """Get audio file by ID (excluding soft deleted)"""
        query = (
            select(AudioFile)
            .where(and_(AudioFile.id == audio_file_id, AudioFile.deleted_at.is_(None)))
            .options(
                selectinload(AudioFile.video),
                # selectinload(AudioFile.drum_events),  # Commented out - relationship not active
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_video_id(
        self, db: AsyncSession, video_id: UUID
    ) -> List[AudioFile]:
        """Get all audio files for a video"""
        query = (
            select(AudioFile)
            .where(and_(AudioFile.video_id == video_id, AudioFile.deleted_at.is_(None)))
            .options(selectinload(AudioFile.video))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        video_id: UUID,
        sample_rate: int,
        channels: int,
        storage_path: str,
        duration_seconds: Optional[float] = None,
    ) -> AudioFile:
        """Create a new audio file record"""
        audio_file = AudioFile(
            video_id=video_id,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration_seconds,
            storage_path=storage_path,
        )
        db.add(audio_file)
        await db.flush()
        await db.refresh(audio_file)
        return audio_file

    async def soft_delete(self, db: AsyncSession, audio_file_id: UUID) -> bool:
        """Soft delete audio file by setting deleted_at timestamp"""
        # First check if audio file exists
        audio_file = await self.get_by_id(db, audio_file_id)
        if not audio_file:
            return False

        query = (
            update(AudioFile)
            .where(and_(AudioFile.id == audio_file_id, AudioFile.deleted_at.is_(None)))
            .values(deleted_at=datetime.utcnow())
        )

        await db.execute(query)
        await db.flush()
        return True
