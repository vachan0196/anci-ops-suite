import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class CompanyProfileUpdate(BaseModel):
    company_name: str | None = None
    owner_name: str | None = None
    business_email: str | None = None
    phone_number: str | None = None
    registered_address: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "company_name",
        "owner_name",
        "business_email",
        "phone_number",
        "registered_address",
        mode="before",
    )
    @classmethod
    def trim_strings(cls, value: str | None) -> str | None:
        return _trim_optional(value)


class CompanyProfileRead(BaseModel):
    tenant_id: uuid.UUID
    company_name: str | None
    owner_name: str | None
    business_email: str | None
    phone_number: str | None
    registered_address: str | None
    company_setup_completed: bool
    company_setup_completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
