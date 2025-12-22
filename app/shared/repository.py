"""
Base Repository
Generic repository pattern implementation for database operations
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    """Generic repository for common database operations"""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def create(self, db: AsyncSession, **kwargs) -> ModelType:
        """Create a new record"""
        instance = self.model(**kwargs)
        db.add(instance)
        await db.commit()
        await db.refresh(instance)
        return instance

    async def get_by_id(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get a record by ID"""
        query = select(self.model).where(
            and_(
                self.model.id == id,
                self.model.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self, db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> List[ModelType]:
        """Get all records with pagination"""
        query = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .order_by(desc(self.model.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update(self, db: AsyncSession, id: UUID, **kwargs) -> Optional[ModelType]:
        """Update a record by ID"""
        instance = await self.get_by_id(db, id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            await db.commit()
            await db.refresh(instance)
        return instance

    async def delete(self, db: AsyncSession, id: UUID) -> bool:
        """Soft delete a record by ID"""
        instance = await self.get_by_id(db, id)
        if instance:
            from datetime import datetime

            instance.deleted_at = datetime.utcnow()
            await db.commit()
            return True
        return False

    async def hard_delete(self, db: AsyncSession, id: UUID) -> bool:
        """Hard delete a record by ID"""
        instance = await self.get_by_id(db, id)
        if instance:
            await db.delete(instance)
            await db.commit()
            return True
        return False
