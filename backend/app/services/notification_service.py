"""
Service layer for in-app notifications (with best-effort email delivery).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AccountStatus, NotificationType, UserRole
from app.models.notification import Notification
from app.models.user import User
from app.utils.email import send_email


async def notify_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
    also_email: bool = False,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    db.add(notification)
    await db.flush()

    if also_email:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is not None:
            await send_email(
                to=user.email,
                subject=f"{title} — Find Your Mechanic",
                html_body=f"<p>Hi {user.full_name},</p><p>{message}</p>",
            )
    return notification


async def notify_admins(
    db: AsyncSession,
    notification_type: NotificationType,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
) -> None:
    admin_ids = (
        await db.execute(
            select(User.id).where(
                User.role == UserRole.ADMIN,
                User.account_status == AccountStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for admin_id in admin_ids:
        await notify_user(
            db=db,
            user_id=admin_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int,
    limit: int,
    is_read: bool | None,
) -> tuple[list[Notification], int]:
    filters = [Notification.user_id == user_id]
    if is_read is not None:
        filters.append(Notification.is_read == is_read)

    total = (
        await db.execute(select(func.count(Notification.id)).where(*filters))
    ).scalar_one()
    rows = list(
        (
            await db.execute(
                select(Notification)
                .where(*filters)
                .order_by(Notification.created_at.desc(), Notification.id)
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
    )
    return rows, total


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
    ).scalar_one()


async def _get_own_notification(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return notification


async def mark_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    notification = await _get_own_notification(db, user_id, notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(tz=timezone.utc)
        await db.flush()
    return notification


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(tz=timezone.utc))
    )
    return result.rowcount or 0


async def delete_notification(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> None:
    notification = await _get_own_notification(db, user_id, notification_id)
    await db.delete(notification)
    await db.flush()
