"""Security utilities for the 2FA / OTP module.

Includes:
- Cryptographically-secure OTP generation
- SHA-256 hashing helpers (peppered with the application SECRET_KEY)
- Constant-time comparison
- Lightweight in-memory async rate limiter
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from app.core.config import settings


# ---------------------------------------------------------------------------
# OTP & token generation
# ---------------------------------------------------------------------------

def generate_numeric_otp(length: int | None = None) -> str:
    """Generate a cryptographically-secure numeric OTP.

    Uses `secrets.randbelow` per digit to avoid modulo bias.
    Returns a zero-padded string of the requested length.
    """
    n = length if length is not None else settings.OTP_LENGTH
    if n < 4 or n > 10:
        raise ValueError("OTP length must be between 4 and 10")
    return "".join(str(secrets.randbelow(10)) for _ in range(n))


def generate_challenge_token() -> str:
    """Generate a 32-byte URL-safe random token for the temporary 2FA challenge."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def _pepper() -> bytes:
    """Server-side pepper used to harden OTP hashes against DB-only leaks."""
    return settings.SECRET_KEY.encode("utf-8")


def hash_otp(otp: str) -> str:
    """Hash an OTP using SHA-256 with a server-side pepper.

    A simple SHA-256 is sufficient because:
    - The OTP is short-lived (minutes) and rate-limited.
    - The pepper makes pre-image attacks impractical without the SECRET_KEY.
    - bcrypt would be overkill here and adds latency to every verify call.
    """
    h = hashlib.sha256()
    h.update(_pepper())
    h.update(b":otp:")
    h.update(otp.encode("utf-8"))
    return h.hexdigest()


def hash_challenge_token(token: str) -> str:
    """Hash a challenge token (no pepper required: it's a 256-bit random value)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ---------------------------------------------------------------------------
# In-memory async rate limiter
# ---------------------------------------------------------------------------

class InMemoryRateLimiter:
    """Sliding-window counter, safe for concurrent coroutines.

    NOTE: This is process-local. For multi-worker deployments (e.g. multiple
    Uvicorn workers or k8s replicas) replace with a Redis-backed limiter.
    The interface is intentionally compatible with a future Redis impl.
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """Register a hit and report whether the request is allowed.

        Returns (allowed, remaining_seconds_until_reset).
        """
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                # Wait time until the oldest hit ages out of the window
                wait = int(window_seconds - (now - bucket[0])) + 1
                return False, max(wait, 1)
            bucket.append(now)
            return True, 0

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._buckets.pop(key, None)


# Singleton limiters used by the auth router
login_rate_limiter = InMemoryRateLimiter()
verify_rate_limiter = InMemoryRateLimiter()
