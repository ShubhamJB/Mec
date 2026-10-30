"""
Pydantic schemas for Public Garage Profile and Operating Hours.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel

from app.schemas.catalog import ServiceRead, VehicleTypeRead
from app.schemas.garage_profile import AvailabilityResponse
from app.schemas.garage_registration import OperatingHourItem
from app.schemas.photo import PhotoRead


class PublicGarageProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    phone: str
    address: str
    latitude: float
    longitude: float
    timezone: str
    average_rating: float | None = None
    review_count: int = 0
    availability: AvailabilityResponse
    services: list[ServiceRead]
    vehicle_types: list[VehicleTypeRead]
    operating_hours: list[OperatingHourItem]
    photos: list[PhotoRead]
    created_at: datetime


class PublicOperatingHoursResponse(BaseModel):
    timezone: str
    hours: list[OperatingHourItem]

