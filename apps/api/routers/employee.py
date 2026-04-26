from dataclasses import dataclass
from datetime import date as date_type, datetime, time, timedelta, timezone
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from apps.api.core.deps import get_current_user, require_tenant_member
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.hour_target import HourTarget
from apps.api.models.shift import Shift
from apps.api.models.shift_request import ShiftRequest
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.staff_role import StaffRole
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers.availability import _validate_availability_payload
from apps.api.routers.shift_requests import create_shift_request
from apps.api.schemas.employee import (
    EmployeeAvailabilityCreate,
    EmployeeAvailabilityListRead,
    EmployeeAvailabilityRead,
    EmployeeHomeRead,
    EmployeeLabourIntelligenceRead,
    EmployeeProfileRead,
    EmployeeRotaRead,
    EmployeeShiftRead,
    EmployeeStoreOption,
    EmployeeSwapCreate,
    EmployeeSwapListRead,
    EmployeeSwapRead,
    EmployeeTodayOperatorRead,
    EmployeeWeeklyShiftRead,
)
from apps.api.schemas.shift_request import ShiftRequestCreate, ShiftRequestStatus

router = APIRouter()


@dataclass
class _EmployeeContext:
    user: User
    membership: TenantUser
    staff_profile: StaffProfile
    available_stores: list[Store]
    selected_store: Store


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _week_bounds(week_start: date_type) -> tuple[datetime, datetime]:
    week_start_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    return week_start_at, week_start_at + timedelta(days=7)


def _month_bounds(current_date: date_type) -> tuple[datetime, datetime]:
    month_start = current_date.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1)
    return (
        datetime.combine(month_start, time.min, tzinfo=timezone.utc),
        datetime.combine(month_end, time.min, tzinfo=timezone.utc),
    )


def _default_week_start() -> date_type:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


def _resolve_staff_profile_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> StaffProfile:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == tenant_id,
            StaffProfile.user_id == user_id,
        )
    )
    if profile is None:
        raise ApiError(
            status_code=404,
            code="STAFF_PROFILE_NOT_FOUND",
            message="Staff profile not found in active tenant",
        )
    if not profile.is_active:
        raise ApiError(
            status_code=404,
            code="STAFF_PROFILE_NOT_FOUND",
            message="Staff profile not found in active tenant",
        )
    return profile


def _resolve_available_stores(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    staff_profile: StaffProfile,
) -> list[Store]:
    if staff_profile.store_id is None:
        return []

    store = db.scalar(
        select(Store).where(
            Store.id == staff_profile.store_id,
            Store.tenant_id == tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )
    return [store]


def _resolve_selected_store_or_404(
    available_stores: list[Store],
    *,
    store_id: uuid.UUID | None,
) -> Store:
    if not available_stores:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )

    if store_id is None:
        return available_stores[0]

    for store in available_stores:
        if store.id == store_id:
            return store

    raise ApiError(
        status_code=404,
        code="STORE_NOT_FOUND",
        message="Store not found in active tenant",
    )


def _resolve_employee_context(
    db: Session,
    *,
    user: User,
    membership: TenantUser,
    store_id: uuid.UUID | None,
) -> _EmployeeContext:
    profile = _resolve_staff_profile_or_404(
        db,
        tenant_id=membership.tenant_id,
        user_id=user.id,
    )
    available_stores = _resolve_available_stores(
        db,
        tenant_id=membership.tenant_id,
        staff_profile=profile,
    )
    selected_store = _resolve_selected_store_or_404(
        available_stores,
        store_id=store_id,
    )
    return _EmployeeContext(
        user=user,
        membership=membership,
        staff_profile=profile,
        available_stores=available_stores,
        selected_store=selected_store,
    )


def _shift_duration_hours(shift: Shift) -> float:
    return max((_as_utc(shift.end_at) - _as_utc(shift.start_at)).total_seconds() / 3600, 0.0)


def _sum_shift_hours(shifts: list[Shift]) -> float:
    return round(sum(_shift_duration_hours(shift) for shift in shifts), 2)


