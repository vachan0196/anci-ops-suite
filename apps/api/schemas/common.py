from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class SuccessResponse(BaseModel, Generic[T]):
    data: T


class ErrorResponse(BaseModel):
    error: ErrorPayload
