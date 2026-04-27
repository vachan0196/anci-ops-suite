import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StoreCreate(BaseModel):
    code: str | None = None
    name: str
    timezone: str | None = None
    address_line1: str | None = None
    city: str | None = None
    postcode: str | None = None
    phone: str | None = None
    manager_user_id: uuid.UUID | None = None


class StoreUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
    address_line1: str | None = None
    city: str | None = None
    postcode: str | None = None
    phone: str | None = None
    manager_user_id: uuid.UUID | None = None


class StoreOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str | None
    name: str
    timezone: str | None
    is_active: bool
    address_line1: str | None
    city: str | None
    postcode: str | None
    phone: str | None
    manager_user_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OpeningHoursDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(ge=0, le=6)
    open_time: time | None = None
    close_time: time | None = None
    is_closed: bool = False

    @model_validator(mode="after")
    def validate_open_times(self) -> "OpeningHoursDay":
        if self.is_closed:
            return self

        if self.open_time is None or self.close_time is None:
            raise ValueError("open_time and close_time are required when store is open")

        if self.close_time <= self.open_time:
            raise ValueError("close_time must be later than open_time")

        return self


class OpeningHoursBulkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_hours: list[OpeningHoursDay]

    @model_validator(mode="after")
    def validate_unique_days(self) -> "OpeningHoursBulkUpdate":
        days = [item.day_of_week for item in self.opening_hours]
        if len(days) != len(set(days)):
            raise ValueError("Each day_of_week can only appear once")
        return self


class OpeningHoursResponse(BaseModel):
    store_id: uuid.UUID
    opening_hours: list[OpeningHoursDay]


class StoreSettingsResponse(BaseModel):
    store_id: uuid.UUID
    business_week_start_day: int


class StoreSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_week_start_day: int | None = Field(default=None, ge=0, le=6)


class StoreReadinessResponse(BaseModel):
    store_id: uuid.UUID
    opening_hours_configured: bool
    staff_configured: bool
    operational_ready: bool
