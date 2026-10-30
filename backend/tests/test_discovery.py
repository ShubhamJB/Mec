"""Unit tests for discovery schemas and coordinate pairing."""
import uuid
import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from app.schemas.discovery import GarageCard
from app.schemas.garage_profile import AvailabilityResponse
from app.services.discovery_service import _build_base_discovery_query
from app.utils.geo import point_from_coords


def test_garage_card_schema():
    card = GarageCard(
        id=uuid.uuid4(),
        name="Auto Repair Experts",
        latitude=27.7172,
        longitude=85.3240,
        distance_km=2.45,
        average_rating=4.8,
        review_count=12,
        availability=AvailabilityResponse(
            status="OPEN",
            is_temporarily_unavailable=False,
            message=None,
            timezone="Asia/Kathmandu",
            local_time="2026-10-30T10:00:00+05:45",
            next_status_change="2026-10-30T18:00:00+05:45",
        ),
        phone="+9779800000000",
        cover_photo_url="https://storage.findyourmechanic.com/photos/sample.jpg",
    )
    assert card.name == "Auto Repair Experts"
    assert card.distance_km == 2.45
    assert card.availability.status == "OPEN"


def test_build_base_discovery_query_sql_generation():
    pt = point_from_coords(27.7172, 85.3240)
    query = _build_base_discovery_query(
        origin_point=pt,
        radius_meters=5000,
        search="auto",
        service_ids=[uuid.uuid4()],
        vehicle_type_ids=[uuid.uuid4()],
    )
    # Validate query compiles properly to PostgreSQL dialect
    compiled_sql = str(query.compile())
    assert "garages" in compiled_sql
    assert "users" in compiled_sql
    assert "ST_DWithin" in compiled_sql
    assert "ST_Distance" in compiled_sql

