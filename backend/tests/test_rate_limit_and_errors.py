from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import http_exception_handler
from app.core.rate_limit import rate_limit_exceeded_handler


def build_app() -> FastAPI:
    app = FastAPI()
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/limited")
    @limiter.limit("2/minute")
    async def limited(request: Request) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/unverified")
    async def unverified() -> None:
        raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")

    @app.get("/suspended")
    async def suspended() -> None:
        raise HTTPException(status_code=403, detail="ACCOUNT_SUSPENDED")

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise HTTPException(status_code=403, detail="Admin access required.")

    return app


def test_rate_limit_returns_429_envelope():
    client = TestClient(build_app())
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    response = client.get("/limited")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_specific_error_codes():
    client = TestClient(build_app())
    unverified = client.get("/unverified")
    assert unverified.status_code == 403
    assert unverified.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    suspended = client.get("/suspended")
    assert suspended.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


def test_generic_forbidden_code_unchanged():
    response = TestClient(build_app()).get("/forbidden")
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.json()["error"]["message"] == "Admin access required."
