"""
Essential password validation utilities for the Drum Notation Backend.
"""

import re
from typing import List, Tuple


def validate_password_length(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password length for bcrypt compatibility.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check minimum length
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long")

    # Check maximum length (bcrypt 72-byte limit)
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        errors.append("Password exceeds 72 bytes (bcrypt limitation)")

    return len(errors) == 0, errors


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Basic password strength validation.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Length check
    length_valid, length_errors = validate_password_length(password)
    errors.extend(length_errors)

    # Basic strength requirements
    if len(password) >= 6:  # Only check strength if length is valid
        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password))

        if not has_upper:
            errors.append("Password must contain at least one uppercase letter")
        if not has_lower:
            errors.append("Password must contain at least one lowercase letter")
        if not has_digit:
            errors.append("Password must contain at least one digit")
        if not has_special:
            errors.append("Password must contain at least one special character")

    return len(errors) == 0, errors


def is_bcrypt_compatible(password: str) -> bool:
    """Check if password is compatible with bcrypt (≤ 72 bytes)."""
    return len(password.encode("utf-8")) <= 72


def truncate_for_bcrypt(password: str) -> str:
    """
    Safely truncate password for bcrypt compatibility.

    Args:
        password: Original password

    Returns:
        Truncated password that fits in 72 bytes
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) <= 72:
        return password

    return password_bytes[:72].decode("utf-8", errors="ignore")
