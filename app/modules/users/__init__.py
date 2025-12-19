"""
Users module for drum notation backend.

This module handles all user-related operations including:
- User registration and authentication
- CRUD operations for user management
- JWT token-based authentication
- Password management
"""

from .models import User
from .repository import UserRepository
from .schemas import (
    Token,
    TokenData,
    UserBase,
    UserCreate,
    UserInDB,
    UserLogin,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
)
from .service import UserService

__all__ = [
    # Models
    "User",
    # Schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserRead",
    "UserInDB",
    "UserLogin",
    "UserPasswordUpdate",
    "Token",
    "TokenData",
    # Repository
    "UserRepository",
    # Service
    "UserService",
]
