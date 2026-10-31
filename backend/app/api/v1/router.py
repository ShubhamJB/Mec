"""
Centralised __init__ for app/api/v1 — imports all routers.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    garages_discovery,
    garages_public,
    notifications,
    owner_analytics,
    owner_garage,
    owner_garage_registration,
    owner_photos,
    owner_staff,
    reviews,
    roadside,
    users,
)
from app.api.v1.endpoints.services import (
    owner_services_router,
    public_garage_services_router,
    services_router,
)
from app.api.v1.endpoints.vehicle_types import (
    owner_vehicle_types_router,
    public_garage_vehicle_types_router,
    vehicle_types_router,
)

api_router = APIRouter()

# Auth & Users
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Garage Registration (Owner)
api_router.include_router(
    owner_garage_registration.router, prefix="/owner", tags=["owner-registration"]
)

# Garage Profile & Management (Owner)
api_router.include_router(owner_garage.router, prefix="/owner", tags=["owner-garage"])
api_router.include_router(owner_photos.router, prefix="/owner", tags=["owner-photos"])
api_router.include_router(owner_staff.router, prefix="/owner", tags=["owner-staff"])
api_router.include_router(owner_analytics.router, prefix="/owner", tags=["owner-analytics"])
api_router.include_router(roadside.owner_router)

# Catalogs
api_router.include_router(services_router, prefix="/services", tags=["services"])
api_router.include_router(vehicle_types_router, prefix="/vehicle-types", tags=["vehicle-types"])

# Discovery (Public Garages)
api_router.include_router(garages_discovery.router, prefix="/garages", tags=["discovery"])
api_router.include_router(garages_public.router, tags=["public-garages"])

# Customer Reviews & Reports
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(roadside.customer_router)

# Administrator APIs
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Public Garage Associations
api_router.include_router(public_garage_services_router, tags=["garages"])
api_router.include_router(public_garage_vehicle_types_router, tags=["garages"])

# Owner Garage Associations
api_router.include_router(owner_services_router, prefix="/owner", tags=["owner-garage"])
api_router.include_router(owner_vehicle_types_router, prefix="/owner", tags=["owner-garage"])

# Notifications
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
