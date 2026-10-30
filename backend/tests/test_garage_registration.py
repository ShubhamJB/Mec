"""Unit tests for garage registration schemas, hours validation, and timezone derivation."""
import uuid
from datetime import time
import pytest
from pydantic import ValidationError

from app.schemas.garage_registration import (
    GarageRegistrationCreate,
    GarageRegistrationPatch,
    OperatingHourItem,
)
from app.utils.geo import derive_timezone


def make_valid_hours():
    hours = []
    # Monday to Saturday open 09:00 - 18:00
    for day in range(1, 7):
        hours.append(
            OperatingHourItem(
                day_of_week=day,
                is_closed=False,
                opening_time=time(9, 0),
                closing_time=time(18, 0),
            )
        )
    # Sunday closed
    hours.append(
        OperatingHourItem(
            day_of_week=7,
            is_closed=True,
            opening_time=None,
            closing_time=None,
        )
    )
    return hours


def test_operating_hours_validation():
    # Valid
    hours = make_valid_hours()
    assert len(hours) == 7

    # Closed day with times should fail
    with pytest.raises(ValidationError):
        OperatingHourItem(
            day_of_week=1,
            is_closed=True,
            opening_time=time(9, 0),
            closing_time=time(17, 0),
        )

    # Open day with opening >= closing should fail
    with pytest.raises(ValidationError):
        OperatingHourItem(
            day_of_week=1,
            is_closed=False,
            opening_time=time(18, 0),
            closing_time=time(9, 0),
        )


def test_garage_registration_create_validation():
    sid = uuid.uuid4()
    vid = uuid.uuid4()
    hours = make_valid_hours()

    req = GarageRegistrationCreate(
        name="  Auto   Care   Pro  ",
        description="Best mechanics in town",
        phone="+9779812345678",
        address="123 Main Street, Kathmandu",
        latitude=27.7172,
        longitude=85.3240,
        service_ids=[sid],
        vehicle_type_ids=[vid],
        operating_hours=hours,
    )
    assert req.name == "Auto Care Pro"
    assert req.phone == "+9779812345678"

    # Invalid phone format
    with pytest.raises(ValidationError):
        GarageRegistrationCreate(
            name="Auto Care",
            phone="invalid-phone",
            address="123 Main St",
            latitude=27.7,
            longitude=85.3,
            service_ids=[sid],
            vehicle_type_ids=[vid],
            operating_hours=hours,
        )

    # Missing catalogs (both IDs and custom missing)
    with pytest.raises(ValidationError):
        GarageRegistrationCreate(
            name="Auto Care",
            phone="+9779812345678",
            address="123 Main St",
            latitude=27.7,
            longitude=85.3,
            service_ids=[],
            custom_services=[],
            vehicle_type_ids=[vid],
            operating_hours=hours,
        )


def test_timezone_derivation():
    # Kathmandu coordinates
    tz_ktm = derive_timezone(27.7172, 85.3240)
    assert tz_ktm == "Asia/Kathmandu"

    # London coordinates
    tz_lon = derive_timezone(51.5074, -0.1278)
    assert tz_lon == "Europe/London"

