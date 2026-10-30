"""
Pydantic schemas for Garage Photos.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class PhotoRead(BaseModel):
    id: uuid.UUID
    garage_id: uuid.UUID
    url: str
    caption: str | None = None
    display_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReorderPhotosRequest(BaseModel):
    ordered_photo_ids: list[uuid.UUID] = Field(
        min_length=1,
        description="List of all active photo IDs for the garage in desired display order",
    )

    @field_validator("ordered_photo_ids")
    @classmethod
    def validate_no_duplicates(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate photo IDs are not permitted in reorder request.")
        return v

