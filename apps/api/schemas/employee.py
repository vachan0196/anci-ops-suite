import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.availability import AvailabilityType
from apps.api.schemas.shift_request import ShiftRequestRead, ShiftRequestStatus


class EmployeeStoreOption(BaseModel):
    id: uuid.UUID
    code: str | None
    name: str
    timezone: str | None

    model_config = {"from_attributes": True}


class EmployeeShiftRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    start_at: datetime
    end_at: datetime
    required_role: str | None
    status: str
    published_at: datetime

    model_config = {"from_attributes": True}


class EmployeeWeeklyShiftRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    assigned_staff_display_name: str | None
    start_at: datetime
    end_at: datetime
    required_role: str | None
    status: str
    published_at: datetime


class EmployeeTodayOperatorRead(BaseModel):
    user_id: uuid.UUID
    display_name: str | None


class EmployeeLabourIntelligenceRead(BaseModel):
    scheduled_hours_this_week: float
    scheduled_hours_this_month: float
    estimated_pay_this_week: float | None
    estimated_pay_this_month: float | None
    monthly_progress_percent: float | None


class EmployeeProfileRead(BaseModel):
    staff_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    job_title: str | None
    store_id: uuid.UUID | None
    pay_type: str | None
    hourly_rate: float | None
    phone: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    contract_type: str | None
    is_active: bool
    roles: list[str] = Field(default_factory=list)


class EmployeeHomeRead(BaseModel):
    week_start: date
    available_stores: list[EmployeeStoreOption] = Field(default_factory=list)
    selected_store: EmployeeStoreOption
    my_rota: list[EmployeeShiftRead] = Field(default_factory=list)
    weekly_rota: list[EmployeeWeeklyShiftRead] = Field(default_factory=list)
    today_operators: list[EmployeeTodayOperatorRead] = Field(default_factory=list)
    today_tasks: None = None
    labour_intelligence: EmployeeLabourIntelligenceRead


class EmployeeRotaRead(BaseModel):
    week_start: date
    available_stores: list[EmployeeStoreOption] = Field(default_factory=list)
    selected_store: EmployeeStoreOption
    shifts: list[EmployeeShiftRead] = Field(default_factory=list)


class EmployeeMyRotaShiftRead(BaseModel):
    id: uuid.UUID
    start_time: datetime
    end_time: datetime
    role_required: str | None
    status: str


class EmployeeMyRotaRead(BaseModel):
    week_start: date
    site_id: uuid.UUID
    employee_account_id: uuid.UUID
    shifts: list[EmployeeMyRotaShiftRead] = Field(default_factory=list)


class EmployeeAvailabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date
    date: date
    start_time: time | None = None
    end_time: time | None = None
    type: AvailabilityType
    notes: str | None = None


class EmployeeAvailabilityRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID | None
    week_start: date
    date: date
    start_time: time | None
    end_time: time | None
    type: AvailabilityType
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeAvailabilityListRead(BaseModel):
    week_start: date
    available_stores: list[EmployeeStoreOption] = Field(default_factory=list)
    selected_store: EmployeeStoreOption
    items: list[EmployeeAvailabilityRead] = Field(default_factory=list)


class EmployeeSwapCreate(BaseModel):
    shift_id: uuid.UUID
    target_user_id: uuid.UUID
    notes: str | None = None


class EmployeeSwapRead(ShiftRequestRead):
    pass


class EmployeeSwapListRead(BaseModel):
    status: ShiftRequestStatus | None
    available_stores: list[EmployeeStoreOption] = Field(default_factory=list)
    selected_store: EmployeeStoreOption
    items: list[EmployeeSwapRead] = Field(default_factory=list)
