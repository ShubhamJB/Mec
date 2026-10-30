"""
User profile endpoints — /api/v1/users
GET /users/me, PATCH /users/me, PATCH /users/me/password
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import ChangePasswordRequest, UpdateProfileRequest, UserProfileResponse
from app.services import auth_service

router = APIRouter()


# ── GET /users/me ─────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get own profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user)


# ── PATCH /users/me ───────────────────────────────────────────────────────────
@router.patch(
    "/me",
    response_model=UserProfileResponse,
    summary="Update own profile (name only)",
)
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    current_user.full_name = body.full_name
    await db.flush()
    return UserProfileResponse.model_validate(current_user)


# ── PATCH /users/me/password ──────────────────────────────────────────────────
@router.patch(
    "/me/password",
    response_model=MessageResponse,
    summary="Change password (requires current password; revokes all sessions)",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.change_password(
        db=db,
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return MessageResponse(
        message="Password changed successfully. All sessions have been signed out."
    )
