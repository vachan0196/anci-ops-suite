import uuid
from datetime import datetime

from pydantic import BaseModel


class StaffProfileCreate(BaseModel):
    user_id: uuid.UUID
    store_id: uuid.UUID | None = None
    display_name: str
    job_title: str | None = None
    is_active: bool = True


class StaffProfileUpdate(BaseModel):
    store_id: uuid.UUID | None = None
    display_name: str | None = None
    job_title: str | None = None
    is_active: bool | None = None


class StaffProfileOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    store_id: uuid.UUID | None
    display_name: str
    job_title: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
