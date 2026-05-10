from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

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
    active_tenant_role: Literal["admin", "member"] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class EmployeeLoginRequest(BaseModel):
    site_id: uuid.UUID
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_employee_password_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(BCRYPT_PASSWORD_TOO_LONG_MESSAGE)
        return value


class EmployeeAccountSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    tenant_id: uuid.UUID
    site_id: uuid.UUID


class EmployeeLoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    employee_account: EmployeeAccountSummary


class EmployeeMeResponse(BaseModel):
    portal: Literal["employee"] = "employee"
    employee_account_id: uuid.UUID
    tenant_id: uuid.UUID
    site_id: uuid.UUID
    display_name: str


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = None
    portal: Literal["admin", "employee"] | None = None


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    portal: Literal["admin", "employee"]


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = None


class LogoutResponse(BaseModel):
    revoked: bool
