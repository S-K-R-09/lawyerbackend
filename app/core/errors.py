"""Consistent error shape: {"error": {"code", "message", "fields"}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class ErrorBody(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["Please correct the highlighted fields."])
    fields: dict[str, str] | None = Field(default=None, examples=[{"amount": "Must be positive."}])


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields
        self.headers = headers


def not_found(message: str = "Not found.") -> AppError:
    return AppError(404, "not_found", message)


def conflict(message: str, fields: dict[str, str] | None = None) -> AppError:
    return AppError(409, "conflict", message, fields)


def validation_error(
    message: str, fields: dict[str, str] | None = None, status: int = 422
) -> AppError:
    return AppError(status, "validation_error", message, fields)


def unauthorized(message: str = "Not authenticated.") -> AppError:
    return AppError(401, "unauthorized", message, headers={"WWW-Authenticate": "Bearer"})


def _payload(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "fields": fields}}


_STATUS_CODES = {
    401: "unauthorized",
    403: "unauthorized",
    404: "not_found",
    405: "not_found",
    409: "conflict",
    429: "rate_limited",
}


def _clean_msg(msg: str) -> str:
    return msg.removeprefix("Value error, ").strip()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.fields),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path", "form")]
            key = ".".join(loc) or "body"
            fields.setdefault(key, _clean_msg(str(err.get("msg", "Invalid value."))))
        return JSONResponse(
            status_code=422,
            content=_payload("validation_error", "Please correct the highlighted fields.", fields),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "validation_error")
        message = str(exc.detail) if exc.detail else "Request failed."
        if exc.status_code == 404 and message == "Not Found":
            message = "Not found."
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=_payload("rate_limited", "Too many requests. Please slow down and retry."),
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the exception type only; messages may carry personal data.
        logger.error("unhandled_exception", extra={"error_type": type(exc).__name__})
        return JSONResponse(
            status_code=500,
            content=_payload("internal_error", "Something went wrong. Please try again."),
        )


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing or invalid access token"},
    404: {"model": ErrorResponse, "description": "Not found (or owned by someone else)"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
