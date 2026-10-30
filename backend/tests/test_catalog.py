"""Unit tests for catalog schemas and normalization."""
import uuid
import pytest
from pydantic import ValidationError
from app.schemas.catalog import (
    CreateCustomServiceRequest,
    CreateCustomVehicleTypeRequest,
    GarageServiceUpdate,
    GarageVehicleTypeUpdate,
)

def test_custom_service_request_normalization():
    req = CreateCustomServiceRequest(name="   Oil   Change   ")
    assert req.name == "Oil Change"

    with pytest.raises(ValidationError):
        CreateCustomServiceRequest(name=" ")

    with pytest.raises(ValidationError):
        CreateCustomServiceRequest(name=" a ")

def test_custom_vehicle_type_request_normalization():
    req = CreateCustomVehicleTypeRequest(name="   Electric   Scooter   ")
    assert req.name == "Electric Scooter"

    with pytest.raises(ValidationError):
        CreateCustomVehicleTypeRequest(name=" ")

def test_garage_service_update_deduplication():
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    req = GarageServiceUpdate(service_ids=[id1, id2, id1, id2])
    assert len(req.service_ids) == 2
    assert req.service_ids == [id1, id2]

def test_garage_vehicle_type_update_deduplication():
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    req = GarageVehicleTypeUpdate(vehicle_type_ids=[id1, id2, id1])
    assert len(req.vehicle_type_ids) == 2
    assert req.vehicle_type_ids == [id1, id2]