def _resolve_monthly_target_hours(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    store_id: uuid.UUID,
    month_start: datetime,
    month_end: datetime,
) -> int | None:
    targets = db.scalars(
        select(HourTarget).where(
            HourTarget.tenant_id == tenant_id,
            HourTarget.user_id == user_id,
            HourTarget.week_start >= month_start.date(),
            HourTarget.week_start < month_end.date(),
            or_(
                HourTarget.store_id == store_id,
                HourTarget.store_id.is_(None),
            ),
        )
    ).all()
    if not targets:
        return None

    by_week: dict[date_type, tuple[int, int | None]] = {}
    for target in targets:
        priority = 2 if target.store_id == store_id else 1
        existing = by_week.get(target.week_start)
        if existing is None or priority >= existing[0]:
            by_week[target.week_start] = (priority, target.target_hours)

    total_target = sum(value or 0 for _, value in by_week.values())
    return total_target if total_target > 0 else None


def _estimate_pay(hours: float, staff_profile: StaffProfile) -> float | None:
    if staff_profile.pay_type != "hourly" or staff_profile.hourly_rate is None:
        return None
    estimate = Decimal(str(hours)) * staff_profile.hourly_rate
    return float(round(estimate, 2))


def _load_my_published_shifts(
    db: Session,
    *,
    context: _EmployeeContext,
    from_at: datetime,
    to_at: datetime,
) -> list[Shift]:
    return db.scalars(
        select(Shift)
        .where(
            Shift.tenant_id == context.membership.tenant_id,
            Shift.store_id == context.selected_store.id,
            Shift.assigned_user_id == context.user.id,
            Shift.published_at.is_not(None),
            Shift.status == "scheduled",
            Shift.start_at >= from_at,
            Shift.start_at < to_at,
        )
        .order_by(Shift.start_at.asc(), Shift.id.asc())
    ).all()


def _build_labour_intelligence(
    db: Session,
    *,
    context: _EmployeeContext,
    week_start: date_type,
) -> EmployeeLabourIntelligenceRead:
    week_start_at, week_end_at = _week_bounds(week_start)
    today = datetime.now(timezone.utc).date()
    month_start_at, month_end_at = _month_bounds(today)

    week_shifts = _load_my_published_shifts(
        db,
        context=context,
        from_at=week_start_at,
        to_at=week_end_at,
    )
    month_shifts = _load_my_published_shifts(
        db,
        context=context,
        from_at=month_start_at,
        to_at=month_end_at,
    )

    scheduled_hours_week = _sum_shift_hours(week_shifts)
    scheduled_hours_month = _sum_shift_hours(month_shifts)
    estimated_pay_week = _estimate_pay(scheduled_hours_week, context.staff_profile)
    estimated_pay_month = _estimate_pay(scheduled_hours_month, context.staff_profile)

    monthly_target_hours = _resolve_monthly_target_hours(
        db,
        tenant_id=context.membership.tenant_id,
        user_id=context.user.id,
        store_id=context.selected_store.id,
        month_start=month_start_at,
        month_end=month_end_at,
    )
    monthly_progress_percent = None
    if monthly_target_hours is not None and monthly_target_hours > 0:
        monthly_progress_percent = round((scheduled_hours_month / monthly_target_hours) * 100, 2)

    return EmployeeLabourIntelligenceRead(
        scheduled_hours_this_week=scheduled_hours_week,
        scheduled_hours_this_month=scheduled_hours_month,
        estimated_pay_this_week=estimated_pay_week,
        estimated_pay_this_month=estimated_pay_month,
        monthly_progress_percent=monthly_progress_percent,
    )


def _as_store_option(store: Store) -> EmployeeStoreOption:
    return EmployeeStoreOption.model_validate(store)


