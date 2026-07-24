import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ShiftStatus = Literal["scheduled", "cancelled", "completed"]


class ShiftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    assigned_user_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime
    required_role: str | None = None


class ShiftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_user_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: ShiftStatus | None = None
    required_role: str | None = None


class ShiftRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    start_at: datetime
    end_at: datetime
    required_role: str | None
    source: Literal["manual", "demand_generation", "legacy_untracked"]
    generation_run_id: uuid.UUID | None
    source_coverage_template_id: uuid.UUID | None
    work_area_id: uuid.UUID | None
    status: ShiftStatus
    published_at: datetime | None
    role_override: bool
    availability_override: bool
    overridden_by_user_id: uuid.UUID | None
    overridden_at: datetime | None
    override_reason: str | None
    superseded_at: datetime | None
    superseded_by_generation_run_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShiftAssignRequest(BaseModel):
    assigned_user_id: uuid.UUID
    override_reason: str | None = None
    mode: Literal["single", "recalibrate"] = "single"


class ShiftAssignResponse(BaseModel):
    shift: ShiftRead
    recommendations: dict | None = None


class ShiftPublishRangeRequest(BaseModel):
    store_id: uuid.UUID
    from_at: datetime = Field(alias="from")
    to_at: datetime = Field(alias="to")


class ShiftPublishRangeResponse(BaseModel):
    updated_count: int
