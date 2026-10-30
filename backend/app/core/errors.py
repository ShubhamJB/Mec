"""
Centralised error envelope for all API responses.

Shape: {"error": {"code": "...", "message": "...", "details": {}, "request_id": "..."}}
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id or str(uuid.uuid4()),
        }
    }


def make_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_envelope(code, message, details, request_id),
    )


# ── Exception handlers to register on the FastAPI app ─────────────────────────
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(code, str(exc.detail), request_id=rid),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    details = {"errors": exc.errors()}
    return JSONResponse(
        status_code=422,
        content=_envelope("VALIDATION_ERROR", "Request validation failed.", details, rid),
    )

