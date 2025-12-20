from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.roles.schemas import (
    RoleCreate,
    RoleRead,
    UserRoleRead,
)
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


# Temporarily disabled for testing
# @router.get("/me", response_model=UserRead)
# async def get_current_user_info(
#     current_user: User = Depends(get_current_user),
# ):
#     """Get current authenticated user information"""
#     return UserRead.model_validate(current_user)


@router.get("/", response_model=List[UserRead])
async def get_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    include_deleted: bool = Query(False, description="Include soft-deleted users"),
    db: AsyncSession = Depends(get_db),
):
    """Get all users with pagination"""
    return await user_service.get_users(db, skip, limit, include_deleted)


@router.get("/count")
async def get_user_count(
    include_deleted: bool = Query(
        False, description="Include soft-deleted users in count"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get total user count"""
    return await user_service.get_user_count(db, include_deleted)


@router.get("/{user_id}", response_model=UserRead)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID"""
    return await user_service.get_user(db, user_id)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update user by ID"""
    return await user_service.update_user(db, user_id, user_update)


# Temporarily disabled for testing
# @router.patch("/me", response_model=UserRead)
# async def update_current_user(
#     user_update: UserUpdate,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     """Update current authenticated user"""
#     return await user_service.update_user(db, current_user.id, user_update)


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete user by ID"""
    return await user_service.delete_user(db, user_id)


# Temporarily disabled for testing
# @router.delete("/me")
# async def delete_current_user(
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     """Delete current authenticated user account"""
#     return await user_service.delete_user(db, current_user.id)


@router.post("/{user_id}/restore", response_model=UserRead)
async def restore_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restore a soft-deleted user"""
    return await user_service.restore_user(db, user_id)


@router.delete("/{user_id}/permanent")
async def permanently_delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete user (use with extreme caution)"""
    return await user_service.permanently_delete_user(db, user_id)


# Temporarily disabled - needs user_id parameter for testing
# @router.post("/change-password")
# async def change_password(
#     password_data: UserPasswordUpdate,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     """Change current user's password"""
#     return await user_service.change_password(db, current_user.id, password_data)


@router.post("/{user_id}/change-password")
async def change_user_password(
    user_id: UUID,
    password_data: UserPasswordUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Change user password by user ID"""
    return await user_service.change_password(db, user_id, password_data)


@router.get("/email/{email}", response_model=UserRead)
async def get_user_by_email(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """Get user by email"""
    return await user_service.get_user_by_email(db, email)


# ==========================
# Role Management Endpoints
# ==========================


@router.post("/roles/", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new role"""
    return await user_service.create_role(db, role_in)


@router.get("/roles/", response_model=List[RoleRead])
async def list_roles(
    db: AsyncSession = Depends(get_db),
):
    """List all roles"""
    return await user_service.get_all_roles(db)


@router.post("/{user_id}/roles/{role_id}", response_model=UserRoleRead)
async def assign_role_to_user(
    user_id: UUID,
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Assign a role to a user"""
    return await user_service.assign_role_to_user(db, user_id, role_id)


@router.delete("/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a role from a user"""
    return await user_service.remove_role_from_user(db, user_id, role_id)


@router.get("/{user_id}/roles", response_model=List[RoleRead])
async def get_roles_for_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all roles assigned to a user"""
    return await user_service.get_roles_for_user(db, user_id)


@router.get("/roles/{role_id}/users", response_model=List[UserRead])
async def get_users_for_role(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all users assigned to a role"""
    return await user_service.get_users_for_role(db, role_id)


@router.get("/roles/{role_id}", response_model=RoleRead)
async def get_role_by_id(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get role by ID"""
    return await user_service.get_role(db, role_id)
