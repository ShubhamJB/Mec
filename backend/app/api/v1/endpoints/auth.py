"""
Auth endpoints — /api/v1/auth
All 8 routes from the API design.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    UserBrief,
    VerifyEmailRequest,
)
from app.services import auth_service

router = APIRouter()


# ── POST /auth/register/customer ──────────────────────────────────────────────
@router.post(
    "/register/customer",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer account",
)
async def register_customer(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    user = await auth_service.register_user(
        db=db,
        full_name=body.full_name,
        email=body.email,
        password=body.password,
        role=UserRole.CUSTOMER,
    )
    return RegisterResponse(
        message="Registration successful. Please check your email to verify your account.",
        user=UserBrief.model_validate(user),
    )


# ── POST /auth/register/owner ─────────────────────────────────────────────────
@router.post(
    "/register/owner",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new garage owner account",
)
async def register_owner(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    user = await auth_service.register_user(
        db=db,
        full_name=body.full_name,
        email=body.email,
        password=body.password,
        role=UserRole.GARAGE_OWNER,
    )
    return RegisterResponse(
        message="Registration successful. Please check your email to verify your account.",
        user=UserBrief.model_validate(user),
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    device_info = request.headers.get("User-Agent", "")[:500]
    access_token, raw_refresh = await auth_service.login(
        db=db,
        email=body.email,
        password=body.password,
        device_info=device_info,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and get new access token",
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    new_access, new_refresh = await auth_service.refresh_tokens(
        db=db,
        raw_refresh_token=body.refresh_token,
    )
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── POST /auth/logout ─────────────────────────────────────────────────────────
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke current refresh session",
)
async def logout(
    body: RefreshRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout(db=db, raw_refresh_token=body.refresh_token)
    return MessageResponse(message="Logged out successfully.")


# ── POST /auth/logout-all ─────────────────────────────────────────────────────
@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Revoke all refresh sessions",
)
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout_all(db=db, user_id=current_user.id)
    return MessageResponse(message="All sessions revoked.")


# ── POST /auth/verify-email ───────────────────────────────────────────────────
@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email address with token",
)
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.verify_email(db=db, raw_token=body.token)
    return MessageResponse(message="Email verified successfully. You can now log in.")


# ── POST /auth/resend-verification ────────────────────────────────────────────
@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend email verification link",
)
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    # Always return the same message to prevent email enumeration
    await auth_service.resend_verification(db=db, email=body.email)
    return MessageResponse(
        message="If an unverified account exists with that email, a new verification link has been sent."
    )
