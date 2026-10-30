"""
Pydantic schemas for auth endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Registration ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return " ".join(v.split())  # collapse internal whitespace

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class RegisterResponse(BaseModel):
    message: str
    user: "UserBrief"


class UserBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── Refresh ───────────────────────────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Email verification ────────────────────────────────────────────────────────

class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


# ── Generic message ───────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str

