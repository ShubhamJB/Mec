"""
Shared enums used across all ORM models.
Keep in sync with Pydantic schemas.
"""
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    GARAGE_OWNER = "GARAGE_OWNER"
    ADMIN = "ADMIN"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RegistrationHistoryStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewStatus(str, enum.Enum):
    PUBLISHED = "PUBLISHED"
    REMOVED = "REMOVED"


class ReviewReportReason(str, enum.Enum):
    SPAM = "SPAM"
    ABUSIVE_CONTENT = "ABUSIVE_CONTENT"
    FAKE_REVIEW = "FAKE_REVIEW"
    IRRELEVANT = "IRRELEVANT"
    OTHER = "OTHER"


class ReviewReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    DISMISSED = "DISMISSED"
    REVIEW_REMOVED = "REVIEW_REMOVED"


class AnalyticsEventType(str, enum.Enum):
    PROFILE_VIEW = "PROFILE_VIEW"
    CALL_CLICK = "CALL_CLICK"


class NotificationType(str, enum.Enum):
    # Auth
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    # Registration
    REGISTRATION_APPROVED = "REGISTRATION_APPROVED"
    REGISTRATION_REJECTED = "REGISTRATION_REJECTED"
    # Profile change
    PROFILE_CHANGE_APPROVED = "PROFILE_CHANGE_APPROVED"
    PROFILE_CHANGE_REJECTED = "PROFILE_CHANGE_REJECTED"
    # Garage moderation
    GARAGE_SUSPENDED = "GARAGE_SUSPENDED"
    GARAGE_RESTORED = "GARAGE_RESTORED"
    # Account moderation
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    ACCOUNT_RESTORED = "ACCOUNT_RESTORED"
    # Reviews
    REVIEW_RECEIVED = "REVIEW_RECEIVED"
    REVIEW_REPORT_RECEIVED = "REVIEW_REPORT_RECEIVED"
    REVIEW_REPORT_RESOLVED = "REVIEW_REPORT_RESOLVED"


class ProfileChangeRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AdminActionType(str, enum.Enum):
    # Registration decisions
    APPROVE_REGISTRATION = "APPROVE_REGISTRATION"
    REJECT_REGISTRATION = "REJECT_REGISTRATION"
    # Profile change decisions
    APPROVE_PROFILE_CHANGE = "APPROVE_PROFILE_CHANGE"
    REJECT_PROFILE_CHANGE = "REJECT_PROFILE_CHANGE"
    # Garage moderation
    SUSPEND_GARAGE = "SUSPEND_GARAGE"
    RESTORE_GARAGE = "RESTORE_GARAGE"
    DELETE_GARAGE = "DELETE_GARAGE"
    # User moderation
    SUSPEND_USER = "SUSPEND_USER"
    RESTORE_USER = "RESTORE_USER"
    # Review moderation
    DISMISS_REVIEW_REPORT = "DISMISS_REVIEW_REPORT"
    REMOVE_REVIEW = "REMOVE_REVIEW"

