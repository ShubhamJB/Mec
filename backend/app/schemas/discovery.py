"""
Pydantic schemas for Public Garage Discovery and Listing.
"""
from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.garage_profile import AvailabilityResponse


class GarageCard(BaseModel):
    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    distance_km: float | None = None
    average_rating: float | None = None
    review_count: int = 0
    availability: AvailabilityResponse
    phone: str
    cover_photo_url: str | None = None

    model_config = {"from_attributes": True}


SortByOption = Literal["nearest", "highest_rated", "most_reviewed"]

