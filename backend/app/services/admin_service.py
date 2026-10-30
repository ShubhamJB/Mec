"""
Service layer for Administrative Moderation, Approvals, and Audit Logs.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    UserRole,
)
from app.models.garage import (
    Garage,
    GarageProfileChangeRequest,
    GarageRegistrationHistory,
)
from app.models.photo import GaragePhoto
from app.models.review import Review, ReviewReport
from app.models.token import RefreshToken
from app.models.user import User
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminGarageRegistrationDetail,
    AdminReviewReportDetail,
    AdminUserDetailResponse,
    AuditLogEntryResponse,
    DeleteGarageRequest,
    GarageModerationRequest,
    ProfileChangeDecisionRequest,
    RegistrationDecisionRequest,
    ReviewReportDecisionRequest,
    UserStatusUpdateRequest,
)
from app.schemas.catalog import ServiceRead, VehicleTypeRead
from app.schemas.garage_profile import ProfileChangeRequestResponse
from app.schemas.garage_registration import (
    GarageRegistrationStatusResponse,
    OperatingHourItem,
)
from app.schemas.photo import PhotoRead
from app.services.notification_service import notify_user
from app.utils.geo import derive_timezone, point_from_coords


# ── Audit Action Helper ───────────────────────────────────────────────────────

async def record_admin_action(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action_type: AdminActionType,
    target_type: str,
    target_id: uuid.UUID,
    reason: str | None = None,
) -> None:
    action = AdminAction(
        admin_id=admin_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
    )
    db.add(action)
    await db.flush()


# ── 1. Admin Dashboard ────────────────────────────────────────────────────────

async def get_admin_dashboard(db: AsyncSession) -> AdminDashboardResponse:
    # User counts
    users_q = select(
        func.count(User.id).label("total"),
        func.count(User.id).filter(User.role == UserRole.CUSTOMER).label("customers"),
        func.count(User.id).filter(User.role == UserRole.GARAGE_OWNER).label("owners"),
        func.count(User.id).filter(User.account_status == AccountStatus.SUSPENDED).label("suspended"),
    ).where(User.deleted_at.is_(None))
    u_row = (await db.execute(users_q)).first()

    # Garage counts
    garages_q = select(
        func.count(Garage.id).label("total"),
        func.count(Garage.id).filter(Garage.approval_status == ApprovalStatus.PENDING).label("pending"),
        func.count(Garage.id).filter(Garage.approval_status == ApprovalStatus.APPROVED).label("approved"),
        func.count(Garage.id).filter(Garage.approval_status == ApprovalStatus.REJECTED).label("rejected"),
        func.count(Garage.id).filter(Garage.is_suspended.is_(True)).label("suspended"),
    ).where(Garage.deleted_at.is_(None))
    g_row = (await db.execute(garages_q)).first()

    # Pending profile changes
    profile_changes_count = (
        await db.execute(
            select(func.count(GarageProfileChangeRequest.id)).where(
                GarageProfileChangeRequest.status == ProfileChangeRequestStatus.PENDING
            )
        )
    ).scalar_one()

    # Reviews count
    reviews_count = (
        await db.execute(
            select(func.count(Review.id)).where(
                Review.deleted_at.is_(None), Review.status == ReviewStatus.PUBLISHED
            )
        )
    ).scalar_one()

    # Pending reports
    reports_count = (
        await db.execute(
            select(func.count(ReviewReport.id)).where(
                ReviewReport.status == ReviewReportStatus.PENDING
            )
        )
    ).scalar_one()

    # Call clicks
    clicks_count = (
        await db.execute(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.event_type == AnalyticsEventType.CALL_CLICK
            )
        )
    ).scalar_one()

    return AdminDashboardResponse(
        total_users=int(u_row[0]) if u_row else 0,
        total_customers=int(u_row[1]) if u_row else 0,
        total_owners=int(u_row[2]) if u_row else 0,
        total_suspended_users=int(u_row[3]) if u_row else 0,
        total_garages=int(g_row[0]) if g_row else 0,
        pending_registrations=int(g_row[1]) if g_row else 0,
        pending_profile_changes=profile_changes_count,
        approved_garages=int(g_row[2]) if g_row else 0,
        rejected_garages=int(g_row[3]) if g_row else 0,
        suspended_garages=int(g_row[4]) if g_row else 0,
        total_reviews=reviews_count,
        pending_review_reports=reports_count,
        total_call_clicks=clicks_count,
    )


# ── 2. Garage Registration Moderation ─────────────────────────────────────────

async def list_garage_registrations(
    db: AsyncSession,
    status_filter: ApprovalStatus | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[dict], int]:
    latest_submission = (
        select(
            GarageRegistrationHistory.garage_id.label("garage_id"),
            func.max(GarageRegistrationHistory.submitted_at).label("submitted_at"),
            func.max(GarageRegistrationHistory.reviewed_at).label("reviewed_at"),
        )
        .group_by(GarageRegistrationHistory.garage_id)
        .subquery()
    )
    submitted_at = func.coalesce(latest_submission.c.submitted_at, Garage.created_at)
    last_activity_at = func.coalesce(latest_submission.c.reviewed_at, submitted_at)
    base_q = (
        select(
            Garage,
            User.full_name,
            User.email,
            submitted_at.label("submitted_at"),
            latest_submission.c.reviewed_at.label("reviewed_at"),
        )
        .join(User, Garage.owner_id == User.id)
        .outerjoin(latest_submission, latest_submission.c.garage_id == Garage.id)
        .where(Garage.deleted_at.is_(None))
    )
    if status_filter:
        base_q = base_q.where(Garage.approval_status == status_filter)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base_q = base_q.where(func.lower(Garage.name).like(term))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    rows = list(
        (
            await db.execute(
                base_q.order_by(last_activity_at.desc(), Garage.id)
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )

    items = [
        {
            "id": str(r[0].id),
            "garage_id": str(r[0].id),
            "name": r[0].name,
            "garage_name": r[0].name,
            "phone": r[0].phone,
            "address": r[0].address,
            "approval_status": r[0].approval_status.value if hasattr(r[0].approval_status, "value") else str(r[0].approval_status),
            "registration_version": r[0].registration_version,
            "owner_id": str(r[0].owner_id),
            "owner_name": r[1],
            "owner_email": r[2],
            "submitted_at": r[3],
            "reviewed_at": r[4],
        }
        for r in rows
    ]
    return items, total


async def get_garage_registration_detail(
    db: AsyncSession,
    garage_id: uuid.UUID,
) -> AdminGarageRegistrationDetail:
    stmt = (
        select(Garage, User.full_name, User.email)
        .join(User, Garage.owner_id == User.id)
        .where(Garage.id == garage_id, Garage.deleted_at.is_(None))
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garage registration not found.",
        )
    garage, owner_name, owner_email = row[0], row[1], row[2]

    # Coordinates
    coords_q = select(
        ST_Y(Garage.location.cast(Geometry)),
        ST_X(Garage.location.cast(Geometry)),
    ).where(Garage.id == garage.id)
    coord_row = (await db.execute(coords_q)).first()
    lat = float(coord_row[0]) if coord_row and coord_row[0] is not None else 0.0
    lng = float(coord_row[1]) if coord_row and coord_row[1] is not None else 0.0

    # Services
    services_q = (
        select(Service)
        .join(GarageService, GarageService.service_id == Service.id)
        .where(GarageService.garage_id == garage.id, Service.is_active.is_(True))
        .order_by(Service.name.asc())
    )
    services = list((await db.execute(services_q)).scalars().all())

    # Vehicle types
    vt_q = (
        select(VehicleType)
        .join(GarageVehicleType, GarageVehicleType.vehicle_type_id == VehicleType.id)
        .where(GarageVehicleType.garage_id == garage.id, VehicleType.is_active.is_(True))
        .order_by(VehicleType.name.asc())
    )
    vehicle_types = list((await db.execute(vt_q)).scalars().all())

    # Operating hours
    hours_q = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(hours_q)).scalars().all())

    # Photos
    photos_q = (
        select(GaragePhoto)
        .where(GaragePhoto.garage_id == garage.id, GaragePhoto.deleted_at.is_(None))
        .order_by(GaragePhoto.display_order.asc())
    )
    photos = list((await db.execute(photos_q)).scalars().all())

    return AdminGarageRegistrationDetail(
        garage_id=garage.id,
        name=garage.name,
        description=garage.description,
        phone=garage.phone,
        address=garage.address,
        latitude=lat,
        longitude=lng,
        timezone=garage.timezone,
        approval_status=garage.approval_status.value,
        registration_version=garage.registration_version,
        owner_id=garage.owner_id,
        owner_name=owner_name,
        owner_email=owner_email,
        submitted_at=garage.created_at,
        services=[ServiceRead.model_validate(s) for s in services],
        vehicle_types=[VehicleTypeRead.model_validate(vt) for vt in vehicle_types],
        operating_hours=[
            OperatingHourItem(
                day_of_week=h.day_of_week,
                is_closed=h.is_closed,
                opening_time=h.opening_time,
                closing_time=h.closing_time,
            )
            for h in hours
        ],
        photos=[PhotoRead.model_validate(p) for p in photos],
    )


async def decide_garage_registration(
    db: AsyncSession,
    admin_id: uuid.UUID,
    garage_id: uuid.UUID,
    dto: RegistrationDecisionRequest,
) -> GarageRegistrationStatusResponse:
    stmt = select(Garage).where(Garage.id == garage_id, Garage.deleted_at.is_(None))
    garage = (await db.execute(stmt)).scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garage registration not found.",
        )

    # Must be PENDING
    if garage.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Registration has already been decided ({garage.approval_status.value}). Stale decision rejected.",
        )

    # Must match expected_version
    if dto.expected_version != garage.registration_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version mismatch. Expected version {dto.expected_version}, but current version is {garage.registration_version}.",
        )

    now = datetime.now(tz=timezone.utc)
    new_status = ApprovalStatus.APPROVED if dto.decision == "APPROVE" else ApprovalStatus.REJECTED
    history_status = RegistrationHistoryStatus.APPROVED if dto.decision == "APPROVE" else RegistrationHistoryStatus.REJECTED

    # Update garage status
    garage.approval_status = new_status

    # Update latest history entry
    hist_stmt = (
        select(GarageRegistrationHistory)
        .where(GarageRegistrationHistory.garage_id == garage.id)
        .order_by(GarageRegistrationHistory.submitted_at.desc())
    )
    latest_hist = (await db.execute(hist_stmt)).scalars().first()
    if latest_hist:
        latest_hist.status = history_status
        latest_hist.reviewed_by = admin_id
        latest_hist.reviewed_at = now
        latest_hist.rejection_reason = dto.rejection_reason

    # Record audit log
    action_type = (
        AdminActionType.APPROVE_REGISTRATION
        if dto.decision == "APPROVE"
        else AdminActionType.REJECT_REGISTRATION
    )
    await record_admin_action(
        db=db,
        admin_id=admin_id,
        action_type=action_type,
        target_type="GARAGE",
        target_id=garage.id,
        reason=dto.rejection_reason,
    )

    approved = dto.decision == "APPROVE"
    await notify_user(
        db=db,
        user_id=garage.owner_id,
        notification_type=(
            NotificationType.REGISTRATION_APPROVED
            if approved
            else NotificationType.REGISTRATION_REJECTED
        ),
        title="Garage registration approved" if approved else "Garage registration rejected",
        message=(
            f"Your garage \"{garage.name}\" has been approved and is now publicly visible."
            if approved
            else f"Your garage \"{garage.name}\" was rejected. Reason: {dto.rejection_reason}"
        ),
        related_entity_type="GARAGE",
        related_entity_id=garage.id,
        also_email=True,
    )

    await db.flush()

    from app.schemas.garage_registration import LatestDecisionBrief
    return GarageRegistrationStatusResponse(
        garage_id=garage.id,
        approval_status=garage.approval_status,
        registration_version=garage.registration_version,
        submitted_at=latest_hist.submitted_at if latest_hist else garage.created_at,
        latest_decision=LatestDecisionBrief(
            status=history_status,
            rejection_reason=dto.rejection_reason,
            reviewed_at=now,
        ),
    )


# ── 3. Profile Change Request Moderation ─────────────────────────────────────

async def list_admin_profile_change_requests(
    db: AsyncSession,
    status_filter: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[GarageProfileChangeRequest], int]:
    base_q = (
        select(GarageProfileChangeRequest)
        .join(Garage, GarageProfileChangeRequest.garage_id == Garage.id)
    )
    if status_filter:
        base_q = base_q.where(GarageProfileChangeRequest.status == status_filter)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base_q = base_q.where(func.lower(Garage.name).like(term))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    rows = list(
        (
            await db.execute(
                base_q.order_by(GarageProfileChangeRequest.submitted_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
    )
    return rows, total


async def decide_profile_change_request(
    db: AsyncSession,
    admin_id: uuid.UUID,
    request_id: uuid.UUID,
    dto: ProfileChangeDecisionRequest,
) -> ProfileChangeRequestResponse:
    stmt = select(GarageProfileChangeRequest).where(GarageProfileChangeRequest.id == request_id)
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile change request not found.",
        )

    if req.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request has already been decided ({req.status}). Stale decision rejected.",
        )

    garage = (await db.execute(select(Garage).where(Garage.id == req.garage_id))).scalar_one()

    now = datetime.now(tz=timezone.utc)
    req.reviewed_by = admin_id
    req.reviewed_at = now

    if dto.decision == "APPROVE":
        req.status = "APPROVED"
        changes = req.proposed_changes
        if "name" in changes:
            garage.name = changes["name"]
        if "address" in changes:
            garage.address = changes["address"]
        if "latitude" in changes and "longitude" in changes:
            lat = float(changes["latitude"])
            lng = float(changes["longitude"])
            garage.location = point_from_coords(lat, lng)
            garage.timezone = derive_timezone(lat, lng)

        await record_admin_action(
            db=db,
            admin_id=admin_id,
            action_type=AdminActionType.APPROVE_PROFILE_CHANGE,
            target_type="GARAGE_PROFILE_CHANGE_REQUEST",
            target_id=req.id,
            reason=None,
        )
    else:
        req.status = "REJECTED"
        req.rejection_reason = dto.rejection_reason

        await record_admin_action(
            db=db,
            admin_id=admin_id,
            action_type=AdminActionType.REJECT_PROFILE_CHANGE,
            target_type="GARAGE_PROFILE_CHANGE_REQUEST",
            target_id=req.id,
            reason=dto.rejection_reason,
        )

    approved = dto.decision == "APPROVE"
    await notify_user(
        db=db,
        user_id=req.submitted_by,
        notification_type=(
            NotificationType.PROFILE_CHANGE_APPROVED
            if approved
            else NotificationType.PROFILE_CHANGE_REJECTED
        ),
        title="Profile change approved" if approved else "Profile change rejected",
        message=(
            "Your requested garage profile changes have been applied."
            if approved
            else f"Your requested garage profile changes were rejected. Reason: {dto.rejection_reason}"
        ),
        related_entity_type="GARAGE_PROFILE_CHANGE_REQUEST",
        related_entity_id=req.id,
        also_email=True,
    )

    await db.flush()
    return ProfileChangeRequestResponse.model_validate(req)


# ── 4. Garage Moderation ─────────────────────────────────────────────────────

async def list_admin_garages(
    db: AsyncSession,
    search: str | None = None,
    status_filter: ApprovalStatus | None = None,
    is_suspended: bool | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[Garage], int]:
    base_q = select(Garage).where(Garage.deleted_at.is_(None))
    if status_filter:
        base_q = base_q.where(Garage.approval_status == status_filter)
    if is_suspended is not None:
        base_q = base_q.where(Garage.is_suspended.is_(is_suspended))
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base_q = base_q.where(func.lower(Garage.name).like(term))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    rows = list(
        (
            await db.execute(
                base_q.order_by(Garage.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
    )
    return rows, total


async def moderate_garage(
    db: AsyncSession,
    admin_id: uuid.UUID,
    garage_id: uuid.UUID,
    dto: GarageModerationRequest,
) -> None:
    garage = (
        await db.execute(select(Garage).where(Garage.id == garage_id, Garage.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garage not found.",
        )

    if dto.action == "SUSPEND":
        garage.is_suspended = True
        await record_admin_action(
            db=db,
            admin_id=admin_id,
            action_type=AdminActionType.SUSPEND_GARAGE,
            target_type="GARAGE",
            target_id=garage.id,
            reason=dto.reason,
        )
    else:
        # RESTORE
        if garage.approval_status != ApprovalStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only approved garages can be restored.",
            )
        garage.is_suspended = False
        await record_admin_action(
            db=db,
            admin_id=admin_id,
            action_type=AdminActionType.RESTORE_GARAGE,
            target_type="GARAGE",
            target_id=garage.id,
            reason=dto.reason,
        )

    suspended = dto.action == "SUSPEND"
    await notify_user(
        db=db,
        user_id=garage.owner_id,
        notification_type=(
            NotificationType.GARAGE_SUSPENDED if suspended else NotificationType.GARAGE_RESTORED
        ),
        title="Garage suspended" if suspended else "Garage restored",
        message=(
            f"Your garage \"{garage.name}\" has been suspended. Reason: {dto.reason}"
            if suspended
            else f"Your garage \"{garage.name}\" has been restored and is visible again."
        ),
        related_entity_type="GARAGE",
        related_entity_id=garage.id,
        also_email=True,
    )

    await db.flush()


async def soft_delete_garage(
    db: AsyncSession,
    admin_id: uuid.UUID,
    garage_id: uuid.UUID,
    dto: DeleteGarageRequest,
) -> None:
    garage = (
        await db.execute(select(Garage).where(Garage.id == garage_id, Garage.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garage not found or already deleted.",
        )

    garage.deleted_at = datetime.now(tz=timezone.utc)
    await record_admin_action(
        db=db,
        admin_id=admin_id,
        action_type=AdminActionType.DELETE_GARAGE,
        target_type="GARAGE",
        target_id=garage.id,
        reason=dto.reason,
    )
    await db.flush()


# ── 5. User Moderation ───────────────────────────────────────────────────────

async def list_admin_users(
    db: AsyncSession,
    role: UserRole | None = None,
    account_status: AccountStatus | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[User], int]:
    base_q = select(User).where(User.deleted_at.is_(None))
    if role:
        base_q = base_q.where(User.role == role)
    if account_status:
        base_q = base_q.where(User.account_status == account_status)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base_q = base_q.where(
            func.lower(User.full_name).like(term) | func.lower(User.email).like(term)
        )

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    rows = list(
        (
            await db.execute(
                base_q.order_by(User.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
    )
    return rows, total


async def get_admin_user_detail(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> AdminUserDetailResponse:
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Optional garage
    garage_q = select(Garage).where(Garage.owner_id == user.id, Garage.deleted_at.is_(None))
    garage = (await db.execute(garage_q)).scalar_one_or_none()

    return AdminUserDetailResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified,
        account_status=user.account_status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        garage_id=garage.id if garage else None,
        garage_name=garage.name if garage else None,
    )


async def update_user_status(
    db: AsyncSession,
    admin_id: uuid.UUID,
    user_id: uuid.UUID,
    dto: UserStatusUpdateRequest,
) -> None:
    if user_id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend their own account.",
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify account status of another administrator.",
        )

    user.account_status = dto.status

    if dto.status == AccountStatus.SUSPENDED:
        # Revoke all active refresh sessions
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(tz=timezone.utc))
        )
        action_type = AdminActionType.SUSPEND_USER
    else:
        action_type = AdminActionType.RESTORE_USER

    await record_admin_action(
        db=db,
        admin_id=admin_id,
        action_type=action_type,
        target_type="USER",
        target_id=user.id,
        reason=dto.reason,
    )

    suspended = dto.status == AccountStatus.SUSPENDED
    await notify_user(
        db=db,
        user_id=user.id,
        notification_type=(
            NotificationType.ACCOUNT_SUSPENDED if suspended else NotificationType.ACCOUNT_RESTORED
        ),
        title="Account suspended" if suspended else "Account restored",
        message=(
            f"Your account has been suspended. Reason: {dto.reason}"
            if suspended
            else "Your account has been restored."
        ),
        related_entity_type="USER",
        related_entity_id=user.id,
        also_email=True,
    )
    await db.flush()


# ── 6. Review Reports Moderation ─────────────────────────────────────────────

async def list_admin_review_reports(
    db: AsyncSession,
    status_filter: ReviewReportStatus | None = None,
    reason_filter: ReviewReportReason | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[ReviewReport], int]:
    base_q = select(ReviewReport)
    if status_filter:
        base_q = base_q.where(ReviewReport.status == status_filter)
    if reason_filter:
        base_q = base_q.where(ReviewReport.reason == reason_filter)

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    rows = list(
        (
            await db.execute(
                base_q.order_by(ReviewReport.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
    )
    return rows, total


async def get_admin_review_report_detail(
    db: AsyncSession,
    report_id: uuid.UUID,
) -> AdminReviewReportDetail:
    stmt = (
        select(ReviewReport, Review, Garage.name, User.full_name)
        .join(Review, ReviewReport.review_id == Review.id)
        .join(Garage, Review.garage_id == Garage.id)
        .join(User, ReviewReport.reporter_id == User.id)
        .where(ReviewReport.id == report_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review report not found.",
        )
    report, review, garage_name, reporter_name = row[0], row[1], row[2], row[3]

    return AdminReviewReportDetail(
        id=report.id,
        review_id=review.id,
        review_rating=review.rating,
        review_comment=review.comment,
        review_status=review.status.value,
        garage_id=review.garage_id,
        garage_name=garage_name,
        reporter_id=report.reporter_id,
        reporter_name=reporter_name,
        reason=report.reason,
        details=report.details,
        status=report.status,
        admin_note=report.admin_note,
        reviewed_at=report.reviewed_at,
        created_at=report.created_at,
    )


async def decide_review_report(
    db: AsyncSession,
    admin_id: uuid.UUID,
    report_id: uuid.UUID,
    dto: ReviewReportDecisionRequest,
) -> None:
    stmt = select(ReviewReport).where(ReviewReport.id == report_id)
    report = (await db.execute(stmt)).scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review report not found.",
        )

    if report.status != ReviewReportStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This report has already been reviewed ({report.status.value}).",
        )

    now = datetime.now(tz=timezone.utc)
    report.reviewed_by = admin_id
    report.reviewed_at = now
    report.admin_note = dto.note

    if dto.decision == "REMOVE_REVIEW":
        review = (
            await db.execute(select(Review).where(Review.id == report.review_id))
        ).scalar_one()
        review.status = ReviewStatus.REMOVED
        review.removed_at = now
        review.removed_by = admin_id
        report.status = ReviewReportStatus.REVIEW_REMOVED

        await record_admin_action(
            db=db,
            admin_id=admin_id,
            action_type=AdminActionType.REMOVE_REVIEW,
            target_type="REVIEW",
            target_id=review.id,
            reason=dto.note,
        )
    else:
        report.status = ReviewReportStatus.DISMISSED
        await record_admin_action(
            db=db,
            admin_id=admin_id,
            action_type=AdminActionType.DISMISS_REVIEW_REPORT,
            target_type="REVIEW_REPORT",
            target_id=report.id,
            reason=dto.note,
        )

    removed = dto.decision == "REMOVE_REVIEW"
    await notify_user(
        db=db,
        user_id=report.reporter_id,
        notification_type=NotificationType.REVIEW_REPORT_RESOLVED,
        title="Review report resolved",
        message=(
            "The review you reported has been removed."
            if removed
            else "The review you reported was reviewed and left in place."
        ),
        related_entity_type="REVIEW_REPORT",
        related_entity_id=report.id,
    )

    await db.flush()


# ── 7. Audit Logs ─────────────────────────────────────────────────────────────

async def list_admin_audit_logs(
    db: AsyncSession,
    admin_id: uuid.UUID | None = None,
    action_type: AdminActionType | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[AuditLogEntryResponse], int]:
    base_q = select(AdminAction, User.full_name).join(User, AdminAction.admin_id == User.id)

    if admin_id:
        base_q = base_q.where(AdminAction.admin_id == admin_id)
    if action_type:
        base_q = base_q.where(AdminAction.action_type == action_type)
    if start_date:
        dt_s = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        base_q = base_q.where(AdminAction.created_at >= dt_s)
    if end_date:
        dt_e = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        base_q = base_q.where(AdminAction.created_at <= dt_e)

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    rows = list(
        (
            await db.execute(
                base_q.order_by(AdminAction.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )

    items = [
        AuditLogEntryResponse(
            id=r[0].id,
            admin_id=r[0].admin_id,
            admin_name=r[1],
            action_type=r[0].action_type.value if hasattr(r[0].action_type, "value") else str(r[0].action_type),
            target_type=r[0].target_type,
            target_id=r[0].target_id,
            reason=r[0].reason,
            created_at=r[0].created_at,
        )
        for r in rows
    ]
    return items, total

