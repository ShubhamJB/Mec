"""Unit tests for availability computation and garage profile schemas."""
from datetime import time
import pytest
from pydantic import ValidationError

from app.schemas.garage_profile import (
    CreateProfileChangeRequest,
    PatchAvailabilityRequest,
    PatchOwnerGarageMinor,
    PutOperatingHoursRequest,
)
from app.schemas.garage_registration import OperatingHourItem
from app.utils.availability import calculate_garage_availability


def make_schedule():
    # 7 days, Monday to Saturday 08:00 - 18:00, Sunday closed
    items = []
    for day in range(1, 7):
        items.append({
            "day_of_week": day,
            "is_closed": False,
            "opening_time": time(8, 0),
            "closing_time": time(18, 0),
        })
    items.append({
        "day_of_week": 7,
        "is_closed": True,
        "opening_time": None,
        "closing_time": None,
    })
    return items


def test_availability_calculation_temporary_override():
    schedule = make_schedule()
    res = calculate_garage_availability(
        is_temporarily_unavailable=True,
        temporary_unavailability_message="Renovation in progress",
        timezone_str="UTC",
        operating_hours=schedule,
    )
    assert res["status"] == "TEMPORARILY_UNAVAILABLE"
    assert res["is_temporarily_unavailable"] is True
    assert res["message"] == "Renovation in progress"
    assert res["next_status_change"] is None


def test_availability_message_cleared_when_unavailable_false():
    req = PatchAvailabilityRequest(
        is_temporarily_unavailable=False,
        message="Should be wiped out",
    )
    assert req.message is None


def test_patch_minor_validation():
    # Valid phone
    p1 = PatchOwnerGarageMinor(phone="+12345678901")
    assert p1.phone == "+12345678901"

    # Invalid phone
    with pytest.raises(ValidationError):
        PatchOwnerGarageMinor(phone="not-a-phone")

    # Empty patch should fail
    with pytest.raises(ValidationError):
        PatchOwnerGarageMinor()


def test_critical_change_request_validation():
    # Valid name change
    req = CreateProfileChangeRequest(name="New Garage Name")
    assert req.name == "New Garage Name"

    # Coordinates must be paired
    with pytest.raises(ValidationError):
        CreateProfileChangeRequest(latitude=27.7172)

    with pytest.raises(ValidationError):
        CreateProfileChangeRequest(longitude=85.3240)

    # Valid coordinates pair
    c_req = CreateProfileChangeRequest(latitude=27.7172, longitude=85.3240)
    assert c_req.latitude == 27.7172
    assert c_req.longitude == 85.3240

    # Empty change request should fail
    with pytest.raises(ValidationError):
        CreateProfileChangeRequest()

