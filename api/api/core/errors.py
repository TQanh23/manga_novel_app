from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.core.request_id import get_request_id

_HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    429: "rate_limited",
}


class ErrorDetail(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """The one error shape every route returns."""

    error: ErrorBody


# Merged into every /v1 route so the generated client knows the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "default": {"model": ErrorResponse, "description": "Error"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


class AppError(Exception):
    """An error the client is meant to see. Raise this instead of HTTPException.

    The message is shown to users and written to logs, so it must never carry
    manuscript text or other content.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Sequence[ErrorDetail] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = list(details) if details is not None else None
        self.headers = dict(headers) if headers is not None else None


def error_response(
    code: str,
    message: str,
    status_code: int,
    *,
    details: Sequence[ErrorDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=get_request_id(),
            details=list(details) if details is not None else None,
        )
    )
    return JSONResponse(
        body.model_dump(mode="json"),
        status_code=status_code,
        headers=dict(headers) if headers is not None else None,
    )


def internal_error_response() -> JSONResponse:
    """What an unexpected exception turns into. Nothing about the cause leaves the server."""
    return error_response("internal_error", "Internal server error", 500)


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(
        exc.code, exc.message, exc.status_code, details=exc.details, headers=exc.headers
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's `input` and `ctx` echo what the client sent (passwords,
    # manuscript text), so only the location, message and type are returned.
    details = [
        ErrorDetail(loc=list(error["loc"]), msg=error["msg"], type=error["type"])
        for error in exc.errors()
    ]
    return error_response("validation_error", "Request validation failed", 422, details=details)


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else code
    return error_response(code, message, exc.status_code, headers=exc.headers)


def install_error_handlers(app: FastAPI) -> None:
    # Starlette types handlers as taking a bare Exception; each one is only ever
    # called with the class it is registered for.
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
