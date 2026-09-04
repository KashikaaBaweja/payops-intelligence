from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from logging import getLogger

from fastapi import Request, Response
from payops_core.logging import bind_request_id, reset_request_id
from starlette.middleware.base import BaseHTTPMiddleware

logger = getLogger(__name__)

_MAX_REQUEST_ID = 128


def resolve_request_id(header_value: str | None) -> str:
    value = (header_value or "").strip()
    if value and len(value) <= _MAX_REQUEST_ID and value.isprintable() and " " not in value:
        return value
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, echo it, and emit a structured access log."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = resolve_request_id(request.headers.get("X-Request-ID"))
        token = bind_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "http_unhandled",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        finally:
            reset_request_id(token)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        # Re-bind so the access log line includes the same request_id.
        token = bind_request_id(request_id)
        try:
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        finally:
            reset_request_id(token)
        return response
