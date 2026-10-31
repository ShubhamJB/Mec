import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.deps import get_current_user
from app.main import app
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.staff import StaffCreate, StaffPatch


def test_staff_create_normalizes_and_validates_fields():
    dto = StaffCreate(
        full_name="  Ramesh   Karki  ",
        phone=" +9779812345678 ",
        role_title="  Senior   Mechanic ",
    )
    assert dto.full_name == "Ramesh Karki"
    assert dto.phone == "+9779812345678"
    assert dto.role_title == "Senior Mechanic"


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": "A", "phone": "+9779812345678"},
        {"full_name": "Ramesh", "phone": "9812345678"},
        {"full_name": "Ramesh", "phone": "+9779812345678", "role_title": "x" * 51},
    ],
)
def test_staff_create_rejects_invalid_fields(payload):
    with pytest.raises(ValidationError):
        StaffCreate(**payload)


def test_staff_patch_requires_change_and_can_clear_role_title():
    with pytest.raises(ValidationError):
        StaffPatch()
    with pytest.raises(ValidationError):
        StaffPatch(is_active=None)
    dto = StaffPatch(role_title=None)
    assert dto.model_dump(exclude_unset=True) == {"role_title": None}


def test_staff_routes_are_registered_only_under_owner_prefix():
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/owner/staff": {"get", "post"},
        "/api/v1/owner/staff/{staff_id}": {"get", "patch", "delete"},
    }
    for path, methods in expected.items():
        assert methods <= paths[path].keys()
    assert not any("staff" in path for path in paths if not path.startswith("/api/v1/owner/"))


def test_customer_cannot_access_private_staff_roster():
    customer = User(
        full_name="Test Customer",
        email="customer@example.com",
        password_hash="unused",
        role=UserRole.CUSTOMER,
        email_verified=True,
    )
    app.dependency_overrides[get_current_user] = lambda: customer
    try:
        response = TestClient(app).get("/api/v1/owner/staff")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
