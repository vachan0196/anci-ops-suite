import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class CoverageTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    required_headcount: int = Field(ge=1)
    required_role: str | None = None
    is_active: bool = True


class CoverageTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    required_headcount: int | None = Field(default=None, ge=1)
    required_role: str | None = None
    is_active: bool | None = None


class CoverageTemplateRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
    required_headcount: int
    required_role: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
