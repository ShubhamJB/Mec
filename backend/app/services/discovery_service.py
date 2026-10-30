"""
Discovery service: PostGIS nearby radius search (5km / 10km fallback),
multi-criteria filtering, and paginated listing.
"""
from __future__ import annotations

import uuid
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_X, ST_Y
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    GarageService,
    GarageVehicleType,
    OperatingHours,
    Service,
    VehicleType,
)
from app.models.enums import AccountStatus, ApprovalStatus, ReviewStatus
from app.models.garage import Garage
from app.models.photo import GaragePhoto
from app.models.review import Review
from app.models.user import User
from app.schemas.discovery import GarageCard, SortByOption
from app.schemas.garage_profile import AvailabilityResponse
from app.utils.availability import calculate_garage_availability
from app.utils.geo import point_from_coords


# ── Subqueries for reviews and cover photos ───────────────────────────────────

def _get_reviews_subquery():
    return (
        select(
            Review.garage_id,
            func.round(func.avg(Review.rating), 1).label("avg_rating"),
            func.count(Review.id).label("rev_count"),
        )
        .where(
            Review.deleted_at.is_(None),
            Review.status == ReviewStatus.PUBLISHED,
        )
        .group_by(Review.garage_id)
        .subquery()
    )


def _get_cover_photos_subquery():
    min_order_subq = (
        select(
            GaragePhoto.garage_id,
            func.min(GaragePhoto.display_order).label("min_order"),
        )
        .where(GaragePhoto.deleted_at.is_(None))
        .group_by(GaragePhoto.garage_id)
        .subquery()
    )
    return (
        select(
            GaragePhoto.garage_id,
            GaragePhoto.url.label("cover_url"),
        )
        .join(
            min_order_subq,
            (GaragePhoto.garage_id == min_order_subq.c.garage_id)
            & (GaragePhoto.display_order == min_order_subq.c.min_order),
        )
        .where(GaragePhoto.deleted_at.is_(None))
        .subquery()
    )


# ── Core Query Builder ────────────────────────────────────────────────────────

