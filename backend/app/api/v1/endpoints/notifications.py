"""
Notification endpoints — /api/v1/notifications
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.pagination import PaginatedResponse
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.notification import NotificationRead, ReadAllResponse, UnreadCountResponse
from app.services import notification_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[NotificationRead],
    summary="List own notifications",
)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    is_read: bool | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationRead]:
    items, total = await notification_service.list_notifications(
        db=db, user_id=current_user.id, page=page, limit=limit, is_read=is_read
    )
    return PaginatedResponse.build(
        items=[NotificationRead.model_validate(i) for i in items],
        total_items=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Count own unread notifications",
)
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    count = await notification_service.get_unread_count(db=db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch(
    "/read-all",
    response_model=ReadAllResponse,
    summary="Mark all own notifications as read",
)
async def read_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReadAllResponse:
    updated = await notification_service.mark_all_read(db=db, user_id=current_user.id)
    return ReadAllResponse(updated_count=updated)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark own notification as read (idempotent)",
)
async def read_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    notification = await notification_service.mark_read(
        db=db, user_id=current_user.id, notification_id=notification_id
    )
    return NotificationRead.model_validate(notification)


@router.delete(
    "/{notification_id}",
    response_model=MessageResponse,
    summary="Delete own notification",
)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await notification_service.delete_notification(
        db=db, user_id=current_user.id, notification_id=notification_id
    )
    return MessageResponse(message="Notification deleted.")
