"""
JWT access-token creation/decoding and refresh-token helpers.

Access tokens  — short-lived JWT (HS256), never stored server-side.
Refresh tokens — opaque random bytes; only the SHA-256 hash is stored.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings

# ── Access tokens ─────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,          # user UUID as string
    role: str,
    extra_claims: dict | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Raises jose.JWTError on any failure.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Refresh tokens ────────────────────────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    """
    Generate a cryptographically secure refresh token.
    Returns (raw_token, sha256_hash).
    raw_token is sent to the client; only the hash is persisted.
    """
    raw = secrets.token_urlsafe(64)
    hashed = _hash_token(raw)
    return raw, hashed


def hash_refresh_token(raw: str) -> str:
    """Hash a raw refresh token for DB lookup."""
    return _hash_token(raw)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Email-verification tokens ─────────────────────────────────────────────────

def generate_email_verification_token() -> tuple[str, str]:
    """
    Generate a URL-safe verification token.
    Returns (raw_token, sha256_hash).
    """
    raw = secrets.token_urlsafe(48)
    hashed = _hash_token(raw)
    return raw, hashed

