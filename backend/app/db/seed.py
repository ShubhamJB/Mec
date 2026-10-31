from __future__ import annotations

import asyncio
import os
import random
import secrets
import sys
import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
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
    RegistrationHistoryStatus,
    ReviewReportReason,
    ReviewReportStatus,
    ReviewStatus,
    UserRole,
)
from app.models.garage import Garage, GarageProfileChangeRequest, GarageRegistrationHistory
from app.models.photo import GaragePhoto
from app.models.review import Review, ReviewReport
from app.models.roadside import RoadsideCapability
from app.models.staff import GarageStaff
from app.models.user import User
from app.utils.geo import derive_timezone, point_from_coords

EMAIL_DOMAIN = "seed.example.com"
ADMIN_EMAIL = f"admin@{EMAIL_DOMAIN}"

GARAGE_COUNT = 500
CUSTOMER_COUNT = 200
EVENT_DAYS = 60

SERVICES = [
    "Oil Change",
    "Brake Repair",
    "Tire Replacement",
    "Wheel Alignment",
    "Battery Replacement",
    "Engine Diagnostics",
    "Air Conditioning Service",
    "Clutch Repair",
    "Suspension Repair",
    "Transmission Service",
    "Electrical Repair",
    "Car Wash and Detailing",
    "Puncture Repair",
    "Denting and Painting",
    "General Servicing",
]

VEHICLE_TYPES = [
    "Motorcycle",
    "Scooter",
    "Hatchback",
    "Sedan",
    "SUV",
    "Pickup Truck",
    "Mini Bus",
    "Electric Vehicle",
]

CITIES = [
    ("Kathmandu", 27.7172, 85.3240, 0.07, 0.55),
    ("Lalitpur", 27.6588, 85.3247, 0.04, 0.20),
    ("Bhaktapur", 27.6710, 85.4298, 0.03, 0.10),
    ("Pokhara", 28.2096, 83.9856, 0.05, 0.15),
]

STREETS = [
    "Ring Road",
    "Kalanki Chowk",
    "Baneshwor Marg",
    "Thamel Lane",
    "Pulchowk Road",
    "Koteshwor Road",
    "Balaju Bypass",
    "Chabahil Road",
    "Satdobato Road",
    "Lakeside Road",
    "New Road",
    "Kupondole Marg",
    "Gongabu Chowk",
    "Jawalakhel Road",
    "Suryabinayak Road",
]

NAME_HEADS = [
    "Himalayan",
    "Namaste",
    "Sagarmatha",
    "Annapurna",
    "Everest",
    "Lumbini",
    "Gorkha",
    "Patan",
    "Newa",
    "Yeti",
    "Machhapuchhre",
    "Bagmati",
    "Pashupati",
    "Rapti",
    "Kanchenjunga",
    "Sherpa",
    "Mustang",
    "Phewa",
    "Trishuli",
    "Boudha",
]

NAME_TAILS = [
    "Auto Works",
    "Motors",
    "Garage",
    "Auto Care",
    "Service Center",
    "Motor Workshop",
    "Auto Clinic",
    "Mechanics",
    "Auto Hub",
    "Car Care",
]

FIRST_NAMES = [
    "Aarav", "Anil", "Bikash", "Binod", "Deepak", "Dipesh", "Ganesh", "Hari", "Kiran", "Krishna",
    "Manish", "Nabin", "Prakash", "Rajesh", "Ramesh", "Roshan", "Sagar", "Sanjay",
    "Suresh", "Utsav",
    "Anita", "Asmita", "Bimala", "Gita", "Kabita", "Laxmi", "Mina", "Nisha", "Pooja", "Rita",
    "Sabina", "Sarita", "Sita", "Sunita", "Usha",
]

LAST_NAMES = [
    "Adhikari", "Gurung", "Karki", "Khadka", "Magar", "Neupane", "Pandey", "Poudel", "Rai",
    "Sharma", "Shrestha", "Tamang", "Thapa", "Bhattarai", "Basnet", "Dahal", "Joshi", "Koirala",
    "Lama", "Maharjan",
]

