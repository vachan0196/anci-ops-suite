import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ShiftRequestType = Literal["pickup", "drop", "swap"]
ShiftRequestStatus = Literal[
    "pending",
    "pending_target",
    "target_accepted",
    "target_declined",
    "approved",
    "rejected",
    "cancelled",
]


class ShiftRequestCreate(BaseModel):
    shift_id: uuid.UUID
    type: ShiftRequestType
    target_user_id: uuid.UUID | None = None
    notes: str | None = None


class ShiftRequestRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    shift_id: uuid.UUID
    requester_user_id: uuid.UUID
    target_user_id: uuid.UUID | None
    type: ShiftRequestType
    status: ShiftRequestStatus
    notes: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
