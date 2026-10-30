"""
Pydantic schemas for Administrator Moderation, Approvals, and Audit Logs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    AccountStatus,
    AdminActionType,
    ApprovalStatus,
    RegistrationHistoryStatus,
    ReviewReportReason,
    ReviewReportStatus,
    UserRole,
)
from app.schemas.catalog import ServiceRead, VehicleTypeRead
from app.schemas.garage_registration import OperatingHourItem
from app.schemas.photo import PhotoRead


# ── Admin Dashboard ───────────────────────────────────────────────────────────

class AdminDashboardResponse(BaseModel):
    total_users: int = 0
    total_customers: int = 0
    total_owners: int = 0
    total_suspended_users: int = 0
    total_garages: int = 0
    pending_registrations: int = 0
    approved_garages: int = 0
    rejected_garages: int = 0
    suspended_garages: int = 0
    total_reviews: int = 0
    pending_review_reports: int = 0
    total_call_clicks: int = 0


# ── Garage Registration Decisions ─────────────────────────────────────────────

RegistrationDecision = Literal["APPROVE", "REJECT"]


class RegistrationDecisionRequest(BaseModel):
    decision: RegistrationDecision
    expected_version: int = Field(ge=1, description="Current registration version expected")
    rejection_reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "RegistrationDecisionRequest":
        if self.decision == "REJECT":
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("rejection_reason is required when decision is REJECT.")
            self.rejection_reason = self.rejection_reason.strip()
        else:
            self.rejection_reason = None
        return self


class AdminGarageRegistrationDetail(BaseModel):
    garage_id: uuid.UUID
    name: str
    description: str | None
    phone: str
    address: str
    latitude: float
    longitude: float
    timezone: str
    approval_status: str
    registration_version: int
    owner_id: uuid.UUID
    owner_name: str
    owner_email: str
    submitted_at: datetime
    services: list[ServiceRead]
    vehicle_types: list[VehicleTypeRead]
    operating_hours: list[OperatingHourItem]
    photos: list[PhotoRead]


# ── Profile Change Request Decisions ─────────────────────────────────────────

ProfileChangeDecision = Literal["APPROVE", "REJECT"]


class ProfileChangeDecisionRequest(BaseModel):
    decision: ProfileChangeDecision
    rejection_reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "ProfileChangeDecisionRequest":
        if self.decision == "REJECT":
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("rejection_reason is required when decision is REJECT.")
            self.rejection_reason = self.rejection_reason.strip()
        else:
            self.rejection_reason = None
        return self


# ── Garage Moderation ─────────────────────────────────────────────────────────

GarageModerationAction = Literal["SUSPEND", "RESTORE"]


class GarageModerationRequest(BaseModel):
    action: GarageModerationAction
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_reason(self) -> "GarageModerationRequest":
        if self.action == "SUSPEND":
            if not self.reason or not self.reason.strip():
                raise ValueError("reason is required when suspending a garage.")
            self.reason = self.reason.strip()
        return self


class DeleteGarageRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def clean_reason(self) -> "DeleteGarageRequest":
        self.reason = self.reason.strip()
        return self


# ── User Moderation ───────────────────────────────────────────────────────────

class UserStatusUpdateRequest(BaseModel):
    status: AccountStatus
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_suspend_reason(self) -> "UserStatusUpdateRequest":
        if self.status == AccountStatus.SUSPENDED:
            if not self.reason or not self.reason.strip():
                raise ValueError("reason is required when suspending a user account.")
            self.reason = self.reason.strip()
        return self


class AdminUserDetailResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: UserRole
    email_verified: bool
    account_status: AccountStatus
    created_at: datetime
    updated_at: datetime
    garage_id: uuid.UUID | None = None
    garage_name: str | None = None

    model_config = {"from_attributes": True}


# ── Review Report Decisions ───────────────────────────────────────────────────

ReviewReportDecision = Literal["DISMISS", "REMOVE_REVIEW"]


class ReviewReportDecisionRequest(BaseModel):
    decision: ReviewReportDecision
    note: str = Field(min_length=2, max_length=2000, description="Mandatory admin decision note")

    @model_validator(mode="after")
    def clean_note(self) -> "ReviewReportDecisionRequest":
        cleaned = self.note.strip()
        if len(cleaned) < 2:
            raise ValueError("note must be at least 2 characters after whitespace trimming.")
        self.note = cleaned
        return self


class AdminReviewReportDetail(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    review_rating: int
    review_comment: str | None
    review_status: str
    garage_id: uuid.UUID
    garage_name: str
    reporter_id: uuid.UUID
    reporter_name: str
    reason: ReviewReportReason
    details: str | None
    status: ReviewReportStatus
    admin_note: str | None
    reviewed_at: datetime | None
    created_at: datetime


# ── Audit Log DTO ─────────────────────────────────────────────────────────────

class AuditLogEntryResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    admin_name: str
    action_type: str
    target_type: str
    target_id: uuid.UUID
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
