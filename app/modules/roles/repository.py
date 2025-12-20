from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.roles.models import Role, UserRole
from app.modules.roles.schemas import RoleCreate, RoleUpdate


class RoleRepository:
    async def get_by_id(self, db: AsyncSession, role_id: UUID) -> Optional[Role]:
        """Get role by ID (excluding soft deleted)"""
        query = select(Role).where(and_(Role.id == role_id, Role.deleted_at.is_(None)))
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[Role]:
        """Get role by name (excluding soft deleted)"""
        query = select(Role).where(and_(Role.name == name, Role.deleted_at.is_(None)))
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> List[Role]:
        """Get all roles with pagination"""
        query = select(Role)

        if not include_deleted:
            query = query.where(Role.deleted_at.is_(None))

        query = query.offset(skip).limit(limit).order_by(Role.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, role_in: RoleCreate) -> Role:
        """Create a new role"""
        role = Role(name=role_in.name, description=role_in.description)
        db.add(role)
        await db.flush()
        await db.refresh(role)
        return role

    async def update(
        self, db: AsyncSession, role_id: UUID, role_update: RoleUpdate
    ) -> Optional[Role]:
        """Update role by ID"""
        # Build update data
        update_data = {}
        if role_update.name is not None:
            update_data["name"] = role_update.name
        if role_update.description is not None:
            update_data["description"] = role_update.description

        if not update_data:
            # No updates to make, return current role
            return await self.get_by_id(db, role_id)

        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(Role)
            .where(and_(Role.id == role_id, Role.deleted_at.is_(None)))
            .values(**update_data)
            .returning(Role)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def soft_delete(self, db: AsyncSession, role_id: UUID) -> bool:
        """Soft delete role by setting deleted_at timestamp"""
        # First check if role exists
        role = await self.get_by_id(db, role_id)
        if not role:
            return False

        query = (
            update(Role)
            .where(and_(Role.id == role_id, Role.deleted_at.is_(None)))
            .values(deleted_at=datetime.utcnow())
        )

        await db.execute(query)
        await db.flush()
        return True

    async def hard_delete(self, db: AsyncSession, role_id: UUID) -> bool:
        """Permanently delete role (use with caution)"""
        role = await self.get_by_id(db, role_id)
        if role:
            await db.delete(role)
            return True
        return False

    async def restore(self, db: AsyncSession, role_id: UUID) -> Optional[Role]:
        """Restore a soft-deleted role"""
        query = (
            update(Role)
            .where(and_(Role.id == role_id, Role.deleted_at.is_not(None)))
            .values(deleted_at=None, updated_at=datetime.utcnow())
            .returning(Role)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count(self, db: AsyncSession, include_deleted: bool = False) -> int:
        """Count total roles"""
        query = select(Role.id)

        if not include_deleted:
            query = query.where(Role.deleted_at.is_(None))

        result = await db.execute(query)
        return len(result.scalars().all())

    async def name_exists(
        self, db: AsyncSession, name: str, exclude_role_id: Optional[UUID] = None
    ) -> bool:
        """Check if role name already exists (excluding soft deleted)"""
        query = select(Role.id).where(
            and_(Role.name == name, Role.deleted_at.is_(None))
        )

        if exclude_role_id:
            query = query.where(Role.id != exclude_role_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def assign_role_to_user(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> UserRole:
        """Assign a role to a user"""
        user_role = UserRole(
            user_id=user_id, role_id=role_id, assigned_at=datetime.utcnow()
        )
        db.add(user_role)
        await db.flush()
        await db.refresh(user_role)
        return user_role

    async def remove_role_from_user(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> bool:
        """Remove a role from a user"""
        # First check if assignment exists
        assignment = await self.get_user_role_assignment(db, user_id, role_id)
        if not assignment:
            return False

        query = delete(UserRole).where(
            and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        await db.execute(query)
        await db.flush()
        return True

    async def get_user_role_assignment(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> Optional[UserRole]:
        """Get a specific user-role assignment"""
        query = select(UserRole).where(
            and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_roles_for_user(self, db: AsyncSession, user_id: UUID) -> List[Role]:
        """Get all roles assigned to a user"""
        query = (
            select(Role)
            .join(UserRole, Role.id == UserRole.role_id)
            .where(and_(UserRole.user_id == user_id, Role.deleted_at.is_(None)))
            .order_by(Role.name)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_users_for_role(self, db: AsyncSession, role_id: UUID):
        """Get all users assigned to a role"""
        # We'll import User here to avoid circular imports
        from app.modules.users.models import User

        query = (
            select(User)
            .join(UserRole, User.id == UserRole.user_id)
            .where(and_(UserRole.role_id == role_id, User.deleted_at.is_(None)))
            .options(selectinload(User.roles))
            .order_by(User.email)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def user_has_role(
        self, db: AsyncSession, user_id: UUID, role_name: str
    ) -> bool:
        """Check if a user has a specific role by name"""
        query = (
            select(UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(
                and_(
                    UserRole.user_id == user_id,
                    Role.name == role_name,
                    Role.deleted_at.is_(None),
                )
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None
