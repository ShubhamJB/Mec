"""
Auth service — all auth business logic lives here.
Endpoints are thin; this module is testable without HTTP.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.jwt import (
    _hash_token,
    create_access_token,
    generate_email_verification_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.security import hash_password, verify_password
from app.models.enums import AccountStatus, UserRole
from app.models.token import EmailVerificationToken, RefreshToken
from app.models.user import User
from app.utils.email import send_verification_email


# ── Registration ──────────────────────────────────────────────────────────────

async def register_user(
    *,
    db: AsyncSession,
    full_name: str,
    email: str,
    password: str,
    role: UserRole,
) -> User:
    """Create a new user. Raises 409 if email already exists."""
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        email_verified=False,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()  # get user.id before creating token

    # Create and send email verification token
    await _create_and_send_verification_token(db=db, user=user)

    return user


# ── Email verification ────────────────────────────────────────────────────────

async def _create_and_send_verification_token(
    *, db: AsyncSession, user: User
) -> None:
    """Revoke old tokens, create a new one, send email."""
    # Revoke any unexpired existing tokens for this user
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(tz=timezone.utc))
    )

    raw_token, token_hash = generate_email_verification_token()
    evt = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=24),
    )
    db.add(evt)

    await send_verification_email(
        to=user.email,
        token=raw_token,
        full_name=user.full_name,
    )


async def verify_email(*, db: AsyncSession, raw_token: str) -> None:
    """Verify email with the raw token. Raises 400/404 on invalid."""
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Verification token not found.")

    now = datetime.now(tz=timezone.utc)
    if record.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used.")
    if record.revoked_at is not None:
        raise HTTPException(status_code=400, detail="Token has been revoked.")
    if record.expires_at < now:
        raise HTTPException(status_code=400, detail="Token has expired.")

    # Mark token used and user verified
    record.used_at = now
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one()
    user.email_verified = True


async def resend_verification(*, db: AsyncSession, email: str) -> None:
    """
    Resend verification email. Generic response to avoid enumeration.
    Only sends if the user exists, is unverified, and is active.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Silently succeed if user not found (anti-enumeration)
    if user and not user.email_verified and user.account_status == AccountStatus.ACTIVE:
        await _create_and_send_verification_token(db=db, user=user)


# ── Login ─────────────────────────────────────────────────────────────────────

async def login(
    *,
    db: AsyncSession,
    email: str,
    password: str,
    device_info: str | None = None,
) -> tuple[str, str]:
    """
    Authenticate user and return (access_token, raw_refresh_token).
    Raises 401/403 on failure.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EMAIL_NOT_VERIFIED",
        )
    if user.account_status == AccountStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ACCOUNT_SUSPENDED",
        )

    access_token = create_access_token(subject=str(user.id), role=user.role.value)
    raw_refresh, refresh_hash = generate_refresh_token()

    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(tz=timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        device_info=device_info,
    )
    db.add(rt)

    return access_token, raw_refresh


# ── Token refresh ─────────────────────────────────────────────────────────────

async def refresh_tokens(
    *,
    db: AsyncSession,
    raw_refresh_token: str,
) -> tuple[str, str]:
    """
    Validate old refresh token, rotate it, return (new_access, new_raw_refresh).
    Raises 401/403 on invalid token.
    """
    token_hash = hash_refresh_token(raw_refresh_token)

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if record is None or not record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    # Load user
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or user.account_status == AccountStatus.SUSPENDED:
        raise HTTPException(status_code=403, detail="Account is suspended.")

    # Revoke old token
    record.revoked_at = datetime.now(tz=timezone.utc)

    # Issue new tokens
    new_access = create_access_token(subject=str(user.id), role=user.role.value)
    new_raw_refresh, new_hash = generate_refresh_token()

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=datetime.now(tz=timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        device_info=record.device_info,
    )
    db.add(new_rt)

    return new_access, new_raw_refresh


# ── Logout ────────────────────────────────────────────────────────────────────

async def logout(*, db: AsyncSession, raw_refresh_token: str) -> None:
    """Revoke the current refresh session."""
    token_hash = hash_refresh_token(raw_refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(tz=timezone.utc)


async def logout_all(*, db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke all active refresh sessions for this user."""
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(tz=timezone.utc))
    )


# ── Password change ───────────────────────────────────────────────────────────

async def change_password(
    *,
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Verify current password, set new hash, revoke all sessions."""
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    user.password_hash = hash_password(new_password)
    await logout_all(db=db, user_id=user.id)

    from app.utils.email import send_password_changed_email
    await send_password_changed_email(to=user.email, full_name=user.full_name)
