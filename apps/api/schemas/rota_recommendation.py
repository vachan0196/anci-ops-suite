import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DraftStatus = Literal["draft", "applied", "discarded"]


class DraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    week_start: date


class DraftRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    week_start: date
    status: DraftStatus
    created_by_user_id: uuid.UUID
    created_at: datetime
    applied_at: datetime | None

    model_config = {"from_attributes": True}


class ItemRead(BaseModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    proposed_user_id: uuid.UUID | None
    score: int
    reason: str | None

    model_config = {"from_attributes": True}


class DraftCreateResponse(BaseModel):
    draft_id: uuid.UUID
    shifts_considered: int
    items_created: int
    unfilled: int


class DraftDetailRead(BaseModel):
    draft: DraftRead
    items: list[ItemRead]
    shifts_considered: int
    items_created: int
    unfilled: int


class ApplyResponse(BaseModel):
    count_applied: int
