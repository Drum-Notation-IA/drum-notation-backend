from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.password_utils import validate_password_length


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        is_valid, errors = validate_password_length(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if v is not None:
            is_valid, errors = validate_password_length(v)
            if not is_valid:
                raise ValueError("; ".join(errors))
        return v


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    roles: List["RoleRead"] = []  # Forward reference to avoid circular imports

    class Config:
        from_attributes = True


class UserInDB(UserRead):
    password_hash: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        is_valid, errors = validate_password_length(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v


class UserPasswordUpdate(BaseModel):
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_passwords(cls, v):
        is_valid, errors = validate_password_length(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Import at the end to avoid circular imports
from app.modules.roles.schemas import RoleRead, UserRoleRead

# Update forward reference
UserRead.model_rebuild()
