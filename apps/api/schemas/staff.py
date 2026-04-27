import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class StaffProfileCreate(BaseModel):
    user_id: uuid.UUID
    store_id: uuid.UUID | None = None
    display_name: str
    job_title: str | None = None
    hourly_rate: Decimal | None = None
    pay_type: str | None = None
    phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    contract_type: str | None = None
    rtw_status: str | None = None
    notes: str | None = None
    is_active: bool = True


class StaffProfileUpdate(BaseModel):
    store_id: uuid.UUID | None = None
    display_name: str | None = None
    job_title: str | None = None
    hourly_rate: Decimal | None = None
    pay_type: str | None = None
    phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    contract_type: str | None = None
    rtw_status: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class StaffSelfUpdate(BaseModel):
    phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class StaffProfileOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    store_id: uuid.UUID | None
    display_name: str
    job_title: str | None
    hourly_rate: Decimal | None
    pay_type: str | None
    phone: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    contract_type: str | None
    rtw_status: str | None
    rtw_checked_at: datetime | None
    rtw_checked_by_user_id: uuid.UUID | None
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StaffDirectoryItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    email: str | None
    job_title: str | None
    phone: str | None
    store_id: uuid.UUID | None
    store_name: str | None
    roles: list[str]
    is_active: bool
    created_at: datetime


class StaffRoleCreate(BaseModel):
    role: str


class StaffRoleOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    staff_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