DESCRIPTIONS = [
    "Family-run workshop with over a decade of experience servicing everyday vehicles.",
    "Certified technicians, transparent pricing and quick turnaround on routine servicing.",
    "Specialists in diagnostics and electrical faults for modern vehicles.",
    "Walk-ins welcome. We explain every repair before we start work.",
    "Full-service garage handling mechanical, electrical and body work under one roof.",
    "Trusted by local riders and drivers for honest advice and reliable repairs.",
]

REVIEW_COMMENTS = {
    5: [
        "Fixed the problem the same day and the price matched the quote.",
        "Honest mechanics. They showed me the worn part before replacing it.",
        "Very quick service and the vehicle runs much smoother now.",
        "Friendly staff, clean workshop and fair pricing.",
    ],
    4: [
        "Good work overall, though the waiting area was crowded.",
        "Repair was done well. Took a little longer than promised.",
        "Reliable service, would come back for the next servicing.",
    ],
    3: [
        "Decent job but the final bill was slightly higher than estimated.",
        "Service was okay. Communication could be better.",
    ],
    2: [
        "The issue came back after a week and I had to return.",
        "Long delay and little updates during the repair.",
    ],
    1: [
        "Problem was not fixed and I was still charged in full.",
    ],
}

REJECTION_REASONS = [
    "Address could not be verified from the submitted location.",
    "Phone number appears invalid. Please resubmit with a reachable number.",
    "Description is too vague. Please describe the services you provide.",
]

UNAVAILABLE_MESSAGES = [
    "Closed for the festival season, back soon.",
    "Temporarily closed for workshop renovation.",
    "Owner away, reopening next week.",
]

REPORT_DETAILS = [
    "This review looks copied from another garage.",
    "Contains abusive language towards the staff.",
    "I do not believe this person was a customer.",
    "Unrelated to the garage's services.",
]


def pick_city(rng: random.Random) -> tuple[str, float, float, float]:
    roll = rng.random()
    cumulative = 0.0
    for name, lat, lng, spread, weight in CITIES:
        cumulative += weight
        if roll <= cumulative:
            return name, lat, lng, spread
    name, lat, lng, spread, _ = CITIES[0]
    return name, lat, lng, spread


def build_hours(rng: random.Random, garage_id: uuid.UUID) -> list[OperatingHours]:
    opening = time(rng.choice([7, 8, 9]), rng.choice([0, 30]))
    closing = time(rng.choice([17, 18, 19, 20]), 0)
    closed_days = {6} if rng.random() < 0.7 else {7}
    if rng.random() < 0.15:
        closed_days = set()
    rows = []
    for day in range(1, 8):
        is_closed = day in closed_days
        rows.append(
            OperatingHours(
                garage_id=garage_id,
                day_of_week=day,
                is_closed=is_closed,
                opening_time=None if is_closed else opening,
                closing_time=None if is_closed else closing,
            )
        )
    return rows


def pick_status(rng: random.Random) -> tuple[ApprovalStatus, bool]:
    roll = rng.random()
    if roll < 0.82:
        return ApprovalStatus.APPROVED, False
    if roll < 0.86:
        return ApprovalStatus.APPROVED, True
    if roll < 0.95:
        return ApprovalStatus.PENDING, False
    return ApprovalStatus.REJECTED, False


def weighted_rating(rng: random.Random) -> int:
    return rng.choices([5, 4, 3, 2, 1], weights=[44, 30, 14, 8, 4])[0]


