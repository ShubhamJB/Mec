"""
Pydantic schemas for Garage Registration and Pending Edits.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, time
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ApprovalStatus, RegistrationHistoryStatus


# ── Operating Hours DTO ───────────────────────────────────────────────────────

class OperatingHourItem(BaseModel):
    day_of_week: int = Field(ge=1, le=7, description="ISO weekday: 1=Monday .. 7=Sunday")
    is_closed: bool
    opening_time: time | None = None
    closing_time: time | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "OperatingHourItem":
        if self.is_closed:
            if self.opening_time is not None or self.closing_time is not None:
                raise ValueError(
                    f"Day {self.day_of_week} is closed; opening_time and closing_time must be null."
                )
        else:
            if self.opening_time is None or self.closing_time is None:
                raise ValueError(
                    f"Day {self.day_of_week} is open; both opening_time and closing_time are required."
                )
            if self.opening_time >= self.closing_time:
                raise ValueError(
                    f"Day {self.day_of_week}: opening_time ({self.opening_time}) must be earlier than closing_time ({self.closing_time})."
                )
        return self


# ── Registration DTOs ─────────────────────────────────────────────────────────

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


class GarageRegistrationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    phone: str = Field(description="E.164 international format, e.g. +1234567890")
    address: str = Field(min_length=5, max_length=500)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)

    service_ids: list[uuid.UUID] = Field(default_factory=list)
    custom_services: list[str] = Field(default_factory=list)

    vehicle_type_ids: list[uuid.UUID] = Field(default_factory=list)
    custom_vehicle_types: list[str] = Field(default_factory=list)

    operating_hours: list[OperatingHourItem]

    @field_validator("name", "address")
    @classmethod
    def normalize_text(cls, v: str) -> str:
        return " ".join(v.strip().split())

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if not E164_REGEX.match(cleaned):
            raise ValueError("Phone number must be in E.164 international format (e.g. +1234567890).")
        return cleaned

    @field_validator("operating_hours")
    @classmethod
    def validate_seven_days(cls, v: list[OperatingHourItem]) -> list[OperatingHourItem]:
        if len(v) != 7:
            raise ValueError("Exactly 7 operating_hours records (one for each ISO weekday 1-7) are required.")
        days = {item.day_of_week for item in v}
        if days != set(range(1, 8)):
            raise ValueError("Operating hours must include each day from 1 (Monday) to 7 (Sunday) exactly once.")
        return sorted(v, key=lambda x: x.day_of_week)

    @model_validator(mode="after")
    def validate_catalogs(self) -> "GarageRegistrationCreate":
        if not self.service_ids and not self.custom_services:
            raise ValueError("At least one active service (or custom service) must be provided.")
        if not self.vehicle_type_ids and not self.custom_vehicle_types:
            raise ValueError("At least one active vehicle type (or custom vehicle type) must be provided.")
        return self


class GarageRegistrationPatch(BaseModel):
    expected_version: int = Field(ge=1, description="Current registration version expected by the client")
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    phone: str | None = None
    address: str | None = Field(default=None, min_length=5, max_length=500)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    service_ids: list[uuid.UUID] | None = None
    vehicle_type_ids: list[uuid.UUID] | None = None
    operating_hours: list[OperatingHourItem] | None = None

    @field_validator("name", "address")
    @classmethod
    def normalize_text(cls, v: str | None) -> str | None:
        if v is not None:
            return " ".join(v.strip().split())
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if not E164_REGEX.match(cleaned):
                raise ValueError("Phone number must be in E.164 international format (e.g. +1234567890).")
            return cleaned
        return v

    @field_validator("operating_hours")
    @classmethod
    def validate_seven_days(cls, v: list[OperatingHourItem] | None) -> list[OperatingHourItem] | None:
        if v is not None:
            if len(v) != 7:
                raise ValueError("Operating hours update must contain exactly 7 records.")
            days = {item.day_of_week for item in v}
            if days != set(range(1, 8)):
                raise ValueError("Operating hours must include each day from 1 to 7.")
            return sorted(v, key=lambda x: x.day_of_week)
        return v

    @model_validator(mode="after")
    def validate_coordinates_paired(self) -> "GarageRegistrationPatch":
        if (self.latitude is not None and self.longitude is None) or (
            self.longitude is not None and self.latitude is None
        ):
            raise ValueError("Latitude and longitude must both be provided together when updating coordinates.")
        return self


# ── Response DTOs ─────────────────────────────────────────────────────────────

class LatestDecisionBrief(BaseModel):
    status: RegistrationHistoryStatus
    rejection_reason: str | None = None
    reviewed_at: datetime | None = None


class GarageRegistrationStatusResponse(BaseModel):
    garage_id: uuid.UUID
    approval_status: ApprovalStatus
    registration_version: int
    submitted_at: datetime
    latest_decision: LatestDecisionBrief | None = None


class GarageRegistrationHistoryItem(BaseModel):
    id: uuid.UUID
    garage_id: uuid.UUID
    status: RegistrationHistoryStatus
    submission_data: dict[str, Any]
    rejection_reason: str | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}

