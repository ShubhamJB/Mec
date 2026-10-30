"""Unit tests for core auth utilities."""
import pytest
from app.core.security import hash_password, verify_password
from app.core.jwt import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    generate_email_verification_token,
)
from app.schemas.auth import RegisterRequest
from pydantic import ValidationError

def test_password_hashing():
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_roundtrip():
    subject = "11111111-1111-1111-1111-111111111111"
    role = "CUSTOMER"
    token = create_access_token(subject=subject, role=role)
    payload = decode_access_token(token)
    assert payload["sub"] == subject
    assert payload["role"] == role
    assert payload["type"] == "access"

def test_refresh_token_generation():
    raw, hashed = generate_refresh_token()
    assert len(raw) > 30
    assert hash_refresh_token(raw) == hashed

def test_register_request_validation():
    # Valid
    req = RegisterRequest(
        full_name="  John   Doe  ",
        email="User@Example.COM",
        password="ValidPassword123"
    )
    assert req.full_name == "John Doe"
    assert req.email == "user@example.com"

    # Too short password
    with pytest.raises(ValidationError):
        RegisterRequest(
            full_name="Jane Doe",
            email="jane@example.com",
            password="short"
        )

