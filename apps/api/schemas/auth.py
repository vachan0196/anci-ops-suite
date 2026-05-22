from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

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
    active_tenant_role: Literal["owner", "admin", "member"] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    requires_2fa: bool | None = None
    two_factor_challenge_token: str | None = None


class TwoFactorStatusResponse(BaseModel):
    totp_enrolled: bool
    totp_enrolled_at: datetime | None = None
    pending_enrolment: bool
    pending_expires_at: datetime | None = None
    recovery_codes_remaining: int


class TwoFactorEnrolBeginResponse(BaseModel):
    status: Literal["pending"]
    otpauth_url: str
    manual_secret: str
    expires_at: datetime


class TwoFactorEnrolConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class TwoFactorEnrolConfirmResponse(BaseModel):
    status: Literal["enabled"]
    recovery_codes: list[str]


class TwoFactorVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    two_factor_challenge_token: str
    code: str | None = None
    recovery_code: str | None = None

    @field_validator("code", "recovery_code")
    @classmethod
    def validate_secret_field_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value must not be blank")
        return value


class TwoFactorDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    code: str | None = None
    recovery_code: str | None = None

    @field_validator("current_password", "code", "recovery_code")
    @classmethod
    def validate_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_single_factor(self) -> "TwoFactorDisableRequest":
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError("Provide exactly one 2FA code or recovery code")
        return self


class TwoFactorDisableResponse(BaseModel):
    status: Literal["disabled"]


class TwoFactorRecoveryCodesRegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = None
    recovery_code: str | None = None

    @field_validator("code", "recovery_code")
    @classmethod
    def validate_secret_field_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_single_factor(self) -> "TwoFactorRecoveryCodesRegenerateRequest":
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError("Provide exactly one 2FA code or recovery code")
        return self


class TwoFactorRecoveryCodesRegenerateResponse(BaseModel):
    status: Literal["regenerated"]
    recovery_codes: list[str]


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


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class PasswordResetRequestResponse(BaseModel):
    message: str


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str
    confirm_password: str

    @field_validator("new_password", "confirm_password")
    @classmethod
    def validate_password_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(BCRYPT_PASSWORD_TOO_LONG_MESSAGE)
        return value


class PasswordResetConfirmResponse(BaseModel):
    success: bool


class EmailVerificationRequestResponse(BaseModel):
    message: str


class EmailVerificationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class EmailVerificationConfirmResponse(BaseModel):
    success: bool
