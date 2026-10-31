"""Roadside eligibility, privacy-aware requests, and owner lifecycle actions."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from fastapi import HTTPException
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y, ST_Distance, ST_DWithin
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roadside_crypto import decrypt_private_payload, encrypt_private_payload
from app.models.catalog import GarageService, GarageVehicleType, Service, VehicleType
from app.models.enums import (
    AccountStatus,
    ApprovalStatus,
    NotificationType,
    ReviewStatus,
    RoadsideRequestStatus,
)
from app.models.garage import Garage
from app.models.notification import Notification
from app.models.review import Review
from app.models.roadside import RoadsideCapability, RoadsideRequest, RoadsideRequestEvent
from app.models.user import User
from app.schemas.roadside import (
    EligibleGarage,
    EligibleGaragesResponse,
    GuestRoadsideRequestStatusRead,
    RoadsideCapabilityRead,
    RoadsideCapabilityUpdate,
    RoadsideRequestCreate,
    RoadsideRequestEventRead,
    RoadsideRequestProgress,
    RoadsideRequestRead,
)
from app.utils.geo import point_from_coords

REQUEST_TTL = timedelta(minutes=15)
CALL_FOLLOWUP_SLA = timedelta(minutes=3)
COARSE_CELL_DEGREES = 0.05


def _call_followup_failed(request: RoadsideRequest) -> bool:
    return (
        request.status == RoadsideRequestStatus.ACCEPTED
        and request.customer_contact_confirmed is False
        and datetime.now(timezone.utc) >= request.updated_at + CALL_FOLLOWUP_SLA
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Roadside request or garage not found.")


async def _owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    garage = (
        await db.execute(
            select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if garage is None:
        raise HTTPException(status_code=404, detail="No registered garage found for this owner.")
    return garage


async def get_capability(db: AsyncSession, owner_id: uuid.UUID) -> RoadsideCapabilityRead:
    garage = await _owner_garage(db, owner_id)
    capability = (
        await db.execute(
            select(RoadsideCapability).where(RoadsideCapability.garage_id == garage.id)
        )
    ).scalar_one_or_none()
    if capability is None:
        capability = RoadsideCapability(garage_id=garage.id)
        db.add(capability)
        await db.flush()
        await db.refresh(capability)
    return RoadsideCapabilityRead.model_validate(capability)


async def patch_capability(
    db: AsyncSession, owner_id: uuid.UUID, dto: RoadsideCapabilityUpdate
) -> RoadsideCapabilityRead:
    garage = await _owner_garage(db, owner_id)
    capability = (
        await db.execute(
            select(RoadsideCapability)
            .where(RoadsideCapability.garage_id == garage.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if capability is None:
        capability = RoadsideCapability(garage_id=garage.id)
        db.add(capability)
    for field, value in dto.model_dump().items():
        setattr(capability, field, value)
    await db.flush()
    await db.refresh(capability)
    return RoadsideCapabilityRead.model_validate(capability)


async def eligible_garages(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    vehicle_type_id: uuid.UUID,
    service_id: uuid.UUID,
    search_radius_km: int,
) -> EligibleGaragesResponse:
    origin = point_from_coords(latitude, longitude)
    distance_km = (ST_Distance(Garage.location, origin) / 1000.0).label("distance_km")
    reviews = (
        select(
            Review.garage_id,
            func.round(func.avg(Review.rating), 1).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .where(Review.status == ReviewStatus.PUBLISHED, Review.deleted_at.is_(None))
        .group_by(Review.garage_id)
        .subquery()
    )
    stmt = (
        select(
            Garage,
            ST_Y(Garage.location.cast(Geometry)),
            ST_X(Garage.location.cast(Geometry)),
            distance_km,
            RoadsideCapability.response_minutes,
            RoadsideCapability.availability_note,
            reviews.c.avg_rating,
            reviews.c.review_count,
        )
        .join(User, Garage.owner_id == User.id)
        .join(RoadsideCapability, RoadsideCapability.garage_id == Garage.id)
        .join(GarageVehicleType, GarageVehicleType.garage_id == Garage.id)
        .join(GarageService, GarageService.garage_id == Garage.id)
        .join(VehicleType, VehicleType.id == GarageVehicleType.vehicle_type_id)
        .join(Service, Service.id == GarageService.service_id)
        .outerjoin(reviews, reviews.c.garage_id == Garage.id)
        .where(
            Garage.approval_status == ApprovalStatus.APPROVED,
            Garage.is_suspended.is_(False),
            Garage.deleted_at.is_(None),
            User.account_status == AccountStatus.ACTIVE,
            User.deleted_at.is_(None),
            RoadsideCapability.enabled.is_(True),
            RoadsideCapability.is_available.is_(True),
            RoadsideCapability.callback_phone.is_not(None),
            ST_DWithin(Garage.location, origin, search_radius_km * 1000),
            RoadsideCapability.service_radius_km >= distance_km,
            GarageVehicleType.vehicle_type_id == vehicle_type_id,
            VehicleType.is_active.is_(True),
            GarageService.service_id == service_id,
            Service.is_active.is_(True),
        )
        .order_by(distance_km)
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()
    items = [
        EligibleGarage(
            id=row[0].id,
            name=row[0].name,
            latitude=float(row[1]),
            longitude=float(row[2]),
            distance_km=round(float(row[3]), 2),
            average_rating=float(row[6]) if row[6] is not None else None,
            review_count=int(row[7] or 0),
            callback_expectation_minutes=int(row[4]),
            availability_note=row[5],
        )
        for row in rows
    ]
    return EligibleGaragesResponse(items=items, search_radius_km=search_radius_km)


async def _validate_target(
    db: AsyncSession, dto: RoadsideRequestCreate
) -> tuple[Garage, RoadsideCapability]:
    garage = (
        await db.execute(
            select(Garage)
            .join(User, Garage.owner_id == User.id)
            .where(
                Garage.id == dto.garage_id,
                Garage.approval_status == ApprovalStatus.APPROVED,
                Garage.is_suspended.is_(False),
                Garage.deleted_at.is_(None),
                User.account_status == AccountStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if garage is None:
        raise _not_found()
    capability = (
        await db.execute(
            select(RoadsideCapability).where(
                RoadsideCapability.garage_id == garage.id,
                RoadsideCapability.enabled.is_(True),
                RoadsideCapability.is_available.is_(True),
                RoadsideCapability.callback_phone.is_not(None),
            )
        )
    ).scalar_one_or_none()
    if capability is None:
        raise HTTPException(
            status_code=409, detail="This garage is not accepting roadside requests."
        )
    service_match = (
        await db.execute(
            select(GarageService.garage_id)
            .join(Service, Service.id == GarageService.service_id)
            .where(
                GarageService.garage_id == garage.id,
                GarageService.service_id == dto.service_id,
                Service.is_active.is_(True),
            )
        )
    ).first()
    vehicle_match = (
        await db.execute(
            select(GarageVehicleType.garage_id)
            .join(VehicleType, VehicleType.id == GarageVehicleType.vehicle_type_id)
            .where(
                GarageVehicleType.garage_id == garage.id,
                GarageVehicleType.vehicle_type_id == dto.vehicle_type_id,
                VehicleType.is_active.is_(True),
            )
        )
    ).first()
    if service_match is None or vehicle_match is None:
        raise HTTPException(
            status_code=422, detail="Garage does not support the selected service and vehicle type."
        )
    is_nearby = (
        await db.execute(
            select(
                ST_DWithin(
                    Garage.location,
                    point_from_coords(dto.latitude, dto.longitude),
                    capability.service_radius_km * 1000,
                )
            ).where(Garage.id == garage.id)
        )
    ).scalar_one()
    if not is_nearby:
        raise HTTPException(
            status_code=422,
            detail="Customer location is outside this garage's roadside service radius.",
        )
    return garage, capability


def _request_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "RA-" + "".join(secrets.choice(alphabet) for _ in range(8))


def _coarse_coordinate(value: float) -> float:
    cell = int(value / COARSE_CELL_DEGREES)
    return round((cell + 0.5) * COARSE_CELL_DEGREES, 4)


async def _reverse_geocode(latitude: float, longitude: float) -> str | None:
    """Resolve the already-coarsened request position to a human-readable area."""
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 14},
                headers={"User-Agent": "FindYourMechanic/1.0 roadside-location-label"},
            )
            response.raise_for_status()
            payload = response.json()
        address = payload.get("address", {})
        nearby = next(
            (address.get(key) for key in ("neighbourhood", "suburb", "quarter", "city_district", "borough", "district") if address.get(key)),
            None,
        )
        city = next(
            (address.get(key) for key in ("city", "town", "village", "municipality", "county") if address.get(key)),
            None,
        )
        label = ", ".join(dict.fromkeys(part for part in (nearby, city) if part))
        return label[:200] or None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def resolve_location_label(latitude: float, longitude: float) -> str | None:
    return await _reverse_geocode(latitude, longitude)


async def _event(
    db: AsyncSession,
    row: RoadsideRequest,
    actor_id: uuid.UUID | None,
    old: RoadsideRequestStatus | None,
    new: RoadsideRequestStatus,
    metadata: dict[str, str] | None = None,
) -> None:
    db.add(
        RoadsideRequestEvent(
            request_id=row.id,
            actor_user_id=actor_id,
            from_status=old,
            to_status=new,
            safe_metadata=metadata,
        )
    )


async def create_request(
    db: AsyncSession, customer: User | None, dto: RoadsideRequestCreate
) -> RoadsideRequestRead:
    garage, _capability = await _validate_target(db, dto)
    if customer is not None and garage.owner_id == customer.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot request roadside service from your own garage.",
        )
    now = datetime.now(timezone.utc)
    encrypted = encrypt_private_payload(
        {
            "latitude": dto.latitude,
            "longitude": dto.longitude,
            "address": dto.address or "",
            "contact_phone": dto.contact_phone,
        }
    )
    coarse_latitude = _coarse_coordinate(dto.latitude)
    coarse_longitude = _coarse_coordinate(dto.longitude)
    location_label = await _reverse_geocode(coarse_latitude, coarse_longitude)
    row = RoadsideRequest(
        customer_id=customer.id if customer else None,
        garage_id=garage.id,
        request_code=_request_code(),
        vehicle_type_id=dto.vehicle_type_id,
        service_id=dto.service_id,
        problem_description=dto.problem_description,
        location_label=location_label,
        coarse_latitude=coarse_latitude,
        coarse_longitude=coarse_longitude,
        private_data_encrypted=encrypted,
        expires_at=now + REQUEST_TTL,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await _event(db, row, customer.id if customer else None, None, RoadsideRequestStatus.PENDING)
    db.add(
        Notification(
            user_id=garage.owner_id,
            title="New roadside assistance request",
            message=f"Request {row.request_code} is waiting for your response.",
            notification_type=NotificationType.ROADSIDE_REQUEST_RECEIVED,
            related_entity_type="roadside_request",
            related_entity_id=row.id,
        )
    )
    return await _serialize(db, row, garage, reveal=False)


async def _serialize(
    db: AsyncSession, row: RoadsideRequest, garage: Garage, reveal: bool
) -> RoadsideRequestRead:
    fields: dict[str, Any] = decrypt_private_payload(row.private_data_encrypted) if reveal else {}
    events = (
        (
            await db.execute(
                select(RoadsideRequestEvent)
                .where(RoadsideRequestEvent.request_id == row.id)
                .order_by(RoadsideRequestEvent.created_at)
            )
        )
        .scalars()
        .all()
    )
    return RoadsideRequestRead(
        id=row.id,
        request_code=row.request_code,
        garage_id=row.garage_id,
        garage_name=garage.name,
        customer_id=row.customer_id,
        status=row.status,
        vehicle_type_id=row.vehicle_type_id,
        service_id=row.service_id,
        problem_description=row.problem_description,
        location_label=row.location_label,
        coarse_latitude=row.coarse_latitude,
        coarse_longitude=row.coarse_longitude,
        exact_latitude=fields.get("latitude"),
        exact_longitude=fields.get("longitude"),
        address=fields.get("address") or None,
        contact_phone=fields.get("contact_phone"),
        quote_amount=row.quote_amount,
        quote_currency=row.quote_currency,
        eta_minutes=row.eta_minutes,
        accepted_at=row.accepted_at,
        customer_contact_confirmed=row.customer_contact_confirmed,
        owner_calling_at=row.owner_calling_at,
        call_followup_failed=_call_followup_failed(row),
        decline_reason=row.decline_reason,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        events=[RoadsideRequestEventRead.model_validate(event) for event in events],
    )


async def _request_with_garage(
    db: AsyncSession, request_id: uuid.UUID
) -> tuple[RoadsideRequest, Garage]:
    result = await db.execute(
        select(RoadsideRequest, Garage)
        .join(Garage, Garage.id == RoadsideRequest.garage_id)
        .where(RoadsideRequest.id == request_id)
        .with_for_update(of=RoadsideRequest)
    )
    pair = result.first()
    if pair is None:
        raise _not_found()
    return pair[0], pair[1]


async def _expire_if_needed(db: AsyncSession, row: RoadsideRequest) -> None:
    if row.status == RoadsideRequestStatus.PENDING and row.expires_at <= datetime.now(timezone.utc):
        await _transition(db, row, None, RoadsideRequestStatus.EXPIRED, {})


async def expire_pending_requests(db: AsyncSession, limit: int = 500) -> int:
    """Expire overdue requests in bounded batches for a periodic worker/cron job."""
    now = datetime.now(timezone.utc)
    rows = list(
        (
            await db.execute(
                select(RoadsideRequest)
                .where(
                    RoadsideRequest.status == RoadsideRequestStatus.PENDING,
                    RoadsideRequest.expires_at <= now,
                )
                .order_by(RoadsideRequest.expires_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        await _transition(db, row, None, RoadsideRequestStatus.EXPIRED, {})
    return len(rows)


async def list_requests(db: AsyncSession, user: User, owner: bool) -> list[RoadsideRequestRead]:
    stmt = select(RoadsideRequest, Garage).join(Garage, Garage.id == RoadsideRequest.garage_id)
    if owner:
        garage = await _owner_garage(db, user.id)
        stmt = stmt.where(RoadsideRequest.garage_id == garage.id)
    else:
        stmt = stmt.where(RoadsideRequest.customer_id == user.id)
    pairs = (await db.execute(stmt.order_by(RoadsideRequest.created_at.desc()).limit(100))).all()
    results: list[RoadsideRequestRead] = []
    for request, garage in pairs:
        await _expire_if_needed(db, request)
        reveal = not owner or request.status in {
            RoadsideRequestStatus.ACCEPTED,
            RoadsideRequestStatus.CONTACTED,
            RoadsideRequestStatus.CONFIRMED,
            RoadsideRequestStatus.IN_PROGRESS,
            RoadsideRequestStatus.COMPLETED,
            RoadsideRequestStatus.UNABLE_TO_SERVE,
        }
        results.append(await _serialize(db, request, garage, reveal))
    return results


async def get_request(
    db: AsyncSession, user: User, request_id: uuid.UUID, owner: bool
) -> RoadsideRequestRead:
    request, garage = await _request_with_garage(db, request_id)
    if owner:
        if garage.owner_id != user.id:
            raise _not_found()
        reveal = request.status in {
            RoadsideRequestStatus.ACCEPTED,
            RoadsideRequestStatus.CONTACTED,
            RoadsideRequestStatus.CONFIRMED,
            RoadsideRequestStatus.IN_PROGRESS,
            RoadsideRequestStatus.COMPLETED,
            RoadsideRequestStatus.UNABLE_TO_SERVE,
        }
    else:
        if request.customer_id != user.id:
            raise _not_found()
        reveal = True
    await _expire_if_needed(db, request)
    return await _serialize(db, request, garage, reveal)


async def get_guest_request_status(
    db: AsyncSession, request_id: uuid.UUID, contact_phone: str
) -> GuestRoadsideRequestStatusRead:
    request, garage = await _request_with_garage(db, request_id)
    private_data = decrypt_private_payload(request.private_data_encrypted)
    if not secrets.compare_digest(str(private_data.get("contact_phone", "")), contact_phone.strip()):
        raise _not_found()
    await _expire_if_needed(db, request)
    return GuestRoadsideRequestStatusRead(
        request_code=request.request_code,
        garage_name=garage.name,
        status=request.status,
        decline_reason=request.decline_reason,
        quote_amount=request.quote_amount,
        quote_currency=request.quote_currency,
        eta_minutes=request.eta_minutes,
        accepted_at=request.accepted_at,
        customer_contact_confirmed=request.customer_contact_confirmed,
        owner_calling_at=request.owner_calling_at,
        call_followup_failed=_call_followup_failed(request),
        updated_at=request.updated_at,
    )


async def record_customer_contact_check(
    db: AsyncSession,
    request_id: uuid.UUID,
    garage_called: bool,
    customer: User | None,
    contact_phone: str | None,
) -> GuestRoadsideRequestStatusRead:
    request, garage = await _request_with_garage(db, request_id)
    if customer is not None:
        if request.customer_id != customer.id:
            raise _not_found()
    else:
        private_data = decrypt_private_payload(request.private_data_encrypted)
        if contact_phone is None or not secrets.compare_digest(
            str(private_data.get("contact_phone", "")), contact_phone.strip()
        ):
            raise _not_found()
    if request.status != RoadsideRequestStatus.ACCEPTED or request.accepted_at is None:
        raise HTTPException(status_code=409, detail="This request is no longer waiting for a call check.")
    call_check_started_at = request.owner_calling_at or request.accepted_at
    if call_check_started_at + timedelta(seconds=20) > datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="You can confirm the call 20 seconds after the garage accepts or starts calling.")
    if request.customer_contact_confirmed is not None:
        raise HTTPException(status_code=409, detail="You have already answered this call check.")
    request.customer_contact_confirmed = garage_called
    updated_at = datetime.now(timezone.utc)
    request.updated_at = updated_at
    await _event(
        db,
        request,
        customer.id if customer is not None else None,
        request.status,
        request.status,
        {"event": "CUSTOMER_CONFIRMED_CALL" if garage_called else "CUSTOMER_NOT_REACHED"},
    )
    await db.flush()
    if not garage_called:
        db.add(
            Notification(
                user_id=garage.owner_id,
                title="URGENT: Rider has not received a call",
                message=f"High priority: the rider says they have not received a call. Call them now for roadside request {request.request_code}.",
                notification_type=NotificationType.ROADSIDE_REQUEST_UPDATED,
                related_entity_type="roadside_request",
                related_entity_id=request.id,
            )
        )
    return GuestRoadsideRequestStatusRead(
        request_code=request.request_code,
        garage_name=garage.name,
        status=request.status,
        decline_reason=request.decline_reason,
        quote_amount=request.quote_amount,
        quote_currency=request.quote_currency,
        eta_minutes=request.eta_minutes,
        accepted_at=request.accepted_at,
        customer_contact_confirmed=request.customer_contact_confirmed,
        owner_calling_at=request.owner_calling_at,
        call_followup_failed=False,
        updated_at=updated_at,
    )


async def owner_calling_rider(
    db: AsyncSession, owner_id: uuid.UUID, request_id: uuid.UUID
) -> RoadsideRequestRead:
    request, garage = await _request_with_garage(db, request_id)
    if garage.owner_id != owner_id:
        raise _not_found()
    await _expire_if_needed(db, request)
    if request.status != RoadsideRequestStatus.ACCEPTED or request.customer_contact_confirmed is True:
        raise HTTPException(status_code=409, detail="This request is not waiting for a call.")
    if request.owner_calling_at is not None and request.customer_contact_confirmed is None:
        raise HTTPException(status_code=409, detail="The garage has already started calling; wait for the rider's next check.")
    now = datetime.now(timezone.utc)
    request.owner_calling_at = now
    request.customer_contact_confirmed = None
    request.updated_at = now
    await _event(
        db,
        request,
        owner_id,
        request.status,
        request.status,
        {"event": "OWNER_CALLING_RIDER", "message": "The garage is calling you now."},
    )
    if request.customer_id is not None:
        db.add(Notification(
            user_id=request.customer_id,
            title="Garage is calling you now",
            message=f"{garage.name} is calling you now about roadside request {request.request_code}.",
            notification_type=NotificationType.ROADSIDE_REQUEST_UPDATED,
            related_entity_type="roadside_request",
            related_entity_id=request.id,
        ))
    return await _serialize(db, request, garage, reveal=True)


async def _transition(
    db: AsyncSession,
    row: RoadsideRequest,
    actor_id: uuid.UUID | None,
    new_status: RoadsideRequestStatus,
    metadata: dict[str, str],
) -> None:
    now = datetime.now(timezone.utc)
    old = row.status
    conditions = [RoadsideRequest.id == row.id, RoadsideRequest.status == old]
    if old == RoadsideRequestStatus.PENDING:
        conditions.append(RoadsideRequest.expires_at > now)
    values: dict[str, Any] = {"status": new_status, "updated_at": now}
    timestamp_fields = {
        RoadsideRequestStatus.ACCEPTED: "accepted_at",
        RoadsideRequestStatus.CONTACTED: "contacted_at",
        RoadsideRequestStatus.CONFIRMED: "confirmed_at",
        RoadsideRequestStatus.COMPLETED: "completed_at",
    }
    field = timestamp_fields.get(new_status)
    if field:
        values[field] = now
    result = await db.execute(
        update(RoadsideRequest)
        .where(*conditions)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", None) != 1:
        raise HTTPException(
            status_code=409, detail="Request has changed, expired, or is no longer actionable."
        )
    row.status = new_status
    for key, value in values.items():
        if key not in {"status", "updated_at"}:
            setattr(row, key, value)
    await _event(db, row, actor_id, old, new_status, metadata or None)


async def owner_action(
    db: AsyncSession,
    owner_id: uuid.UUID,
    request_id: uuid.UUID,
    action: str,
    reason: str | None = None,
) -> RoadsideRequestRead:
    request, garage = await _request_with_garage(db, request_id)
    if garage.owner_id != owner_id:
        raise _not_found()
    await _expire_if_needed(db, request)
    if action == "accept":
        await _transition(db, request, owner_id, RoadsideRequestStatus.ACCEPTED, {})
        if request.customer_id is not None:
            db.add(
                Notification(
                    user_id=request.customer_id,
                    title="Garage accepted your roadside request",
                    message=f"{garage.name} accepted request {request.request_code} and should call you shortly.",
                    notification_type=NotificationType.ROADSIDE_REQUEST_UPDATED,
                    related_entity_type="roadside_request",
                    related_entity_id=request.id,
                )
            )
    elif action == "decline":
        if request.status != RoadsideRequestStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only pending requests can be declined.")
        safe_reason = " ".join((reason or "Unable to take this request").split())
        if len(safe_reason) < 2:
            raise HTTPException(status_code=422, detail="Decline reason is too short.")
        request.decline_reason = safe_reason
        await _transition(
            db, request, owner_id, RoadsideRequestStatus.DECLINED, {"reason": safe_reason}
        )
        if request.customer_id is not None:
            db.add(
                Notification(
                    user_id=request.customer_id,
                    title="Roadside request declined",
                    message=f"Garage {garage.name} cannot take request {request.request_code}.",
                    notification_type=NotificationType.ROADSIDE_REQUEST_UPDATED,
                    related_entity_type="roadside_request",
                    related_entity_id=request.id,
                )
            )
    return await _serialize(
        db,
        request,
        garage,
        reveal=request.status
        in {
            RoadsideRequestStatus.ACCEPTED,
            RoadsideRequestStatus.CONTACTED,
            RoadsideRequestStatus.CONFIRMED,
            RoadsideRequestStatus.IN_PROGRESS,
            RoadsideRequestStatus.COMPLETED,
            RoadsideRequestStatus.UNABLE_TO_SERVE,
        },
    )


async def update_progress(
    db: AsyncSession,
    owner_id: uuid.UUID,
    request_id: uuid.UUID,
    dto: RoadsideRequestProgress,
) -> RoadsideRequestRead:
    request, garage = await _request_with_garage(db, request_id)
    if garage.owner_id != owner_id:
        raise _not_found()
    transitions = {
        RoadsideRequestStatus.CONTACTED: {RoadsideRequestStatus.ACCEPTED},
        RoadsideRequestStatus.CONFIRMED: {RoadsideRequestStatus.CONTACTED},
        RoadsideRequestStatus.IN_PROGRESS: {RoadsideRequestStatus.CONFIRMED},
        RoadsideRequestStatus.COMPLETED: {RoadsideRequestStatus.IN_PROGRESS},
        RoadsideRequestStatus.UNABLE_TO_SERVE: {
            RoadsideRequestStatus.ACCEPTED,
            RoadsideRequestStatus.CONTACTED,
            RoadsideRequestStatus.CONFIRMED,
            RoadsideRequestStatus.IN_PROGRESS,
        },
    }
    if request.status not in transitions.get(dto.status, set()):
        raise HTTPException(status_code=409, detail="Invalid roadside request status transition.")
    if dto.quote_amount is not None:
        request.quote_amount = dto.quote_amount
        request.quote_currency = dto.quote_currency
    if dto.eta_minutes is not None:
        request.eta_minutes = dto.eta_minutes
    await _transition(db, request, owner_id, dto.status, {})
    if request.customer_id is not None:
        db.add(
            Notification(
                user_id=request.customer_id,
                title="Roadside request updated",
                message=(
                    f"Request {request.request_code} is now "
                    f"{dto.status.value.lower().replace('_', ' ')}."
                ),
                notification_type=NotificationType.ROADSIDE_REQUEST_UPDATED,
                related_entity_type="roadside_request",
                related_entity_id=request.id,
            )
        )
    return await _serialize(
        db,
        request,
        garage,
        reveal=request.status
        in {
            RoadsideRequestStatus.ACCEPTED,
            RoadsideRequestStatus.CONTACTED,
            RoadsideRequestStatus.CONFIRMED,
            RoadsideRequestStatus.IN_PROGRESS,
            RoadsideRequestStatus.COMPLETED,
            RoadsideRequestStatus.UNABLE_TO_SERVE,
        },
    )


async def cancel_request(
    db: AsyncSession, customer_id: uuid.UUID, request_id: uuid.UUID
) -> RoadsideRequestRead:
    request, garage = await _request_with_garage(db, request_id)
    if request.customer_id != customer_id:
        raise _not_found()
    if request.status == RoadsideRequestStatus.CANCELLED:
        return await _serialize(db, request, garage, reveal=False)
    if request.status not in {
        RoadsideRequestStatus.PENDING,
        RoadsideRequestStatus.ACCEPTED,
        RoadsideRequestStatus.CONTACTED,
        RoadsideRequestStatus.CONFIRMED,
    }:
        raise HTTPException(status_code=409, detail="Request can no longer be cancelled.")
    await _transition(db, request, customer_id, RoadsideRequestStatus.CANCELLED, {})
    return await _serialize(db, request, garage, reveal=False)
