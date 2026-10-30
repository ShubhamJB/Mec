"""
Centralised model imports — import from here everywhere else.
This ensures all models are registered with SQLAlchemy metadata
before Alembic autogenerate runs.
"""
from app.models.user import User
from app.models.garage import Garage, GarageRegistrationHistory, GarageProfileChangeRequest
from app.models.catalog import (
    Service,
    GarageService,
    VehicleType,
    GarageVehicleType,
    OperatingHours,
)
from app.models.photo import GaragePhoto
from app.models.review import Review, ReviewReport
from app.models.notification import Notification
from app.models.analytics import AnalyticsEvent, AdminAction
from app.models.token import RefreshToken, EmailVerificationToken
from app.models.enums import (
    UserRole,
    AccountStatus,
    ApprovalStatus,
    RegistrationHistoryStatus,
    ReviewStatus,
    ReviewReportReason,
    ReviewReportStatus,
    AnalyticsEventType,
    NotificationType,
    ProfileChangeRequestStatus,
    AdminActionType,
)

__all__ = [
    "User",
    "Garage",
    "GarageRegistrationHistory",
    "GarageProfileChangeRequest",
    "Service",
    "GarageService",
    "VehicleType",
    "GarageVehicleType",
    "OperatingHours",
    "GaragePhoto",
    "Review",
    "ReviewReport",
    "Notification",
    "AnalyticsEvent",
    "AdminAction",
    "RefreshToken",
    "EmailVerificationToken",
    "UserRole",
    "AccountStatus",
    "ApprovalStatus",
    "RegistrationHistoryStatus",
    "ReviewStatus",
    "ReviewReportReason",
    "ReviewReportStatus",
    "AnalyticsEventType",
    "NotificationType",
    "ProfileChangeRequestStatus",
    "AdminActionType",
]

