"""Validated request/response models for roadside assistance."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import RoadsideRequestStatus

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


class RoadsideCapabilityUpdate(BaseModel):
    enabled: bool
    is_available: bool
    service_radius_km: int = Field(ge=1, le=100)
    availability_note: str | None = Field(default=None, max_length=300)
    callback_phone: str = Field(min_length=9, max_length=16)
    response_minutes: int = Field(default=15, ge=1, le=240)

    @field_validator("callback_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError("Callback phone must use E.164 international format.")
        return value

    @field_validator("availability_note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split()) or None

    @model_validator(mode="after")
    def availability_requires_opt_in(self) -> "RoadsideCapabilityUpdate":
        if self.is_available and not self.enabled:
            raise ValueError("Roadside availability requires roadside assistance to be enabled.")
        return self


class RoadsideCapabilityRead(RoadsideCapabilityUpdate):
    id: uuid.UUID
    garage_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EligibleGarage(BaseModel):
    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    distance_km: float
    average_rating: float | None = None
    review_count: int
    callback_expectation_minutes: int
    availability_note: str | None = None


class EligibleGaragesResponse(BaseModel):
    items: list[EligibleGarage]
    search_radius_km: int


class RoadsideRequestCreate(BaseModel):
    garage_id: uuid.UUID
    vehicle_type_id: uuid.UUID
    service_id: uuid.UUID
    problem_description: str = Field(min_length=10, max_length=1000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)
    contact_phone: str = Field(min_length=9, max_length=16)
    consent_to_share_after_acceptance: bool

    @field_validator("problem_description")
    @classmethod
    def clean_problem(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 10:
            raise ValueError("Problem description must contain at least 10 characters.")
        return cleaned

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError("Contact phone must use E.164 international format.")
        return value

    @model_validator(mode="after")
    def require_consent(self) -> "RoadsideRequestCreate":
        if not self.consent_to_share_after_acceptance:
            raise ValueError(
                "Consent to share contact and precise location after acceptance is required."
            )
        return self


class RoadsideRequestAction(BaseModel):
    reason: str | None = Field(default=None, min_length=2, max_length=100)


class RoadsideRequestProgress(BaseModel):
    status: RoadsideRequestStatus = Field(
        description=(
            "Owner progress state: CONTACTED, CONFIRMED, IN_PROGRESS, COMPLETED, "
            "or UNABLE_TO_SERVE."
        )
    )
    quote_amount: Decimal | None = Field(default=None, ge=0, le=9999999)
    quote_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    eta_minutes: int | None = Field(default=None, ge=1, le=1440)

    @model_validator(mode="after")
    def quote_fields_pair(self) -> "RoadsideRequestProgress":
        if self.status not in {
            RoadsideRequestStatus.CONTACTED,
            RoadsideRequestStatus.CONFIRMED,
            RoadsideRequestStatus.IN_PROGRESS,
            RoadsideRequestStatus.COMPLETED,
            RoadsideRequestStatus.UNABLE_TO_SERVE,
        }:
            raise ValueError("Status is not a valid owner progress state.")
        if (self.quote_amount is None) != (self.quote_currency is None):
            raise ValueError("Quote amount and currency must be supplied together.")
        return self


class RoadsideRequestEventRead(BaseModel):
    from_status: RoadsideRequestStatus | None
    to_status: RoadsideRequestStatus
    created_at: datetime
    safe_metadata: dict[str, str] | None = None

    model_config = {"from_attributes": True}


class RoadsideRequestRead(BaseModel):
    id: uuid.UUID
    request_code: str
    garage_id: uuid.UUID
    garage_name: str
    customer_id: uuid.UUID
    status: RoadsideRequestStatus
    vehicle_type_id: uuid.UUID
    service_id: uuid.UUID
    problem_description: str
    coarse_latitude: float
    coarse_longitude: float
    exact_latitude: float | None = None
    exact_longitude: float | None = None
    address: str | None = None
    contact_phone: str | None = None
    quote_amount: Decimal | None = None
    quote_currency: str | None = None
    eta_minutes: int | None = None
    decline_reason: str | None = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    events: list[RoadsideRequestEventRead] = Field(default_factory=list)
