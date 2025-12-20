from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserRoleRead,
)


class RoleService:
    def __init__(self):
        self.repo = RoleRepository()

    async def create_role(self, db: AsyncSession, role_in: RoleCreate) -> RoleRead:
        """Create a new role"""
        # Check if role name already exists
        if await self.repo.name_exists(db, role_in.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role name already exists",
            )

        role = await self.repo.create(db, role_in)
        await db.commit()
        return RoleRead.model_validate(role)

    async def get_role(self, db: AsyncSession, role_id: UUID) -> RoleRead:
        """Get role by ID"""
        role = await self.repo.get_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )
        return RoleRead.model_validate(role)

    async def get_role_by_name(self, db: AsyncSession, name: str) -> RoleRead:
        """Get role by name"""
        role = await self.repo.get_by_name(db, name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )
        return RoleRead.model_validate(role)

    async def get_all_roles(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> List[RoleRead]:
        """Get all roles with pagination"""
        roles = await self.repo.get_all(db, skip, limit, include_deleted)
        return [RoleRead.model_validate(role) for role in roles]

    async def update_role(
        self, db: AsyncSession, role_id: UUID, role_update: RoleUpdate
    ) -> RoleRead:
        """Update role"""
        # Check if role exists
        existing_role = await self.repo.get_by_id(db, role_id)
        if not existing_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        # Check if name is being updated and already exists
        if role_update.name and role_update.name != existing_role.name:
            if await self.repo.name_exists(
                db, role_update.name, exclude_role_id=role_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Role name already exists",
                )

        role = await self.repo.update(db, role_id, role_update)
        await db.commit()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found after update",
            )

        return RoleRead.model_validate(role)

    async def delete_role(self, db: AsyncSession, role_id: UUID) -> dict:
        """Soft delete role"""
        role = await self.repo.get_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        success = await self.repo.soft_delete(db, role_id)
        await db.commit()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete role",
            )

        return {"message": "Role deleted successfully"}

    async def permanently_delete_role(self, db: AsyncSession, role_id: UUID) -> dict:
        """Permanently delete role (use with caution)"""
        role = await self.repo.get_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        success = await self.repo.hard_delete(db, role_id)
        await db.commit()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to permanently delete role",
            )

        return {"message": "Role permanently deleted"}

    async def restore_role(self, db: AsyncSession, role_id: UUID) -> RoleRead:
        """Restore a soft-deleted role"""
        role = await self.repo.restore(db, role_id)
        await db.commit()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found or not deleted",
            )

        return RoleRead.model_validate(role)

    async def assign_role_to_user(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> UserRoleRead:
        """Assign a role to a user"""
        # Check if role exists
        role = await self.repo.get_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        # Check if user exists
        from app.modules.users.repository import UserRepository

        user_repo = UserRepository()
        user = await user_repo.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Check if assignment already exists
        existing_assignment = await self.repo.get_user_role_assignment(
            db, user_id, role_id
        )
        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has this role",
            )

        user_role = await self.repo.assign_role_to_user(db, user_id, role_id)
        await db.commit()
        return UserRoleRead.model_validate(user_role)

    async def remove_role_from_user(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> dict:
        """Remove a role from a user"""
        # Check if assignment exists
        existing_assignment = await self.repo.get_user_role_assignment(
            db, user_id, role_id
        )
        if not existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not have this role",
            )

        success = await self.repo.remove_role_from_user(db, user_id, role_id)
        await db.commit()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove role from user",
            )

        return {"message": "Role removed from user successfully"}

    async def get_roles_for_user(
        self, db: AsyncSession, user_id: UUID
    ) -> List[RoleRead]:
        """Get all roles assigned to a user"""
        # Check if user exists
        from app.modules.users.repository import UserRepository

        user_repo = UserRepository()
        user = await user_repo.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        roles = await self.repo.get_roles_for_user(db, user_id)
        return [RoleRead.model_validate(role) for role in roles]

    async def get_users_for_role(self, db: AsyncSession, role_id: UUID):
        """Get all users assigned to a role"""
        # Check if role exists
        role = await self.repo.get_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        users = await self.repo.get_users_for_role(db, role_id)

        # Import UserRead here to avoid circular imports
        from app.modules.users.schemas import UserRead

        return [UserRead.model_validate(user) for user in users]

    async def user_has_role(
        self, db: AsyncSession, user_id: UUID, role_name: str
    ) -> bool:
        """Check if a user has a specific role by name"""
        return await self.repo.user_has_role(db, user_id, role_name)

    async def get_role_count(
        self, db: AsyncSession, include_deleted: bool = False
    ) -> dict:
        """Get total role count"""
        count = await self.repo.count(db, include_deleted)
        return {"total_roles": count}
