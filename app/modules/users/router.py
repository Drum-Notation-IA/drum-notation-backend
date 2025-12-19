from typing import List
from uuid import UUID

from app.core.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.users.models import User
from app.modules.users.schemas import (
    Token,
    UserCreate,
    UserLogin,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user"""
    return await user_service.create_user(db, user_in)


@router.post("/login", response_model=Token)
async def login_user(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login user and return JWT token"""
    return await user_service.authenticate_user(db, login_data)


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user information"""
    return UserRead.model_validate(current_user)


@router.get("/", response_model=List[UserRead])
async def get_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    include_deleted: bool = Query(False, description="Include soft-deleted users"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all users with pagination (requires authentication)"""
    return await user_service.get_users(db, skip, limit, include_deleted)


@router.get("/count")
async def get_user_count(
    include_deleted: bool = Query(
        False, description="Include soft-deleted users in count"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total user count (requires authentication)"""
    return await user_service.get_user_count(db, include_deleted)


@router.get("/{user_id}", response_model=UserRead)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user by ID (requires authentication)"""
    return await user_service.get_user(db, user_id)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user by ID (users can only update themselves unless admin)"""
    # Users can only update their own profile
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    return await user_service.update_user(db, user_id, user_update)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current authenticated user"""
    return await user_service.update_user(db, current_user.id, user_update)


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete user by ID (users can only delete themselves)"""
    # Users can only delete their own account
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user",
        )

    return await user_service.delete_user(db, user_id)


@router.delete("/me")
async def delete_current_user(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete current authenticated user account"""
    return await user_service.delete_user(db, current_user.id)


@router.post("/{user_id}/restore", response_model=UserRead)
async def restore_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a soft-deleted user (admin only - implement admin check as needed)"""
    # Note: You might want to add admin role checking here
    return await user_service.restore_user(db, user_id)


@router.delete("/{user_id}/permanent")
async def permanently_delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete user (admin only - use with extreme caution)"""
    # Note: You might want to add admin role checking here
    # This is a dangerous operation and should be restricted
    return await user_service.permanently_delete_user(db, user_id)


@router.post("/change-password")
async def change_password(
    password_data: UserPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change current user's password"""
    return await user_service.change_password(db, current_user.id, password_data)


@router.get("/email/{email}", response_model=UserRead)
async def get_user_by_email(
    email: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user by email (requires authentication)"""
    return await user_service.get_user_by_email(db, email)
