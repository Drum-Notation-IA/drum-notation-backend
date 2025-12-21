import os
import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.media.models import Media, MediaType
from app.modules.media.schemas import MediaCreate, MediaUpdate


class MediaRepository:
    async def get_by_id(self, db: AsyncSession, media_id: UUID) -> Optional[Media]:
        """Get media by ID (excluding soft deleted)"""
        query = (
            select(Media)
            .where(and_(Media.id == media_id, Media.deleted_at.is_(None)))
            .options(selectinload(Media.user))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_stored_filename(
        self, db: AsyncSession, stored_filename: str
    ) -> Optional[Media]:
        """Get media by stored filename (excluding soft deleted)"""
        query = (
            select(Media)
            .where(
                and_(
                    Media.stored_filename == stored_filename,
                    Media.deleted_at.is_(None),
                )
            )
            .options(selectinload(Media.user))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[UUID] = None,
        media_type: Optional[MediaType] = None,
        include_deleted: bool = False,
    ) -> List[Media]:
        """Get all media files with pagination and filtering"""
        query = select(Media).options(selectinload(Media.user))

        # Apply filters
        filters = []
        if not include_deleted:
            filters.append(Media.deleted_at.is_(None))
        if user_id:
            filters.append(Media.uploaded_by == user_id)
        if media_type:
            filters.append(Media.media_type == media_type)

        if filters:
            query = query.where(and_(*filters))

        query = query.offset(skip).limit(limit).order_by(Media.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        media_in: MediaCreate,
        uploaded_by: UUID,
        stored_filename: str,
        file_path: str,
    ) -> Media:
        """Create a new media file record"""
        media = Media(
            original_filename=media_in.original_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            content_type=media_in.content_type,
            media_type=media_in.media_type.value,
            file_size=media_in.file_size,
            description=media_in.description,
            uploaded_by=uploaded_by,
        )
        db.add(media)
        await db.flush()
        await db.refresh(media)
        return media

    async def update(
        self, db: AsyncSession, media_id: UUID, media_update: MediaUpdate
    ) -> Optional[Media]:
        """Update media metadata by ID"""
        # Build update data
        update_data = {}
        if media_update.original_filename is not None:
            update_data["original_filename"] = media_update.original_filename
        if media_update.description is not None:
            update_data["description"] = media_update.description

        if not update_data:
            # No updates to make, return current media
            return await self.get_by_id(db, media_id)

        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(Media)
            .where(and_(Media.id == media_id, Media.deleted_at.is_(None)))
            .values(**update_data)
            .returning(Media)
        )

        result = await db.execute(query)
        updated_media = result.scalar_one_or_none()

        if updated_media:
            # Reload the media with relationships
            return await self.get_by_id(db, media_id)
        return updated_media

    async def soft_delete(self, db: AsyncSession, media_id: UUID) -> bool:
        """Soft delete media by setting deleted_at timestamp"""
        # First check if media exists
        media = await self.get_by_id(db, media_id)
        if not media:
            return False

        query = (
            update(Media)
            .where(and_(Media.id == media_id, Media.deleted_at.is_(None)))
            .values(deleted_at=datetime.utcnow())
        )

        await db.execute(query)
        await db.flush()
        return True

    async def hard_delete(self, db: AsyncSession, media_id: UUID) -> bool:
        """Permanently delete media (use with caution)"""
        media = await self.get_by_id(db, media_id)
        if media:
            await db.delete(media)
            return True
        return False

    async def restore(self, db: AsyncSession, media_id: UUID) -> Optional[Media]:
        """Restore a soft-deleted media file"""
        query = (
            update(Media)
            .where(and_(Media.id == media_id, Media.deleted_at.is_not(None)))
            .values(deleted_at=None, updated_at=datetime.utcnow())
            .returning(Media)
        )

        result = await db.execute(query)
        restored_media = result.scalar_one_or_none()

        if restored_media:
            # Reload the media with relationships
            return await self.get_by_id(db, media_id)
        return restored_media

    async def count(
        self,
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        media_type: Optional[MediaType] = None,
        include_deleted: bool = False,
    ) -> int:
        """Count total media files with filters"""
        query = select(Media.id)

        # Apply filters
        filters = []
        if not include_deleted:
            filters.append(Media.deleted_at.is_(None))
        if user_id:
            filters.append(Media.uploaded_by == user_id)
        if media_type:
            filters.append(Media.media_type == media_type)

        if filters:
            query = query.where(and_(*filters))

        result = await db.execute(query)
        return len(result.scalars().all())

    async def get_by_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        media_type: Optional[MediaType] = None,
    ) -> List[Media]:
        """Get all media files for a specific user"""
        return await self.get_all(
            db, skip=skip, limit=limit, user_id=user_id, media_type=media_type
        )

    async def stored_filename_exists(
        self, db: AsyncSession, stored_filename: str
    ) -> bool:
        """Check if stored filename already exists"""
        query = select(Media.id).where(Media.stored_filename == stored_filename)
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_user_media_size(self, db: AsyncSession, user_id: UUID) -> int:
        """Get total file size for a user's media files"""
        query = select(Media.file_size).where(
            and_(Media.uploaded_by == user_id, Media.deleted_at.is_(None))
        )
        result = await db.execute(query)
        sizes = result.scalars().all()
        return sum(sizes) if sizes else 0
