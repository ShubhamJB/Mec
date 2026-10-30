"""
Public Discovery and Search Endpoints (/garages/nearby, /garages).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedResponse
from app.db.session import get_db
from app.schemas.discovery import GarageCard, SortByOption
from app.services import discovery_service

router = APIRouter()


@router.get(
    "/nearby",
    response_model=list[GarageCard],
    summary="Get up to 3 nearest eligible garages within 5km (or 10km fallback)",
)
async def get_nearby_garages(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Customer latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Customer longitude"),
    search: str | None = Query(default=None, description="Optional garage name search"),
    service_ids: list[uuid.UUID] | None = Query(default=None, description="Filter by service IDs (ANY)"),
    vehicle_type_ids: list[uuid.UUID] | None = Query(default=None, description="Filter by vehicle type IDs (ANY)"),
    open_now: bool = Query(default=False, description="Filter only currently open garages"),
    db: AsyncSession = Depends(get_db),
) -> list[GarageCard]:
    return await discovery_service.get_nearby_garages(
        db=db,
        latitude=latitude,
        longitude=longitude,
        search=search,
        service_ids=service_ids,
        vehicle_type_ids=vehicle_type_ids,
        open_now=open_now,
    )


@router.get(
    "",
    response_model=PaginatedResponse[GarageCard],
    summary="List eligible garages with optional coordinates (5/10km fallback), filters, and sorting",
)
async def list_garages(
    latitude: float | None = Query(default=None, ge=-90.0, le=90.0),
    longitude: float | None = Query(default=None, ge=-180.0, le=180.0),
    search: str | None = Query(default=None, description="Filter by garage name"),
    service_ids: list[uuid.UUID] | None = Query(default=None, description="Filter by service IDs (ANY)"),
    vehicle_type_ids: list[uuid.UUID] | None = Query(default=None, description="Filter by vehicle type IDs (ANY)"),
    open_now: bool = Query(default=False, description="Filter only currently open garages"),
    sort_by: SortByOption | None = Query(
        default=None,
        description="Sort by: 'nearest' (requires coords), 'highest_rated', or 'most_reviewed'",
    ),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[GarageCard]:
    items, total = await discovery_service.list_garages(
        db=db,
        latitude=latitude,
        longitude=longitude,
        search=search,
        service_ids=service_ids,
        vehicle_type_ids=vehicle_type_ids,
        open_now=open_now,
        sort_by=sort_by,
        page=page,
        limit=limit,
    )
    return PaginatedResponse.build(
        items=items,
        total_items=total,
        page=page,
        limit=limit,
    )

