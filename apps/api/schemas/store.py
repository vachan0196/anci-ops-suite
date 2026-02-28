import uuid
from datetime import datetime

from pydantic import BaseModel


class StoreCreate(BaseModel):
    code: str | None = None
    name: str
    timezone: str | None = None


class StoreUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class StoreOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str | None
    name: str
    timezone: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
