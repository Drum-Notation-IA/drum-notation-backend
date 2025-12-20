from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.roles.schemas import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserRoleRead,
)
from app.modules.roles.service import RoleService

router = APIRouter(prefix="/roles", tags=["roles"])
role_service = RoleService()


@router.post("/", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new role"""
    return await role_service.create_role(db, role_in)


@router.get("/", response_model=List[RoleRead])
async def get_roles(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    include_deleted: bool = Query(False, description="Include soft-deleted roles"),
    db: AsyncSession = Depends(get_db),
):
    """Get all roles with pagination"""
    return await role_service.get_all_roles(db, skip, limit, include_deleted)


@router.get("/count")
async def get_role_count(
    include_deleted: bool = Query(
        False, description="Include soft-deleted roles in count"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get total role count"""
    return await role_service.get_role_count(db, include_deleted)


@router.get("/{role_id}", response_model=RoleRead)
async def get_role_by_id(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get role by ID"""
    return await role_service.get_role(db, role_id)


@router.get("/name/{role_name}", response_model=RoleRead)
async def get_role_by_name(
    role_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get role by name"""
    return await role_service.get_role_by_name(db, role_name)


@router.put("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: UUID,
    role_update: RoleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update role by ID"""
    return await role_service.update_role(db, role_id, role_update)


@router.delete("/{role_id}")
async def delete_role(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete role by ID"""
    return await role_service.delete_role(db, role_id)


@router.post("/{role_id}/restore", response_model=RoleRead)
async def restore_role(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Restore a soft-deleted role"""
    return await role_service.restore_role(db, role_id)


@router.delete("/{role_id}/permanent")
async def permanently_delete_role(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete role (use with extreme caution)"""
    return await role_service.permanently_delete_role(db, role_id)


# ==========================
# User-Role Management Endpoints
# ==========================


@router.post("/{role_id}/users/{user_id}", response_model=UserRoleRead)
async def assign_role_to_user(
    role_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Assign a role to a user"""
    return await role_service.assign_role_to_user(db, user_id, role_id)


@router.delete("/{role_id}/users/{user_id}")
async def remove_role_from_user(
    role_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a role from a user"""
    return await role_service.remove_role_from_user(db, user_id, role_id)


@router.get("/{role_id}/users")
async def get_users_for_role(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all users assigned to a role"""
    return await role_service.get_users_for_role(db, role_id)


@router.get("/users/{user_id}", response_model=List[RoleRead])
async def get_roles_for_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all roles assigned to a user"""
    return await role_service.get_roles_for_user(db, user_id)


@router.get("/users/{user_id}/check/{role_name}")
async def check_user_has_role(
    user_id: UUID,
    role_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if a user has a specific role"""
    has_role = await role_service.user_has_role(db, user_id, role_name)
    return {"user_id": user_id, "role_name": role_name, "has_role": has_role}
