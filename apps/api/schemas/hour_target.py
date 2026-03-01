import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class HourTargetUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    store_id: uuid.UUID | None = None
    week_start: date
    min_hours: int | None = None
    max_hours: int | None = None
    target_hours: int | None = None
    notes: str | None = None


class HourTargetRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    store_id: uuid.UUID | None
    week_start: date
    min_hours: int | None
    max_hours: int | None
    target_hours: int | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
