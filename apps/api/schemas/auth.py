import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

BCRYPT_MAX_PASSWORD_BYTES = 72
BCRYPT_PASSWORD_TOO_LONG_MESSAGE = (
    "Password must be at most 72 bytes (bcrypt limit)."
)


class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(BCRYPT_PASSWORD_TOO_LONG_MESSAGE)
        return value


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    active_tenant_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