@router.get("/home", response_model=EmployeeHomeRead)
def get_employee_home(
    store_id: uuid.UUID | None = None,
    week_start: date_type | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeHomeRead:
    effective_week_start = week_start or _default_week_start()
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    week_start_at, week_end_at = _week_bounds(effective_week_start)

    my_shifts = _load_my_published_shifts(
        db,
        context=context,
        from_at=week_start_at,
        to_at=week_end_at,
    )

    weekly_rows = db.execute(
        select(Shift, StaffProfile.display_name)
        .select_from(Shift)
        .outerjoin(
            StaffProfile,
            and_(
                StaffProfile.tenant_id == Shift.tenant_id,
                StaffProfile.user_id == Shift.assigned_user_id,
            ),
        )
        .where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == context.selected_store.id,
            Shift.published_at.is_not(None),
            Shift.status == "scheduled",
            Shift.start_at >= week_start_at,
            Shift.start_at < week_end_at,
        )
        .order_by(Shift.start_at.asc(), Shift.id.asc())
    ).all()
    weekly_rota = [
        EmployeeWeeklyShiftRead(
            id=shift.id,
            store_id=shift.store_id,
            assigned_user_id=shift.assigned_user_id,
            assigned_staff_display_name=display_name,
            start_at=shift.start_at,
            end_at=shift.end_at,
            required_role=shift.required_role,
            status=shift.status,
            published_at=shift.published_at,
        )
        for shift, display_name in weekly_rows
    ]

    today = datetime.now(timezone.utc).date()
    today_operator_rows = db.execute(
        select(Shift.assigned_user_id, StaffProfile.display_name)
        .select_from(Shift)
        .outerjoin(
            StaffProfile,
            and_(
                StaffProfile.tenant_id == Shift.tenant_id,
                StaffProfile.user_id == Shift.assigned_user_id,
            ),
        )
        .where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == context.selected_store.id,
            Shift.published_at.is_not(None),
            Shift.status == "scheduled",
            Shift.assigned_user_id.is_not(None),
            Shift.start_at >= datetime.combine(today, time.min, tzinfo=timezone.utc),
            Shift.start_at < datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc),
        )
        .distinct()
        .order_by(Shift.assigned_user_id.asc())
    ).all()
    today_operators = [
        EmployeeTodayOperatorRead(
            user_id=user_id,
            display_name=display_name,
        )
        for user_id, display_name in today_operator_rows
        if user_id is not None
    ]

    return EmployeeHomeRead(
        week_start=effective_week_start,
        available_stores=[_as_store_option(store) for store in context.available_stores],
        selected_store=_as_store_option(context.selected_store),
        my_rota=[EmployeeShiftRead.model_validate(shift) for shift in my_shifts],
        weekly_rota=weekly_rota,
        today_operators=today_operators,
        today_tasks=None,
        labour_intelligence=_build_labour_intelligence(
            db,
            context=context,
            week_start=effective_week_start,
        ),
    )


