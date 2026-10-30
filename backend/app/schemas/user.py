"""
Pydantic schemas for user profile endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: str
    account_status: str
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return " ".join(v.split())


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        if self.new_password == self.current_password:
            raise ValueError("new_password must differ from current_password.")
        return self

