from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RoleRead(RoleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserRoleBase(BaseModel):
    user_id: UUID
    role_id: UUID


class UserRoleCreate(UserRoleBase):
    pass


class UserRoleRead(UserRoleBase):
    assigned_at: datetime

    class Config:
        from_attributes = True


class RoleAssignment(BaseModel):
    role_id: UUID


class UserRoleAssignment(BaseModel):
    user_id: UUID
    role_id: UUID
