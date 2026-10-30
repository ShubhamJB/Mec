"""
Endpoints for Services Catalog and Garage Service Associations.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified_owner
from app.core.pagination import PaginatedResponse
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.catalog import CreateCustomServiceRequest, GarageServiceUpdate, ServiceRead
from app.services import catalog_service

services_router = APIRouter()
owner_services_router = APIRouter()
public_garage_services_router = APIRouter()


# ── Public Catalog ────────────────────────────────────────────────────────────

@services_router.get(
    "",
    response_model=PaginatedResponse[ServiceRead],
    summary="List active predefined and approved custom services",
)
async def list_services(
    search: str | None = Query(default=None, description="Search service by name"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ServiceRead]:
    items, total = await catalog_service.list_services(
        db=db, search=search, page=page, limit=limit
    )
    return PaginatedResponse.build(
        items=[ServiceRead.model_validate(i) for i in items],
        total_items=total,
        page=page,
        limit=limit,
    )


@services_router.post(
    "/custom",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom service (verified garage owner)",
)
async def create_custom_service(
    body: CreateCustomServiceRequest,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> ServiceRead:
    service = await catalog_service.create_custom_service(
        db=db, name=body.name, user_id=current_user.id
    )
    return ServiceRead.model_validate(service)


# ── Public Garage Associations ────────────────────────────────────────────────

@public_garage_services_router.get(
    "/garages/{garage_id}/services",
    response_model=list[ServiceRead],
    summary="List active services for a publicly visible garage",
)
async def get_garage_services(
    garage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ServiceRead]:
    services = await catalog_service.get_garage_services(db=db, garage_id=garage_id)
    return [ServiceRead.model_validate(s) for s in services]


# ── Owner Garage Associations ─────────────────────────────────────────────────

@owner_services_router.post(
    "/garage/services",
    response_model=list[ServiceRead],
    summary="Update associated services for the owner's garage",
)
async def update_garage_services(
    body: GarageServiceUpdate,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[ServiceRead]:
    services = await catalog_service.update_owner_garage_services(
        db=db, owner_id=current_user.id, service_ids=body.service_ids
    )
    return [ServiceRead.model_validate(s) for s in services]


@owner_services_router.delete(
    "/garage/services/{service_id}",
    response_model=MessageResponse,
    summary="Remove a service from owner's garage (must retain >= 1 if approved)",
)
async def remove_garage_service(
    service_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await catalog_service.remove_owner_garage_service(
        db=db, owner_id=current_user.id, service_id=service_id
    )
    return MessageResponse(message="Service removed from garage successfully.")

