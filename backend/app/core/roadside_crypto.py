"""Authenticated encryption helpers for private roadside request data."""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import settings


def _fernet() -> Fernet:
    if not settings.ROADSIDE_DATA_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Roadside assistance is not configured. Set ROADSIDE_DATA_KEY.",
        )
    try:
        return Fernet(settings.ROADSIDE_DATA_KEY.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Roadside assistance encryption key is invalid.",
        ) from exc


def encrypt_private_payload(payload: dict[str, str | float]) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return _fernet().encrypt(data).decode()


def decrypt_private_payload(token: str) -> dict[str, str | float]:
    try:
        decoded = _fernet().decrypt(token.encode())
        payload = json.loads(decoded)
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Roadside private request data could not be decrypted.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Roadside private request data is invalid.",
        )
    return payload
