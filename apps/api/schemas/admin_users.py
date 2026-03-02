import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from apps.api.schemas.auth import BCRYPT_MAX_PASSWORD_BYTES, BCRYPT_PASSWORD_TOO_LONG_MESSAGE


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    full_name: str | None = None
    role: str = "member"

    @field_validator("password")
    @classmethod
    def validate_password_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(BCRYPT_PASSWORD_TOO_LONG_MESSAGE)
        return value


class AdminUserCreateResponse(BaseModel):
    id: uuid.UUID
    email: str
    active_tenant_id: uuid.UUID
    role: str
