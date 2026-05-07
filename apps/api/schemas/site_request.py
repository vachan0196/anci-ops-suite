import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SiteRequestType = Literal["leave", "swap", "cover"]
SiteRequestStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "target_accepted",
    "target_declined",
]


class SiteRequestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_reason: str | None = Field(default=None, max_length=500)
    rejection_reason: str | None = Field(default=None, max_length=500)


class SiteRequestShiftSummary(BaseModel):
    id: uuid.UUID
    start_at: datetime
    end_at: datetime
    role_required: str | None
    assigned_employee_display_name: str | None


class SiteRequestRead(BaseModel):
    id: uuid.UUID
    request_type: SiteRequestType
    status: SiteRequestStatus
    requester_employee_account_id: uuid.UUID | None
    requester_display_name: str | None
    target_employee_account_id: uuid.UUID | None
    target_display_name: str | None
    shift_id: uuid.UUID | None
    target_shift_id: uuid.UUID | None
    start_date: date | None
    end_date: date | None
    reason: str | None
    created_at: datetime
    decided_at: datetime | None
    approver_user_id: uuid.UUID | None
    approval_reason: str | None
    rejection_reason: str | None


class SiteRequestDetailRead(SiteRequestRead):
    shift: SiteRequestShiftSummary | None = None
    target_shift: SiteRequestShiftSummary | None = None


class SiteRequestListRead(BaseModel):
    site_id: uuid.UUID
    items: list[SiteRequestRead] = Field(default_factory=list)


class SiteRequestDecisionRead(BaseModel):
    id: uuid.UUID
    status: Literal["approved", "rejected"]
    rota_updated: bool = False
    affected_shift_count: int = 0
    message: str | None = None
