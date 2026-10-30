"""
Pydantic schemas for Owner Garage Profile, Availability, and Critical Change Requests.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.catalog import ServiceRead, VehicleTypeRead
from app.schemas.garage_registration import OperatingHourItem

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


# ── Availability DTOs ─────────────────────────────────────────────────────────

class AvailabilityResponse(BaseModel):
    status: str = Field(description="OPEN, CLOSED, or TEMPORARILY_UNAVAILABLE")
    is_temporarily_unavailable: bool
    message: str | None = None
    timezone: str
    local_time: str
    next_status_change: str | None = None


class PatchAvailabilityRequest(BaseModel):
    is_temporarily_unavailable: bool
    message: str | None = Field(default=None, max_length=300)

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = " ".join(v.strip().split())
            return cleaned or None
        return None

    @model_validator(mode="after")
    def validate_message_rules(self) -> "PatchAvailabilityRequest":
        # Message only applies while unavailable; clear when false
        if not self.is_temporarily_unavailable:
            self.message = None
        return self


# ── Minor Profile Edits (Phone & Description only) ───────────────────────────

class PatchOwnerGarageMinor(BaseModel):
    phone: str | None = None
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if not E164_REGEX.match(cleaned):
                raise ValueError("Phone number must be in E.164 international format (e.g. +1234567890).")
            return cleaned
        return None

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return None

    @model_validator(mode="after")
    def validate_at_least_one(self) -> "PatchOwnerGarageMinor":
        if self.phone is None and self.description is None:
            raise ValueError("At least one minor field (phone or description) must be provided.")
        return self


# ── Critical Profile Change Requests (Name, Address, Location) ───────────────

class CreateProfileChangeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=5, max_length=500)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)

    @field_validator("name", "address")
    @classmethod
    def normalize_text(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = " ".join(v.strip().split())
            return cleaned or None
        return None

    @model_validator(mode="after")
    def validate_request(self) -> "CreateProfileChangeRequest":
        # Coordinates must be provided together
        has_lat = self.latitude is not None
        has_lng = self.longitude is not None
        if has_lat != has_lng:
            raise ValueError("Latitude and longitude must both be provided together.")

        # At least one field must be proposed
        if not self.name and not self.address and not has_lat:
            raise ValueError("At least one critical field (name, address, or coordinates) must be provided.")
        return self


class ProfileChangeRequestResponse(BaseModel):
    id: uuid.UUID
    garage_id: uuid.UUID
    proposed_changes: dict[str, Any]
    status: str
    rejection_reason: str | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Operating Hours Replacement Request ───────────────────────────────────────

class PutOperatingHoursRequest(BaseModel):
    hours: list[OperatingHourItem]

    @field_validator("hours")
    @classmethod
    def validate_seven_days(cls, v: list[OperatingHourItem]) -> list[OperatingHourItem]:
        if len(v) != 7:
            raise ValueError("Operating hours replacement must contain exactly 7 records.")
        days = {item.day_of_week for item in v}
        if days != set(range(1, 8)):
            raise ValueError("Operating hours must include each day from 1 (Monday) to 7 (Sunday) exactly once.")
        return sorted(v, key=lambda x: x.day_of_week)


# ── Full Owner Garage Profile DTO ─────────────────────────────────────────────

class OwnerGarageProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    phone: str
    address: str
    latitude: float
    longitude: float
    timezone: str
    approval_status: str
    is_suspended: bool
    registration_version: int
    availability: AvailabilityResponse
    services: list[ServiceRead]
    vehicle_types: list[VehicleTypeRead]
    operating_hours: list[OperatingHourItem]

