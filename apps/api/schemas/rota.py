import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class GenerateWeekRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    week_start: date


class GenerateWeekResponse(BaseModel):
    created_count: int


class WeeklyRotaShiftRead(BaseModel):
    id: uuid.UUID
    assigned_employee_account_id: uuid.UUID | None
    role_required: str | None
    start_time: datetime
    end_time: datetime


class WeeklyRotaRead(BaseModel):
    site_id: uuid.UUID
    week_start: date
    shifts: list[WeeklyRotaShiftRead]


class SiteShiftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_employee_account_id: uuid.UUID | None = None
    role_required: str | None = None
    start_time: datetime
    end_time: datetime
