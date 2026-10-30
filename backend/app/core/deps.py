"""
FastAPI dependency: resolve the currently authenticated user from the
Bearer JWT access token in the Authorization header.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.models.enums import AccountStatus, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

# ── Errors ────────────────────────────────────────────────────────────────────
_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)
_403_suspended = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Account is suspended.",
)


async def _get_user_from_token(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> User:
    if credentials is None:
        raise _401
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        token_type: str = payload.get("type", "")
    except JWTError:
        raise _401

    if token_type != "access" or not user_id:
        raise _401

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise _401
    return user


# ── Public dependency: any authenticated user ─────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _get_user_from_token(credentials, db)
    if user.account_status == AccountStatus.SUSPENDED:
        raise _403_suspended
    return user


# ── Optional auth: returns None for unauthenticated requests ──────────────────
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return await _get_user_from_token(credentials, db)
    except HTTPException:
        return None


# ── Role-specific dependencies ────────────────────────────────────────────────
async def require_customer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Customer access required.")
    if not current_user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified.")
    return current_user


async def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.GARAGE_OWNER:
        raise HTTPException(status_code=403, detail="Garage owner access required.")
    if not current_user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified.")
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


async def require_verified_owner(current_user: User = Depends(get_current_user)) -> User:
    """Owner who has verified their email."""
    return await require_owner(current_user)

