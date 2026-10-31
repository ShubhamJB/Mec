from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.core.roadside_crypto import decrypt_private_payload, encrypt_private_payload
from app.main import create_app
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.roadside import (
    RoadsideCapabilityUpdate,
    RoadsideRequestCreate,
    RoadsideRequestProgress,
)
from app.services.roadside_service import _coarse_coordinate


def test_roadside_private_payload_is_encrypted_and_round_trips(monkeypatch):
    from app.core import roadside_crypto

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(roadside_crypto.settings, "ROADSIDE_DATA_KEY", key)
    payload = {
        "latitude": 27.7,
        "longitude": 85.3,
        "address": "Private location",
        "contact_phone": "+9779812345678",
    }
    ciphertext = encrypt_private_payload(payload)
    assert "Private location" not in ciphertext
    assert "+9779812345678" not in ciphertext
    assert decrypt_private_payload(ciphertext) == payload


def test_roadside_schemas_require_explicit_consent_and_valid_availability():
    with pytest.raises(ValueError):
        RoadsideRequestCreate(
            garage_id=uuid.uuid4(),
            vehicle_type_id=uuid.uuid4(),
            service_id=uuid.uuid4(),
            problem_description="Engine stopped suddenly",
            latitude=27.7,
            longitude=85.3,
            contact_phone="+9779812345678",
            consent_to_share_after_acceptance=False,
        )

    with pytest.raises(ValueError):
        RoadsideCapabilityUpdate(
            enabled=False,
            is_available=True,
            service_radius_km=10,
            callback_phone="+9779812345678",
        )


def test_roadside_progress_rejects_non_owner_assignable_states():
    with pytest.raises(ValueError):
        RoadsideRequestProgress(status="PENDING")


def test_roadside_preview_location_is_quantized_to_cell_center():
    assert _coarse_coordinate(27.7123) == 27.725
    assert _coarse_coordinate(85.3123) == 85.325


def test_roadside_routes_are_registered_and_require_authentication():
    app = create_app()
    customer = User(
        id=uuid.uuid4(),
        full_name="Customer",
        email="customer@example.com",
        password_hash="unused",
        role=UserRole.CUSTOMER,
        email_verified=True,
    )
    app.dependency_overrides[get_current_user] = lambda: customer
    try:
        paths = app.openapi()["paths"]
        assert "/api/v1/roadside/eligible-garages" in paths
        assert "/api/v1/owner/roadside/capability" in paths
        response = TestClient(app).get("/api/v1/owner/roadside/capability")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_roadside_private_data_key_required(monkeypatch):
    from app.core import roadside_crypto

    monkeypatch.setattr(roadside_crypto.settings, "ROADSIDE_DATA_KEY", "")
    with pytest.raises(HTTPException) as exc:
        encrypt_private_payload({"contact_phone": "+9779812345678"})
    assert exc.value.status_code == 503