def _build_base_discovery_query(
    origin_point: WKTElement | None = None,
    radius_meters: float | None = None,
    search: str | None = None,
    service_ids: list[uuid.UUID] | None = None,
    vehicle_type_ids: list[uuid.UUID] | None = None,
):
    rev_subq = _get_reviews_subquery()
    photo_subq = _get_cover_photos_subquery()

    dist_col = (
        (ST_Distance(Garage.location, origin_point) / 1000.0).label("distance_km")
        if origin_point is not None
        else func.null().label("distance_km")
    )

    query = (
        select(
            Garage,
            ST_Y(Garage.location.cast(func.geometry())).label("latitude"),
            ST_X(Garage.location.cast(func.geometry())).label("longitude"),
            dist_col,
            rev_subq.c.avg_rating,
            func.coalesce(rev_subq.c.rev_count, 0).label("review_count"),
            photo_subq.c.cover_url,
        )
        .join(User, Garage.owner_id == User.id)
        .outerjoin(rev_subq, Garage.id == rev_subq.c.garage_id)
        .outerjoin(photo_subq, Garage.id == photo_subq.c.garage_id)
        .where(
            # Public eligibility rule:
            # Approved AND not garage-suspended AND not deleted AND owner ACTIVE and not deleted
            Garage.approval_status == ApprovalStatus.APPROVED,
            Garage.is_suspended.is_(False),
            Garage.deleted_at.is_(None),
            User.account_status == AccountStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    )

    # Search by garage name
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.where(func.lower(Garage.name).like(term))

    # Multi-select services (ANY within group)
    if service_ids:
        service_subq = (
            select(GarageService.garage_id)
            .join(Service, GarageService.service_id == Service.id)
            .where(Service.id.in_(service_ids), Service.is_active.is_(True))
        )
        query = query.where(Garage.id.in_(service_subq))

    # Multi-select vehicle types (ANY within group)
    if vehicle_type_ids:
        vt_subq = (
            select(GarageVehicleType.garage_id)
            .join(VehicleType, GarageVehicleType.vehicle_type_id == VehicleType.id)
            .where(VehicleType.id.in_(vehicle_type_ids), VehicleType.is_active.is_(True))
        )
        query = query.where(Garage.id.in_(vt_subq))

    # Radius constraint using PostGIS ST_DWithin
    if origin_point is not None and radius_meters is not None:
        query = query.where(ST_DWithin(Garage.location, origin_point, radius_meters))

    return query


# ── Availability Loader & Card Builder ────────────────────────────────────────

async def _fetch_operating_hours_for_garages(
    db: AsyncSession, garage_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[OperatingHours]]:
    if not garage_ids:
        return {}
    stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id.in_(garage_ids))
        .order_by(OperatingHours.day_of_week.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    mapping: dict[uuid.UUID, list[OperatingHours]] = {gid: [] for gid in garage_ids}
    for r in rows:
        mapping[r.garage_id].append(r)
    return mapping


def _build_garage_card(row: Any, hours: list[OperatingHours]) -> GarageCard:
    garage = row[0]
    lat = float(row[1]) if row[1] is not None else 0.0
    lng = float(row[2]) if row[2] is not None else 0.0
    dist_km = round(float(row[3]), 2) if row[3] is not None else None
    avg_rating = float(row[4]) if row[4] is not None else None
    rev_count = int(row[5]) if row[5] is not None else 0
    cover_url = row[6]

    avail_dict = calculate_garage_availability(
        is_temporarily_unavailable=garage.is_temporarily_unavailable,
        temporary_unavailability_message=garage.temporary_unavailability_message,
        timezone_str=garage.timezone,
        operating_hours=hours,
    )

    return GarageCard(
        id=garage.id,
        name=garage.name,
        latitude=lat,
        longitude=lng,
        distance_km=dist_km,
        average_rating=avg_rating,
        review_count=rev_count,
        availability=AvailabilityResponse(**avail_dict),
        phone=garage.phone,
        cover_photo_url=cover_url,
    )


# ── GET /garages/nearby ───────────────────────────────────────────────────────

async def get_nearby_garages(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    search: str | None = None,
    service_ids: list[uuid.UUID] | None = None,
    vehicle_type_ids: list[uuid.UUID] | None = None,
    open_now: bool = False,
) -> list[GarageCard]:
    origin_point = point_from_coords(latitude, longitude)

    # 1. Search 5 km radius
    q_5km = _build_base_discovery_query(
        origin_point=origin_point,
        radius_meters=5000,
        search=search,
        service_ids=service_ids,
        vehicle_type_ids=vehicle_type_ids,
    ).order_by("distance_km")

    rows_5km = list((await db.execute(q_5km)).all())
    target_rows = rows_5km

    # 2. If fewer than 3 matching garages, expand to 10 km
    if len(rows_5km) < 3:
        q_10km = _build_base_discovery_query(
            origin_point=origin_point,
            radius_meters=10000,
            search=search,
            service_ids=service_ids,
            vehicle_type_ids=vehicle_type_ids,
        ).order_by("distance_km")
        target_rows = list((await db.execute(q_10km)).all())

    # 3. Load operating hours to compute availability and filter open_now
    garage_ids = [r[0].id for r in target_rows]
    hours_map = await _fetch_operating_hours_for_garages(db, garage_ids)

    cards: list[GarageCard] = []
    for r in target_rows:
        card = _build_garage_card(r, hours_map.get(r[0].id, []))
        if open_now and card.availability.status != "OPEN":
            continue
        cards.append(card)
        if len(cards) == 3:
            break

    return cards


# ── GET /garages (Listing) ───────────────────────────────────────────────────

async def list_garages(
    db: AsyncSession,
    latitude: float | None = None,
    longitude: float | None = None,
    search: str | None = None,
    service_ids: list[uuid.UUID] | None = None,
    vehicle_type_ids: list[uuid.UUID] | None = None,
    open_now: bool = False,
    sort_by: SortByOption | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[GarageCard], int]:
    # Validate coordinate pairing
    has_lat = latitude is not None
    has_lng = longitude is not None
    if has_lat != has_lng:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latitude and longitude must both be provided together.",
        )

    if sort_by == "nearest" and not has_lat:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sorting by 'nearest' requires latitude and longitude.",
        )

    origin_point = point_from_coords(latitude, longitude) if has_lat else None

    # Handle radius fallback if coordinates provided
    chosen_radius: float | None = None
    if origin_point is not None:
        count_5km_q = select(func.count(Garage.id)).where(
            Garage.approval_status == ApprovalStatus.APPROVED,
            Garage.is_suspended.is_(False),
            Garage.deleted_at.is_(None),
            ST_DWithin(Garage.location, origin_point, 5000),
        )
        count_5km = (await db.execute(count_5km_q)).scalar_one()
        chosen_radius = 5000.0 if count_5km >= 3 else 10000.0

    query = _build_base_discovery_query(
        origin_point=origin_point,
        radius_meters=chosen_radius,
        search=search,
        service_ids=service_ids,
        vehicle_type_ids=vehicle_type_ids,
    )

    # Sorting
    if sort_by == "nearest" or (sort_by is None and origin_point is not None):
        query = query.order_by("distance_km")
    elif sort_by == "highest_rated":
        # Average rating desc (unrated NULLS LAST), then review count desc, then name asc
        query = query.order_by(
            func.coalesce(select(_get_reviews_subquery().c.avg_rating).scalar_subquery(), -1.0).desc(),
            "review_count",
            Garage.name.asc(),
        )
    elif sort_by == "most_reviewed":
        query = query.order_by("review_count", Garage.name.asc())
    else:
        # Default without coordinates: highest rated / name
        query = query.order_by(Garage.name.asc())

    # If open_now filter is active, we evaluate availability in application memory
    if open_now:
        all_rows = list((await db.execute(query)).all())
        all_ids = [r[0].id for r in all_rows]
        hours_map = await _fetch_operating_hours_for_garages(db, all_ids)

        filtered_cards: list[GarageCard] = []
        for r in all_rows:
            card = _build_garage_card(r, hours_map.get(r[0].id, []))
            if card.availability.status == "OPEN":
                filtered_cards.append(card)

        total_items = len(filtered_cards)
        paginated_cards = filtered_cards[(page - 1) * limit : page * limit]
        return paginated_cards, total_items

    # Standard database pagination
    count_stmt = select(func.count()).select_from(query.subquery())
    total_items = (await db.execute(count_stmt)).scalar_one()

    paginated_query = query.offset((page - 1) * limit).limit(limit)
    rows = list((await db.execute(paginated_query)).all())

    garage_ids = [r[0].id for r in rows]
    hours_map = await _fetch_operating_hours_for_garages(db, garage_ids)

    cards = [_build_garage_card(r, hours_map.get(r[0].id, [])) for r in rows]
    return cards, total_items
