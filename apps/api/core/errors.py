import logging

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


async def api_error_exception_handler(request: Request, exc: ApiError) -> JSONResponse:
    payload = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(payload),
    )


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    sanitized_errors: list[dict] = []
    for error in errors:
        sanitized_error = {
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "type": error.get("type"),
        }
        if "input" in error:
            sanitized_error["input"] = error["input"]
        sanitized_errors.append(sanitized_error)
    return sanitized_errors


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = _sanitize_validation_errors(exc.errors())
    payload = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": str(exc),
            "details": details,
        }
    }
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(payload),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception for path=%s", request.url.path, exc_info=exc)
    payload = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Unexpected error",
        }
    }
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(payload),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
