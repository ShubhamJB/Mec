"""
Pydantic schemas for notification endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import NotificationType


class NotificationRead(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    notification_type: NotificationType
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int


class ReadAllResponse(BaseModel):
    updated_count: int