@router.get("/me/rota", response_model=EmployeeRotaRead)
def get_my_rota(
    store_id: uuid.UUID | None = None,
    week_start: date_type | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeRotaRead:
    effective_week_start = week_start or _default_week_start()
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    week_start_at, week_end_at = _week_bounds(effective_week_start)
    shifts = _load_my_published_shifts(
        db,
        context=context,
        from_at=week_start_at,
        to_at=week_end_at,
    )
    return EmployeeRotaRead(
        week_start=effective_week_start,
        available_stores=[_as_store_option(store) for store in context.available_stores],
        selected_store=_as_store_option(context.selected_store),
        shifts=[EmployeeShiftRead.model_validate(shift) for shift in shifts],
    )


@router.get("/me/labour-intelligence", response_model=EmployeeLabourIntelligenceRead)
def get_my_labour_intelligence(
    store_id: uuid.UUID | None = None,
    week_start: date_type | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeLabourIntelligenceRead:
    effective_week_start = week_start or _default_week_start()
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    return _build_labour_intelligence(db, context=context, week_start=effective_week_start)


@router.get("/me/profile", response_model=EmployeeProfileRead)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeProfileRead:
    profile = _resolve_staff_profile_or_404(
        db,
        tenant_id=membership.tenant_id,
        user_id=current_user.id,
    )
    roles = db.scalars(
        select(StaffRole.role).where(
            StaffRole.tenant_id == membership.tenant_id,
            StaffRole.staff_id == profile.id,
        )
    ).all()
    return EmployeeProfileRead(
        staff_id=profile.id,
        user_id=profile.user_id,
        display_name=profile.display_name,
        job_title=profile.job_title,
        store_id=profile.store_id,
        pay_type=profile.pay_type,
        hourly_rate=float(profile.hourly_rate) if profile.hourly_rate is not None else None,
        phone=profile.phone,
        emergency_contact_name=profile.emergency_contact_name,
        emergency_contact_phone=profile.emergency_contact_phone,
        contract_type=profile.contract_type,
        is_active=profile.is_active,
        roles=sorted(roles),
    )


@router.get("/me/availability", response_model=EmployeeAvailabilityListRead)
def get_my_availability(
    week_start: date_type,
    store_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeAvailabilityListRead:
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    entries = db.scalars(
        select(AvailabilityEntry)
        .where(
            AvailabilityEntry.tenant_id == membership.tenant_id,
            AvailabilityEntry.user_id == current_user.id,
            AvailabilityEntry.week_start == week_start,
            AvailabilityEntry.store_id == context.selected_store.id,
        )
        .order_by(AvailabilityEntry.date.asc(), AvailabilityEntry.created_at.asc())
    ).all()
    return EmployeeAvailabilityListRead(
        week_start=week_start,
        available_stores=[_as_store_option(store) for store in context.available_stores],
        selected_store=_as_store_option(context.selected_store),
        items=[EmployeeAvailabilityRead.model_validate(entry) for entry in entries],
    )


@router.post("/me/availability", response_model=EmployeeAvailabilityRead, status_code=201)
def create_my_availability(
    payload: EmployeeAvailabilityCreate,
    store_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeAvailabilityRead:
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    _validate_availability_payload(payload)

    duplicate = db.scalar(
        select(AvailabilityEntry).where(
            AvailabilityEntry.tenant_id == membership.tenant_id,
            AvailabilityEntry.user_id == current_user.id,
            AvailabilityEntry.store_id == context.selected_store.id,
            AvailabilityEntry.week_start == payload.week_start,
            AvailabilityEntry.date == payload.date,
            AvailabilityEntry.type == payload.type,
            AvailabilityEntry.start_time == payload.start_time,
            AvailabilityEntry.end_time == payload.end_time,
        )
    )
    if duplicate is not None:
        raise ApiError(
            status_code=409,
            code="AVAILABILITY_DUPLICATE",
            message="Duplicate availability entry already exists",
        )

    entry = AvailabilityEntry(
        tenant_id=membership.tenant_id,
        user_id=current_user.id,
        store_id=context.selected_store.id,
        week_start=payload.week_start,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        type=payload.type,
        notes=payload.notes,
    )
    db.add(entry)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=current_user.id,
            action="create",
            entity_type="availability_entry",
            entity_id=str(entry.id),
        )
    )
    db.commit()
    db.refresh(entry)
    return EmployeeAvailabilityRead.model_validate(entry)


@router.delete("/me/availability/{entry_id}", response_model=EmployeeAvailabilityRead)
def delete_my_availability(
    entry_id: uuid.UUID,
    store_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeAvailabilityRead:
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    entry = db.scalar(
        select(AvailabilityEntry).where(
            AvailabilityEntry.id == entry_id,
            AvailabilityEntry.tenant_id == membership.tenant_id,
            AvailabilityEntry.user_id == current_user.id,
            AvailabilityEntry.store_id == context.selected_store.id,
        )
    )
    if entry is None:
        raise ApiError(
            status_code=404,
            code="AVAILABILITY_NOT_FOUND",
            message="Availability entry not found in active tenant",
        )

    response = EmployeeAvailabilityRead.model_validate(entry)
    db.delete(entry)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=current_user.id,
            action="delete",
            entity_type="availability_entry",
            entity_id=str(entry.id),
        )
    )
    db.commit()
    return response


@router.get("/me/swaps", response_model=EmployeeSwapListRead)
def list_my_swaps(
    store_id: uuid.UUID | None = None,
    status: ShiftRequestStatus | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeSwapListRead:
    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    query = (
        select(ShiftRequest)
        .join(Shift, Shift.id == ShiftRequest.shift_id)
        .where(
            ShiftRequest.tenant_id == membership.tenant_id,
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == context.selected_store.id,
            ShiftRequest.type == "swap",
            or_(
                ShiftRequest.requester_user_id == current_user.id,
                ShiftRequest.target_user_id == current_user.id,
            ),
            Shift.published_at.is_not(None),
        )
    )
    if status is not None:
        query = query.where(ShiftRequest.status == status)

    items = db.scalars(query.order_by(ShiftRequest.created_at.desc())).all()
    return EmployeeSwapListRead(
        status=status,
        available_stores=[_as_store_option(store) for store in context.available_stores],
        selected_store=_as_store_option(context.selected_store),
        items=[EmployeeSwapRead.model_validate(item) for item in items],
    )


@router.post("/me/swaps", response_model=EmployeeSwapRead, status_code=201)
def create_my_swap(
    payload: EmployeeSwapCreate,
    store_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> EmployeeSwapRead:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == payload.shift_id,
            Shift.tenant_id == membership.tenant_id,
        )
    )
    if shift is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )

    context = _resolve_employee_context(
        db,
        user=current_user,
        membership=membership,
        store_id=store_id,
    )
    if shift.store_id != context.selected_store.id or shift.published_at is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )

    created = create_shift_request(
        payload=ShiftRequestCreate(
            shift_id=payload.shift_id,
            type="swap",
            target_user_id=payload.target_user_id,
            notes=payload.notes,
        ),
        membership=membership,
        db=db,
    )
    return EmployeeSwapRead.model_validate(created)
