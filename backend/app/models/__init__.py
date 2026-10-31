"""
Centralised model imports — import from here everywhere else.
This ensures all models are registered with SQLAlchemy metadata
before Alembic autogenerate runs.
"""

from app.models.analytics import AdminAction, AnalyticsEvent
from app.models.catalog import (
    GarageService,
    GarageVehicleType,
    OperatingHours,
    Service,
    VehicleType,
)
from app.models.enums import (
    AccountStatus,
    AdminActionType,
    AnalyticsEventType,
    ApprovalStatus,
    NotificationType,
    ProfileChangeRequestStatus,
    RegistrationHistoryStatus,
    ReviewReportReason,
    ReviewReportStatus,
    ReviewStatus,
    RoadsideRequestStatus,
    UserRole,
)
from app.models.garage import Garage, GarageProfileChangeRequest, GarageRegistrationHistory
from app.models.notification import Notification
from app.models.photo import GaragePhoto
from app.models.review import Review, ReviewReport
from app.models.roadside import RoadsideCapability, RoadsideRequest, RoadsideRequestEvent
from app.models.staff import GarageStaff
from app.models.token import EmailVerificationToken, RefreshToken
from app.models.user import User

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
    "GarageStaff",
    "RoadsideCapability",
    "RoadsideRequest",
    "RoadsideRequestEvent",
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
    "RoadsideRequestStatus",
    "AdminActionType",
]
