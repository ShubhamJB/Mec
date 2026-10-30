"""
Pydantic schemas for Services and Vehicle Types catalogs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ── Services Schemas ──────────────────────────────────────────────────────────

class ServiceRead(BaseModel):
    id: uuid.UUID
    name: str
    is_predefined: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateCustomServiceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        # Trim leading/trailing whitespace and collapse internal spaces
        normalized = " ".join(v.strip().split())
        if len(normalized) < 2:
            raise ValueError("Service name must be at least 2 characters after whitespace trimming.")
        return normalized


class GarageServiceUpdate(BaseModel):
    service_ids: list[uuid.UUID] = Field(min_length=1)

    @field_validator("service_ids")
    @classmethod
    def deduplicate_service_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        seen = set()
        deduped = []
        for sid in v:
            if sid not in seen:
                seen.add(sid)
                deduped.append(sid)
        return deduped


# ── Vehicle Types Schemas ─────────────────────────────────────────────────────

class VehicleTypeRead(BaseModel):
    id: uuid.UUID
    name: str
    is_predefined: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateCustomVehicleTypeRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        normalized = " ".join(v.strip().split())
        if len(normalized) < 2:
            raise ValueError("Vehicle type name must be at least 2 characters after whitespace trimming.")
        return normalized


class GarageVehicleTypeUpdate(BaseModel):
    vehicle_type_ids: list[uuid.UUID] = Field(min_length=1)

    @field_validator("vehicle_type_ids")
    @classmethod
    def deduplicate_vehicle_type_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        seen = set()
        deduped = []
        for vid in v:
            if vid not in seen:
                seen.add(vid)
                deduped.append(vid)
        return deduped

