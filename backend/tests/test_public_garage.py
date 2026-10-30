"""Unit tests for public garage schemas and privacy guarantees."""
import uuid
from datetime import datetime, time, timezone
from app.schemas.garage_profile import AvailabilityResponse
from app.schemas.garage_registration import OperatingHourItem
from app.schemas.public_garage import (
    PublicGarageProfileResponse,
    PublicOperatingHoursResponse,
)


def test_public_garage_profile_privacy_guarantee():
    profile = PublicGarageProfileResponse(
        id=uuid.uuid4(),
        name="Valley Auto Works",
        description="Full auto servicing and diagnostics.",
        phone="+9779811111111",
        address="Ring Road, Lalitpur",
        latitude=27.6710,
        longitude=85.3210,
        timezone="Asia/Kathmandu",
        average_rating=4.5,
        review_count=8,
        availability=AvailabilityResponse(
            status="OPEN",
            is_temporarily_unavailable=False,
            message=None,
            timezone="Asia/Kathmandu",
            local_time="2026-10-30T10:00:00+05:45",
            next_status_change="2026-10-30T18:00:00+05:45",
        ),
        services=[],
        vehicle_types=[],
        operating_hours=[
            OperatingHourItem(
                day_of_week=1,
                is_closed=False,
                opening_time=time(9, 0),
                closing_time=time(18, 0),
            )
        ],
        photos=[],
        created_at=datetime.now(tz=timezone.utc),
    )

    dumped = profile.model_dump()
    # Critical privacy assertions from SRS:
    assert "owner" not in dumped
    assert "owner_id" not in dumped
    assert "owner_email" not in dumped
    assert "password_hash" not in dumped
    assert "rejection_reason" not in dumped
    assert dumped["name"] == "Valley Auto Works"


def test_public_operating_hours_response():
    resp = PublicOperatingHoursResponse(
        timezone="Asia/Kathmandu",
        hours=[
            OperatingHourItem(
                day_of_week=1,
                is_closed=False,
                opening_time=time(8, 0),
                closing_time=time(17, 0),
            )
        ],
    )
    assert resp.timezone == "Asia/Kathmandu"
    assert len(resp.hours) == 1

