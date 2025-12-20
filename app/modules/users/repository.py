from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserUpdate


class UserRepository:
    async def get_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Get user by ID (excluding soft deleted)"""
        query = (
            select(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .options(selectinload(User.roles))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email (excluding soft deleted)"""
        query = (
            select(User)
            .where(and_(User.email == email, User.deleted_at.is_(None)))
            .options(selectinload(User.roles))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> List[User]:
        """Get all users with pagination"""
        query = select(User).options(selectinload(User.roles))

        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))

        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, user_in: UserCreate) -> User:
        """Create a new user"""
        user = User(email=user_in.email, password_hash=hash_password(user_in.password))
        db.add(user)
        await db.flush()
        await db.refresh(user)

        # For new users, manually set roles to empty list to avoid lazy loading
        # This prevents SQLAlchemy from trying to query the roles relationship
        user.__dict__["roles"] = []
        return user

    async def update(
        self, db: AsyncSession, user_id: UUID, user_update: UserUpdate
    ) -> Optional[User]:
        """Update user by ID"""
        # Build update data
        update_data = {}
        if user_update.email is not None:
            update_data["email"] = user_update.email
        if user_update.password is not None:
            update_data["password_hash"] = hash_password(user_update.password)

        if not update_data:
            # No updates to make, return current user
            return await self.get_by_id(db, user_id)

        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .values(**update_data)
            .returning(User)
        )

        result = await db.execute(query)
        updated_user = result.scalar_one_or_none()

        if updated_user:
            # Reload the user with relationships
            return await self.get_by_id(db, user_id)
        return updated_user

    async def soft_delete(self, db: AsyncSession, user_id: UUID) -> bool:
        """Soft delete user by setting deleted_at timestamp"""
        # First check if user exists
        user = await self.get_by_id(db, user_id)
        if not user:
            return False

        query = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .values(deleted_at=datetime.utcnow())
        )

        await db.execute(query)
        await db.flush()
        return True

    async def hard_delete(self, db: AsyncSession, user_id: UUID) -> bool:
        """Permanently delete user (use with caution)"""
        user = await self.get_by_id(db, user_id)
        if user:
            await db.delete(user)
            return True
        return False

    async def restore(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Restore a soft-deleted user"""
        query = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_not(None)))
            .values(deleted_at=None, updated_at=datetime.utcnow())
            .returning(User)
        )

        result = await db.execute(query)
        restored_user = result.scalar_one_or_none()

        if restored_user:
            # Reload the user with relationships
            query_with_roles = (
                select(User).where(User.id == user_id).options(selectinload(User.roles))
            )
            result = await db.execute(query_with_roles)
            return result.scalar_one_or_none()
        return restored_user

    async def count(self, db: AsyncSession, include_deleted: bool = False) -> int:
        """Count total users"""
        query = select(User.id)

        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))

        result = await db.execute(query)
        return len(result.scalars().all())

    async def email_exists(
        self, db: AsyncSession, email: str, exclude_user_id: Optional[UUID] = None
    ) -> bool:
        """Check if email already exists (excluding soft deleted)"""
        query = select(User.id).where(
            and_(User.email == email, User.deleted_at.is_(None))
        )

        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def authenticate(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user for authentication (returns user with password_hash)"""
        query = (
            select(User)
            .where(and_(User.email == email, User.deleted_at.is_(None)))
            .options(selectinload(User.roles))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
