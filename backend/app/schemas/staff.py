from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(max_length=16)
    role_title: str | None = Field(default=None, max_length=50)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if len(normalized) < 2:
            raise ValueError("Name must contain at least 2 characters.")
        return normalized

    @field_validator("role_title")
    @classmethod
    def normalize_role_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not E164_REGEX.fullmatch(value):
            raise ValueError("Phone number must be in E.164 international format.")
        return value


class StaffPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=16)
    role_title: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("full_name", "role_title")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        if not normalized:
            return None
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not E164_REGEX.fullmatch(value):
            raise ValueError("Phone number must be in E.164 international format.")
        return value

    @model_validator(mode="after")
    def validate_not_empty(self) -> "StaffPatch":
        if not self.model_fields_set:
            raise ValueError("At least one staff field must be provided.")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("Name cannot be null.")
        if "phone" in self.model_fields_set and self.phone is None:
            raise ValueError("Phone cannot be null.")
        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("Active status cannot be null.")
        if self.full_name is not None and len(self.full_name) < 2:
            raise ValueError("Name must contain at least 2 characters.")
        return self


class StaffRead(BaseModel):
    id: uuid.UUID
    garage_id: uuid.UUID
    full_name: str
    phone: str
    role_title: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
