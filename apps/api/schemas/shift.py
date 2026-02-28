import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ShiftStatus = Literal["scheduled", "cancelled", "completed"]


class ShiftCreate(BaseModel):
    store_id: uuid.UUID
    assigned_user_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime


class ShiftUpdate(BaseModel):
    assigned_user_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: ShiftStatus | None = None


class ShiftRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    start_at: datetime
    end_at: datetime
    status: ShiftStatus
    created_at: datetime

    model_config = {"from_attributes": True}
