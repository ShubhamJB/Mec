"""
Administrative Moderation, Approvals, and Audit Endpoints (/admin/*).
"""
from __future__ import annotations

import uuid
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.pagination import PaginatedResponse
from app.db.session import get_db
from app.models.enums import (
    AccountStatus,
    AdminActionType,
    ApprovalStatus,
    ReviewReportReason,
    ReviewReportStatus,
    UserRole,
)
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
from app.schemas.auth import MessageResponse
from app.schemas.garage_profile import ProfileChangeRequestResponse
from app.schemas.garage_registration import GarageRegistrationStatusResponse
from app.services import admin_service

router = APIRouter()


# ── 1. Admin Dashboard ────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Get admin dashboard platform counts and moderation summaries",
)
async def get_admin_dashboard(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardResponse:
    return await admin_service.get_admin_dashboard(db=db)


# ── 2. Garage Registration Moderation ─────────────────────────────────────────

@router.get(
    "/garage-registrations",
    response_model=PaginatedResponse[dict],
    summary="List garage registrations with status filter and search",
)
async def list_garage_registrations(
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[dict]:
    items, total = await admin_service.list_garage_registrations(
        db=db, status_filter=status_filter, search=search, page=page, limit=limit
    )
    return PaginatedResponse.build(items=items, total_items=total, page=page, limit=limit)


@router.get(
    "/garage-registrations/{garage_id}",
    response_model=AdminGarageRegistrationDetail,
    summary="Get full garage registration detail and submission snapshot",
)
async def get_garage_registration(
    garage_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminGarageRegistrationDetail:
    return await admin_service.get_garage_registration_detail(db=db, garage_id=garage_id)


@router.patch(
    "/garage-registrations/{garage_id}",
    response_model=GarageRegistrationStatusResponse,
    summary="Make approval/rejection decision on a PENDING registration (atomic version check)",
)
async def decide_garage_registration(
    garage_id: uuid.UUID,
    body: RegistrationDecisionRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> GarageRegistrationStatusResponse:
    return await admin_service.decide_garage_registration(
        db=db, admin_id=current_admin.id, garage_id=garage_id, dto=body
    )


# ── 3. Profile Change Request Moderation ─────────────────────────────────────

@router.get(
    "/garage-profile-change-requests",
    response_model=PaginatedResponse[ProfileChangeRequestResponse],
    summary="List garage profile change requests",
)
async def list_profile_change_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProfileChangeRequestResponse]:
    items, total = await admin_service.list_admin_profile_change_requests(
        db=db, status_filter=status_filter, search=search, page=page, limit=limit
    )
    return PaginatedResponse.build(
        items=[ProfileChangeRequestResponse.model_validate(i) for i in items],
        total_items=total,
        page=page,
        limit=limit,
    )


@router.patch(
    "/garage-profile-change-requests/{request_id}",
    response_model=ProfileChangeRequestResponse,
    summary="Approve or reject a critical garage profile change request",
)
async def decide_profile_change_request(
    request_id: uuid.UUID,
    body: ProfileChangeDecisionRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ProfileChangeRequestResponse:
    return await admin_service.decide_profile_change_request(
        db=db, admin_id=current_admin.id, request_id=request_id, dto=body
    )


# ── 4. Garage Moderation ─────────────────────────────────────────────────────

@router.get(
    "/garages",
    response_model=PaginatedResponse[dict],
    summary="List all garages with moderation states (suspended, status, search)",
)
async def list_admin_garages(
    search: str | None = Query(default=None),
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
    suspended: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[dict]:
    items, total = await admin_service.list_admin_garages(
        db=db, search=search, status_filter=status_filter, is_suspended=suspended, page=page, limit=limit
    )
    card_dicts = [
        {
            "id": g.id,
            "name": g.name,
            "phone": g.phone,
            "address": g.address,
            "approval_status": g.approval_status.value,
            "is_suspended": g.is_suspended,
            "created_at": g.created_at,
        }
        for g in items
    ]
    return PaginatedResponse.build(items=card_dicts, total_items=total, page=page, limit=limit)


@router.patch(
    "/garages/{garage_id}/moderation",
    response_model=MessageResponse,
    summary="Suspend or restore an approved garage listing",
)
async def moderate_garage(
    garage_id: uuid.UUID,
    body: GarageModerationRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await admin_service.moderate_garage(
        db=db, admin_id=current_admin.id, garage_id=garage_id, dto=body
    )
    return MessageResponse(message=f"Garage successfully {body.action.lower()}ed.")


@router.delete(
    "/garages/{garage_id}",
    response_model=MessageResponse,
    summary="Soft-delete a garage listing (preserves reviews and audit logs)",
)
async def delete_garage(
    garage_id: uuid.UUID,
    body: DeleteGarageRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await admin_service.soft_delete_garage(
        db=db, admin_id=current_admin.id, garage_id=garage_id, dto=body
    )
    return MessageResponse(message="Garage deleted successfully.")


# ── 5. User Moderation ───────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=PaginatedResponse[AdminUserDetailResponse],
    summary="List users filtered by role, account status, and search",
)
async def list_admin_users(
    role: UserRole | None = Query(default=None),
    account_status: AccountStatus | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AdminUserDetailResponse]:
    items, total = await admin_service.list_admin_users(
        db=db, role=role, account_status=account_status, search=search, page=page, limit=limit
    )
    return PaginatedResponse.build(
        items=[AdminUserDetailResponse.model_validate(u) for u in items],
        total_items=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Get user detail including optional owned garage",
)
async def get_admin_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetailResponse:
    return await admin_service.get_admin_user_detail(db=db, user_id=user_id)


@router.patch(
    "/users/{user_id}/status",
    response_model=MessageResponse,
    summary="Change user account status (ACTIVE or SUSPENDED; revokes tokens on suspend)",
)
async def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await admin_service.update_user_status(
        db=db, admin_id=current_admin.id, user_id=user_id, dto=body
    )
    return MessageResponse(message=f"User account status updated to {body.status.value}.")


# ── 6. Review Reports Moderation ─────────────────────────────────────────────

@router.get(
    "/review-reports",
    response_model=PaginatedResponse[dict],
    summary="List review reports with status and reason filters",
)
async def list_review_reports(
    status_filter: ReviewReportStatus | None = Query(default=None, alias="status"),
    reason_filter: ReviewReportReason | None = Query(default=None, alias="reason"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[dict]:
    items, total = await admin_service.list_admin_review_reports(
        db=db, status_filter=status_filter, reason_filter=reason_filter, page=page, limit=limit
    )
    report_dicts = [
        {
            "id": r.id,
            "review_id": r.review_id,
            "reporter_id": r.reporter_id,
            "reason": r.reason.value,
            "status": r.status.value,
            "created_at": r.created_at,
        }
        for r in items
    ]
    return PaginatedResponse.build(items=report_dicts, total_items=total, page=page, limit=limit)


@router.get(
    "/review-reports/{report_id}",
    response_model=AdminReviewReportDetail,
    summary="Get full review report detail including review and garage data",
)
async def get_review_report(
    report_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminReviewReportDetail:
    return await admin_service.get_admin_review_report_detail(db=db, report_id=report_id)


@router.patch(
    "/review-reports/{report_id}",
    response_model=MessageResponse,
    summary="Decide review report: DISMISS or REMOVE_REVIEW (removes review from ratings & blocks author restore)",
)
async def decide_review_report(
    report_id: uuid.UUID,
    body: ReviewReportDecisionRequest,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await admin_service.decide_review_report(
        db=db, admin_id=current_admin.id, report_id=report_id, dto=body
    )
    return MessageResponse(message=f"Report decision '{body.decision}' applied successfully.")


# ── 7. Audit Logs ─────────────────────────────────────────────────────────────

@router.get(
    "/audit-logs",
    response_model=PaginatedResponse[AuditLogEntryResponse],
    summary="List immutable administrative audit logs with filters (admin, action_type, date range)",
)
async def list_audit_logs(
    admin_id: uuid.UUID | None = Query(default=None),
    action_type: AdminActionType | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuditLogEntryResponse]:
    items, total = await admin_service.list_admin_audit_logs(
        db=db,
        admin_id=admin_id,
        action_type=action_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )
    return PaginatedResponse.build(items=items, total_items=total, page=page, limit=limit)