async def seed() -> None:
    rng = random.Random(42)
    now = datetime.now(tz=timezone.utc)

    password = os.environ.get("SEED_PASSWORD") or secrets.token_urlsafe(12)
    password_hash = hash_password(password)
    city_timezones = {name: derive_timezone(lat, lng) for name, lat, lng, _, _ in CITIES}

    async with AsyncSessionLocal() as session:
        existing_admin = (
            await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()
        existing_owner = (
            await session.execute(select(User).where(User.email == f"owner0002@{EMAIL_DOMAIN}"))
        ).scalar_one_or_none()
        existing = existing_admin is not None
        if existing:
            # The Compose seed profile supplies a stable local password, so this command
            # remains useful on an already-seeded developer database without duplicating data.
            if password:
                users = (
                    await session.execute(
                        select(User).where(User.email.like(f"%@{EMAIL_DOMAIN}"))
                    )
                ).scalars().all()
                for user in users:
                    user.password_hash = password_hash
            if existing_owner is not None:
                demo_garage = (
                    await session.execute(
                        select(Garage).where(Garage.owner_id == existing_owner.id)
                    )
                ).scalar_one_or_none()
                if demo_garage is not None:
                    demo_garage.approval_status = ApprovalStatus.APPROVED
                    demo_garage.is_suspended = False
                    demo_garage.location = point_from_coords(27.7172, 85.3240)
                    demo_garage.timezone = derive_timezone(27.7172, 85.3240)
                    capability = (
                        await session.execute(
                            select(RoadsideCapability).where(
                                RoadsideCapability.garage_id == demo_garage.id
                            )
                        )
                    ).scalar_one_or_none()
                    if capability is None:
                        capability = RoadsideCapability(garage_id=demo_garage.id)
                        session.add(capability)
                    capability.enabled = True
                    capability.is_available = True
                    capability.service_radius_km = 25
                    capability.availability_note = (
                        "Seeded demo garage accepting roadside requests."
                    )
                    capability.callback_phone = demo_garage.phone
                    capability.response_minutes = 15
                    engine_diagnostics = (
                        await session.execute(
                            select(Service).where(
                                func.lower(Service.name) == "engine diagnostics",
                                Service.is_active.is_(True),
                            )
                        )
                    ).scalar_one_or_none()
                    electric_vehicle = (
                        await session.execute(
                            select(VehicleType).where(
                                func.lower(VehicleType.name) == "electric vehicle",
                                VehicleType.is_active.is_(True),
                            )
                        )
                    ).scalar_one_or_none()
                    if engine_diagnostics is not None:
                        has_service = (
                            await session.execute(
                                select(GarageService).where(
                                    GarageService.garage_id == demo_garage.id,
                                    GarageService.service_id == engine_diagnostics.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if has_service is None:
                            session.add(
                                GarageService(
                                    garage_id=demo_garage.id,
                                    service_id=engine_diagnostics.id,
                                )
                            )
                    if electric_vehicle is not None:
                        has_vehicle_type = (
                            await session.execute(
                                select(GarageVehicleType).where(
                                    GarageVehicleType.garage_id == demo_garage.id,
                                    GarageVehicleType.vehicle_type_id == electric_vehicle.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if has_vehicle_type is None:
                            session.add(
                                GarageVehicleType(
                                    garage_id=demo_garage.id,
                                    vehicle_type_id=electric_vehicle.id,
                                )
                            )
            await session.commit()
            print(
                "Seed data already present; the owner0002 roadside demo was "
                "updated for Kathmandu Electric Vehicle and Engine Diagnostics searches."
            )
            if existing_admin:
                print(f"  Admin user ID:        {existing_admin.id}")
                print(f"  Admin login email:    {existing_admin.email}")
            if existing_owner:
                print(f"  Garage owner user ID: {existing_owner.id}")
                print(f"  Garage owner login:   {existing_owner.email} (garage owner0002)")
            if password:
                print(f"  Shared password:      {password}")
                print("  Password reset applied to all seeded accounts.")
            else:
                print("  No SEED_PASSWORD was set; existing passwords are unchanged and cannot be recovered.")
            return

        existing_services = {
            s.name.lower(): s for s in (await session.execute(select(Service))).scalars().all()
        }
        services: list[Service] = []
        for name in SERVICES:
            service = existing_services.get(name.lower()) or Service(name=name, is_predefined=True)
            if service.id is None:
                session.add(service)
            services.append(service)

        existing_types = {
            v.name.lower(): v for v in (await session.execute(select(VehicleType))).scalars().all()
        }
        vehicle_types: list[VehicleType] = []
        for name in VEHICLE_TYPES:
            vehicle_type = existing_types.get(name.lower()) or VehicleType(
                name=name, is_predefined=True
            )
            if vehicle_type.id is None:
                session.add(vehicle_type)
            vehicle_types.append(vehicle_type)
        await session.flush()

        admin = User(
            full_name="Seed Admin",
            email=ADMIN_EMAIL,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            email_verified=True,
            account_status=AccountStatus.ACTIVE,
        )
        session.add(admin)

        customers: list[User] = []
        for i in range(1, CUSTOMER_COUNT + 1):
            suspended = i > CUSTOMER_COUNT - 3
            customers.append(
                User(
                    full_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    email=f"customer{i:04d}@{EMAIL_DOMAIN}",
                    password_hash=password_hash,
                    role=UserRole.CUSTOMER,
                    email_verified=True,
                    account_status=AccountStatus.SUSPENDED if suspended else AccountStatus.ACTIVE,
                )
            )
        session.add_all(customers)

        owners: list[User] = []
        for i in range(1, GARAGE_COUNT + 1):
            owners.append(
                User(
                    full_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    email=f"owner{i:04d}@{EMAIL_DOMAIN}",
                    password_hash=password_hash,
                    role=UserRole.GARAGE_OWNER,
                    email_verified=True,
                    account_status=AccountStatus.ACTIVE,
                )
            )
        session.add_all(owners)
        await session.flush()

        active_customers = [c for c in customers if c.account_status == AccountStatus.ACTIVE]
        public_garages: list[Garage] = []
        approved_garages: list[Garage] = []
        garages: list[Garage] = []
        reviews: list[Review] = []
        counts = {
            "photos": 0,
            "events": 0,
            "audit": 0,
            "pending_changes": 0,
            "staff": 0,
            "inactive_staff": 0,
        }

        for index, owner in enumerate(owners, start=1):
            if index == 2:
                city, latitude, longitude = "Kathmandu", 27.7172, 85.3240
            else:
                city, base_lat, base_lng, spread = pick_city(rng)
                latitude = round(base_lat + rng.uniform(-spread, spread), 6)
                longitude = round(base_lng + rng.uniform(-spread, spread), 6)
            approval_status, is_suspended = pick_status(rng)
            if index == 2:
                approval_status = ApprovalStatus.APPROVED
                is_suspended = False
            created_at = now - timedelta(days=rng.randint(10, 400))
            name = f"{rng.choice(NAME_HEADS)} {rng.choice(NAME_TAILS)}"
            phone = f"+97798{rng.randint(10000000, 99999999)}"
            address = f"{rng.randint(1, 120)} {rng.choice(STREETS)}, {city}"
            description = rng.choice(DESCRIPTIONS)

            unavailable = approval_status == ApprovalStatus.APPROVED and rng.random() < 0.05
            garage = Garage(
                owner_id=owner.id,
                name=name,
                description=description,
                phone=phone,
                address=address,
                location=point_from_coords(latitude, longitude),
                timezone=city_timezones[city],
                approval_status=approval_status,
                is_suspended=is_suspended,
                is_temporarily_unavailable=unavailable,
                temporary_unavailability_message=rng.choice(UNAVAILABLE_MESSAGES)
                if unavailable
                else None,
                registration_version=1,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(garage)
            await session.flush()
            garages.append(garage)

            garage_services = rng.sample(services, rng.randint(2, 6))
            garage_types = rng.sample(vehicle_types, rng.randint(1, 4))
            if index == 2:
                garage_services = services
                garage_types = vehicle_types
            for service in garage_services:
                session.add(GarageService(garage_id=garage.id, service_id=service.id))
            for vehicle_type in garage_types:
                session.add(
                    GarageVehicleType(garage_id=garage.id, vehicle_type_id=vehicle_type.id)
                )
            if index == 2:
                session.add(
                    RoadsideCapability(
                        garage_id=garage.id,
                        enabled=True,
                        is_available=True,
                        service_radius_km=25,
                        availability_note="Seeded demo garage accepting roadside requests.",
                        callback_phone=phone,
                        response_minutes=15,
                    )
                )
            session.add_all(build_hours(rng, garage.id))

            history_status = RegistrationHistoryStatus(approval_status.value)
            reviewed_at = (
                created_at + timedelta(days=rng.randint(1, 3))
                if approval_status != ApprovalStatus.PENDING
                else None
            )
            rejection_reason = (
                rng.choice(REJECTION_REASONS)
                if approval_status == ApprovalStatus.REJECTED
                else None
            )
            session.add(
                GarageRegistrationHistory(
                    garage_id=garage.id,
                    reviewed_by=admin.id if reviewed_at else None,
                    status=history_status,
                    submission_data={
                        "name": name,
                        "description": description,
                        "phone": phone,
                        "address": address,
                        "latitude": latitude,
                        "longitude": longitude,
                        "services": [s.name for s in garage_services],
                        "vehicle_types": [v.name for v in garage_types],
                    },
                    rejection_reason=rejection_reason,
                    submitted_at=created_at,
                    reviewed_at=reviewed_at,
                )
            )
            if reviewed_at:
                session.add(
                    AdminAction(
                        admin_id=admin.id,
                        action_type=AdminActionType.APPROVE_REGISTRATION
                        if approval_status == ApprovalStatus.APPROVED
                        else AdminActionType.REJECT_REGISTRATION,
                        target_type="GARAGE",
                        target_id=garage.id,
                        reason=rejection_reason,
                        created_at=reviewed_at,
                    )
                )
                counts["audit"] += 1
            if is_suspended:
                session.add(
                    AdminAction(
                        admin_id=admin.id,
                        action_type=AdminActionType.SUSPEND_GARAGE,
                        target_type="GARAGE",
                        target_id=garage.id,
                        reason="Repeated complaints from customers.",
                        created_at=now - timedelta(days=rng.randint(1, 20)),
                    )
                )
                counts["audit"] += 1

            if approval_status == ApprovalStatus.APPROVED:
                approved_garages.append(garage)
                for order in range(rng.randint(1, 3)):
                    session.add(
                        GaragePhoto(
                            garage_id=garage.id,
                            url=f"https://picsum.photos/seed/garage-{index}-{order}/1200/800",
                            storage_key=f"seed/garages/{garage.id}/{order}.jpg",
                            caption=None,
                            display_order=order,
                        )
                    )
                    counts["photos"] += 1

                if rng.random() < 0.03:
                    session.add(
                        GarageProfileChangeRequest(
                            garage_id=garage.id,
                            submitted_by=owner.id,
                            proposed_changes={
                                "address": f"{rng.randint(1, 120)} {rng.choice(STREETS)}, {city}"
                            },
                            status="PENDING",
                            submitted_at=now - timedelta(days=rng.randint(0, 5)),
                        )
                    )
                    counts["pending_changes"] += 1

            if approval_status == ApprovalStatus.APPROVED and not is_suspended:
                public_garages.append(garage)

        await session.flush()

        for garage in approved_garages:
            popularity = rng.choice([0, 0, 1, 2, 3, 5, 8, 12])
            reviewers = rng.sample(
                active_customers, min(popularity, len(active_customers))
            )
            for customer in reviewers:
                rating = weighted_rating(rng)
                comment = (
                    rng.choice(REVIEW_COMMENTS[rating]) if rng.random() < 0.75 else None
                )
                created = now - timedelta(days=rng.randint(0, 180), hours=rng.randint(0, 23))
                reviews.append(
                    Review(
                        garage_id=garage.id,
                        customer_id=customer.id,
                        rating=rating,
                        comment=comment,
                        status=ReviewStatus.PUBLISHED,
                        created_at=created,
                        updated_at=created,
                    )
                )
        session.add_all(reviews)
        await session.flush()

        reportable = rng.sample(reviews, min(25, len(reviews)))
        report_count = 0
        for review in reportable:
            reporter = rng.choice(
                [c for c in active_customers if c.id != review.customer_id]
            )
            session.add(
                ReviewReport(
                    review_id=review.id,
                    reporter_id=reporter.id,
                    reason=rng.choice(list(ReviewReportReason)),
                    details=rng.choice(REPORT_DETAILS),
                    status=ReviewReportStatus.PENDING,
                    created_at=now - timedelta(days=rng.randint(0, 10)),
                )
            )
            report_count += 1

        event_total = 0
        for garage in public_garages:
            weight = rng.choice([2, 5, 10, 20, 40])
            for _ in range(weight):
                occurred = now - timedelta(
                    days=rng.randint(0, EVENT_DAYS - 1),
                    hours=rng.randint(0, 23),
                    minutes=rng.randint(0, 59),
                )
                session.add(
                    AnalyticsEvent(
                        garage_id=garage.id,
                        customer_id=None,
                        event_type=AnalyticsEventType.PROFILE_VIEW,
                        created_at=occurred,
                    )
                )
                event_total += 1
                if rng.random() < 0.25:
                    session.add(
                        AnalyticsEvent(
                            garage_id=garage.id,
                            customer_id=None,
                            event_type=AnalyticsEventType.CALL_CLICK,
                            created_at=occurred + timedelta(minutes=rng.randint(1, 5)),
                        )
                    )
                    event_total += 1
        counts["events"] = event_total

        staff_roles = [
            "Mechanic",
            "Senior Mechanic",
            "Auto Electrician",
            "Service Technician",
            "Service Advisor",
        ]
        for index, garage in enumerate(garages, start=1):
            if index == 1:
                staff_count = 0
            elif index == 3:
                staff_count = 2
            else:
                staff_count = 0 if rng.random() < 0.45 else rng.randint(1, 3)

            for _ in range(staff_count):
                is_active = rng.random() >= 0.08
                session.add(
                    GarageStaff(
                        garage_id=garage.id,
                        full_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                        phone=f"+97798{rng.randint(10000000, 99999999)}",
                        role_title=rng.choice(staff_roles),
                        is_active=is_active,
                    )
                )
                counts["staff"] += 1
                if not is_active:
                    counts["inactive_staff"] += 1

        await session.commit()

    print("Seed complete.")
    print(
        f"  garages:           {GARAGE_COUNT} "
        f"({len(approved_garages)} approved, {len(public_garages)} publicly visible)"
    )
    print(f"  owners:            {GARAGE_COUNT}")
    print(f"  customers:         {CUSTOMER_COUNT}")
    print(f"  services:          {len(services)}")
    print(f"  vehicle types:     {len(vehicle_types)}")
    print(f"  reviews:           {len(reviews)}")
    print(f"  review reports:    {report_count} (pending)")
    print(f"  photos:            {counts['photos']}")
    print(f"  analytics events:  {counts['events']}")
    print(f"  pending changes:   {counts['pending_changes']}")
    print(f"  audit log rows:    {counts['audit']}")
    print(f"  staff members:     {counts['staff']} ({counts['inactive_staff']} inactive)")
    print()
    demo_owner = owners[1]
    print("Local demo credentials (all seeded accounts share this password):")
    print(f"  Admin user ID:        {admin.id}")
    print(f"  Admin login email:    {admin.email}")
    print(f"  Garage owner user ID: {demo_owner.id}")
    print(f"  Garage owner login:   {demo_owner.email} (garage owner0002)")
    print(f"  Shared password:      {password}")
    print("All other seeded owners/customers use the same password.")
    print("Set SEED_PASSWORD in backend/.env to choose a predictable local password.")


async def main() -> None:
    engine.echo = False
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
