import uuid
from datetime import datetime, timezone

from app.main import app
from app.models.enums import NotificationType
from app.schemas.notification import NotificationRead, ReadAllResponse, UnreadCountResponse


def test_notification_read_schema():
    n = NotificationRead(
        id=uuid.uuid4(),
        title="Garage registration approved",
        message="Approved.",
        notification_type=NotificationType.REGISTRATION_APPROVED,
        related_entity_type="GARAGE",
        related_entity_id=uuid.uuid4(),
        is_read=False,
        read_at=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    assert n.is_read is False


def test_count_schemas():
    assert UnreadCountResponse(unread_count=3).unread_count == 3
    assert ReadAllResponse(updated_count=2).updated_count == 2


def test_notification_routes_registered():
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/notifications"]
    assert "get" in paths["/api/v1/notifications/unread-count"]
    assert "patch" in paths["/api/v1/notifications/read-all"]
    assert "patch" in paths["/api/v1/notifications/{notification_id}/read"]
    assert "delete" in paths["/api/v1/notifications/{notification_id}"]
