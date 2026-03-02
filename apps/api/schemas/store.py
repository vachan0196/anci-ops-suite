import uuid
from datetime import datetime

from pydantic import BaseModel


class StoreCreate(BaseModel):
    code: str | None = None
    name: str
    timezone: str | None = None
    address_line1: str | None = None
    city: str | None = None
    postcode: str | None = None
    phone: str | None = None
    manager_user_id: uuid.UUID | None = None


class StoreUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
    address_line1: str | None = None
    city: str | None = None
    postcode: str | None = None
    phone: str | None = None
    manager_user_id: uuid.UUID | None = None


class StoreOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str | None
    name: str
    timezone: str | None
    is_active: bool
    address_line1: str | None
    city: str | None
    postcode: str | None
    phone: str | None
    manager_user_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
