from logging import getLogger
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from payops_core.logging import get_request_id
from payops_core.models.api import ErrorResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = getLogger(__name__)


def _payload(status_code: int, error: str, detail: Any) -> dict:
    body = ErrorResponse(
        error=error,
        detail=detail,
        status_code=status_code,
        request_id=get_request_id() or "-",
    )
    return body.model_dump(mode="json")


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    error = "not_found" if exc.status_code == 404 else "http_error"
    if exc.status_code == 400:
        error = "bad_request"
    if exc.status_code >= 500:
        error = "internal_error"
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(exc.status_code, error, detail),
        headers={"X-Request-ID": get_request_id() or "-"},
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_payload(422, "validation_error", exc.errors()),
        headers={"X-Request-ID": get_request_id() or "-"},
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error")
    return JSONResponse(
        status_code=500,
        content=_payload(500, "internal_error", "Internal server error"),
        headers={"X-Request-ID": get_request_id() or "-"},
    )
