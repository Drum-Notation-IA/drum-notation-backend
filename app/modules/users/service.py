from datetime import timedelta
from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.modules.roles.schemas import RoleCreate, RoleRead, UserRoleRead
from app.modules.roles.service import RoleService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    Token,
    UserCreate,
    UserLogin,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
)


class UserService:
    def __init__(self):
        self.repo = UserRepository()
        self.role_service = RoleService()

    async def create_user(self, db: AsyncSession, user_in: UserCreate) -> UserRead:
        """Create a new user"""
        # Check if email already exists
        if await self.repo.email_exists(db, user_in.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        user = await self.repo.create(db, user_in)
        await db.commit()
        return UserRead.model_validate(user)

    async def get_user(self, db: AsyncSession, user_id: UUID) -> UserRead:
        """Get user by ID"""
        user = await self.repo.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserRead.model_validate(user)

    async def get_user_by_email(self, db: AsyncSession, email: str) -> UserRead:
        """Get user by email"""
        user = await self.repo.get_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserRead.model_validate(user)

    async def get_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> List[UserRead]:
        """Get all users with pagination"""
        users = await self.repo.get_all(db, skip, limit, include_deleted)
        return [UserRead.model_validate(user) for user in users]

    async def update_user(
        self, db: AsyncSession, user_id: UUID, user_update: UserUpdate
    ) -> UserRead:
        """Update user"""
        # Check if user exists
        existing_user = await self.repo.get_by_id(db, user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Check if email is being updated and already exists
        if user_update.email and user_update.email != existing_user.email:
            if await self.repo.email_exists(
                db, user_update.email, exclude_user_id=user_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        user = await self.repo.update(db, user_id, user_update)
        await db.commit()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found after update",
            )

        return UserRead.model_validate(user)

    async def delete_user(self, db: AsyncSession, user_id: UUID) -> dict:
        """Soft delete user"""
        user = await self.repo.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        success = await self.repo.soft_delete(db, user_id)
        await db.commit()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete user",
            )

        return {"message": "User deleted successfully"}

    async def permanently_delete_user(self, db: AsyncSession, user_id: UUID) -> dict:
        """Permanently delete user (use with caution)"""
        user = await self.repo.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        success = await self.repo.hard_delete(db, user_id)
        await db.commit()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to permanently delete user",
            )

        return {"message": "User permanently deleted"}

    async def restore_user(self, db: AsyncSession, user_id: UUID) -> UserRead:
        """Restore a soft-deleted user"""
        user = await self.repo.restore(db, user_id)
        await db.commit()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or not deleted",
            )

        return UserRead.model_validate(user)

    async def authenticate_user(self, db: AsyncSession, login_data: UserLogin) -> Token:
        """Authenticate user and return JWT token"""
        user = await self.repo.authenticate(db, login_data.email)

        if not user or not verify_password(
            login_data.password, str(user.password_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        return Token(access_token=access_token, token_type="bearer")

    async def change_password(
        self, db: AsyncSession, user_id: UUID, password_data: UserPasswordUpdate
    ) -> dict:
        """Change user password"""
        user = await self.repo.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Verify current password
        if not verify_password(password_data.current_password, str(user.password_hash)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password",
            )

        # Update password
        user_update = UserUpdate(password=password_data.new_password)
        await self.repo.update(db, user_id, user_update)
        await db.commit()

        return {"message": "Password updated successfully"}

    async def get_user_count(
        self, db: AsyncSession, include_deleted: bool = False
    ) -> dict:
        """Get total user count"""
        count = await self.repo.count(db, include_deleted)
        return {"total_users": count}

    async def get_current_user_from_token(self, db: AsyncSession, email: str) -> User:
        """Get current user from JWT token email"""
        user = await self.repo.get_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    # ==========================
    # Role Management Methods
    # ==========================

    async def create_role(self, db: AsyncSession, role_in: RoleCreate) -> RoleRead:
        """Create a new role"""
        return await self.role_service.create_role(db, role_in)

    async def get_all_roles(self, db: AsyncSession) -> List[RoleRead]:
        """Get all roles"""
        return await self.role_service.get_all_roles(db)

    async def get_role(self, db: AsyncSession, role_id: UUID) -> RoleRead:
        """Get role by ID"""
        return await self.role_service.get_role(db, role_id)

    async def assign_role_to_user(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> UserRoleRead:
        """Assign a role to a user"""
        return await self.role_service.assign_role_to_user(db, user_id, role_id)

    async def remove_role_from_user(
        self, db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> dict:
        """Remove a role from a user"""
        return await self.role_service.remove_role_from_user(db, user_id, role_id)

    async def get_roles_for_user(
        self, db: AsyncSession, user_id: UUID
    ) -> List[RoleRead]:
        """Get all roles assigned to a user"""
        return await self.role_service.get_roles_for_user(db, user_id)

    async def get_users_for_role(self, db: AsyncSession, role_id: UUID):
        """Get all users assigned to a role"""
        return await self.role_service.get_users_for_role(db, role_id)
