from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from apps.api.core.settings import settings

F = TypeVar("F", bound=Callable[..., Any])


class NoOpLimiter:
    def limit(self, _limit: str) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            return func

        return decorator


limiter = Limiter(key_func=get_remote_address) if settings.RATE_LIMIT_ENABLED else NoOpLimiter()


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    payload = {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Rate limit exceeded",
            "details": None,
        }
    }
    return JSONResponse(status_code=429, content=jsonable_encoder(payload))
