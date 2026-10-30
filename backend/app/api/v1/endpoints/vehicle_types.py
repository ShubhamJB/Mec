"""
Endpoints for Vehicle Types Catalog and Garage Vehicle Type Associations.
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
from app.schemas.catalog import (
    CreateCustomVehicleTypeRequest,
    GarageVehicleTypeUpdate,
    VehicleTypeRead,
)
from app.services import catalog_service

vehicle_types_router = APIRouter()
owner_vehicle_types_router = APIRouter()
public_garage_vehicle_types_router = APIRouter()


# ── Public Catalog ────────────────────────────────────────────────────────────

@vehicle_types_router.get(
    "",
    response_model=PaginatedResponse[VehicleTypeRead],
    summary="List active vehicle types",
)
async def list_vehicle_types(
    search: str | None = Query(default=None, description="Search vehicle type by name"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[VehicleTypeRead]:
    items, total = await catalog_service.list_vehicle_types(
        db=db, search=search, page=page, limit=limit
    )
    return PaginatedResponse.build(
        items=[VehicleTypeRead.model_validate(i) for i in items],
        total_items=total,
        page=page,
        limit=limit,
    )


@vehicle_types_router.post(
    "/custom",
    response_model=VehicleTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom vehicle type (verified garage owner)",
)
async def create_custom_vehicle_type(
    body: CreateCustomVehicleTypeRequest,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> VehicleTypeRead:
    vehicle_type = await catalog_service.create_custom_vehicle_type(
        db=db, name=body.name, user_id=current_user.id
    )
    return VehicleTypeRead.model_validate(vehicle_type)


# ── Public Garage Associations ────────────────────────────────────────────────

@public_garage_vehicle_types_router.get(
    "/garages/{garage_id}/vehicle-types",
    response_model=list[VehicleTypeRead],
    summary="List active vehicle types for a publicly visible garage",
)
async def get_garage_vehicle_types(
    garage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[VehicleTypeRead]:
    vehicle_types = await catalog_service.get_garage_vehicle_types(
        db=db, garage_id=garage_id
    )
    return [VehicleTypeRead.model_validate(vt) for vt in vehicle_types]


# ── Owner Garage Associations ─────────────────────────────────────────────────

@owner_vehicle_types_router.post(
    "/garage/vehicle-types",
    response_model=list[VehicleTypeRead],
    summary="Update associated vehicle types for the owner's garage",
)
async def update_garage_vehicle_types(
    body: GarageVehicleTypeUpdate,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[VehicleTypeRead]:
    vehicle_types = await catalog_service.update_owner_garage_vehicle_types(
        db=db, owner_id=current_user.id, vehicle_type_ids=body.vehicle_type_ids
    )
    return [VehicleTypeRead.model_validate(vt) for vt in vehicle_types]


@owner_vehicle_types_router.delete(
    "/garage/vehicle-types/{vehicle_type_id}",
    response_model=MessageResponse,
    summary="Remove a vehicle type from owner's garage (must retain >= 1 if approved)",
)
async def remove_garage_vehicle_type(
    vehicle_type_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await catalog_service.remove_owner_garage_vehicle_type(
        db=db, owner_id=current_user.id, vehicle_type_id=vehicle_type_id
    )
    return MessageResponse(message="Vehicle type removed from garage successfully.")

