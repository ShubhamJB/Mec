from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.errors import make_error_response

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return make_error_response(
        status_code=429,
        code="RATE_LIMIT_EXCEEDED",
        message="Too many requests. Please try again later.",
        request_id=request_id,
    )
