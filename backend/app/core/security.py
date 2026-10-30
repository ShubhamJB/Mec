"""
Password hashing and verification using modern bcrypt directly.
"""
from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Return bcrypt hash of plain password."""
    # Bcrypt truncates or raises if > 72 bytes; enforce up to 72 bytes
    pwd_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed."""
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        return False
