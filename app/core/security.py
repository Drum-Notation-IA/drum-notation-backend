from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.password_utils import is_bcrypt_compatible, truncate_for_bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Handles bcrypt's 72-byte limitation by truncating if necessary.
    """
    # Handle bcrypt 72-byte limit
    if not is_bcrypt_compatible(password):
        password = truncate_for_bcrypt(password)

    # Convert to bytes for bcrypt
    password_bytes = password.encode("utf-8")

    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string for database storage
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Handles the same 72-byte truncation as hash_password.
    """
    try:
        # Apply same truncation as hash_password
        if not is_bcrypt_compatible(plain_password):
            plain_password = truncate_for_bcrypt(plain_password)

        # Convert to bytes for bcrypt
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")

        # Verify password
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
