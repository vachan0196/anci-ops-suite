import uuid
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.shift import Shift
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
from apps.api.models.store_opening_hours import StoreOpeningHours
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.rota import (
    RotaWeekActionRequest,
    SiteShiftCreate,
    SiteShiftUpdate,
    WeeklyRotaRead,
    WeeklyRotaShiftRead,
)

router = APIRouter()


def _week_bounds(week_start: date_type) -> tuple[datetime, datetime]:
    week_start_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    return week_start_at, week_start_at + timedelta(days=7)


def _get_site_or_404(db: Session, *, tenant_id: uuid.UUID, site_id: uuid.UUID) -> Store:
    site = db.scalar(
        select(Store).where(
            Store.id == site_id,
            Store.tenant_id == tenant_id,
        )
    )
    if site is None:
        raise ApiError(
            status_code=404,
            code="SITE_NOT_FOUND",
            message="Site not found in active tenant",
        )
    return site


def _get_shift_for_site_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    shift_id: uuid.UUID,
) -> Shift:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == shift_id,
            Shift.tenant_id == tenant_id,
            Shift.store_id == site_id,
        )
    )
    if shift is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found for selected site",
        )
    return shift


def _normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = role.strip().lower()
    return normalized or None


def _validate_shift_times(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="end_time must be after start_time",
        )


def _validate_assigned_staff_for_site(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    assigned_employee_account_id: uuid.UUID,
) -> None:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == tenant_id,
            StaffProfile.store_id == site_id,
            StaffProfile.user_id == assigned_employee_account_id,
            StaffProfile.is_active.is_(True),
        )
    )
    if profile is None:
        raise ApiError(
            status_code=400,
            code="SHIFT_ASSIGNED_STAFF_INVALID",
            message="Assigned staff must be active at the selected site",
        )


def _ensure_shift_is_editable(shift: Shift) -> None:
    if shift.status == "cancelled":
        raise ApiError(
            status_code=409,
            code="SHIFT_ALREADY_CANCELLED",
            message="Cancelled shifts cannot be changed",
        )
    if shift.published_at is not None:
        raise ApiError(
            status_code=409,
            code="SHIFT_ALREADY_PUBLISHED",
            message="Published shifts cannot be changed in draft rota editing",
        )


def _to_weekly_shift_read(shift: Shift) -> WeeklyRotaShiftRead:
    return WeeklyRotaShiftRead(
        id=shift.id,
        assigned_employee_account_id=shift.assigned_user_id,
        role_required=shift.required_role,
        start_time=shift.start_at,
        end_time=shift.end_at,
    )


def _get_active_week_shifts(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    week_start: date_type,
) -> list[Shift]:
    week_start_at, week_end_at = _week_bounds(week_start)
    return list(
        db.scalars(
            select(Shift)
            .where(
                Shift.tenant_id == tenant_id,
                Shift.store_id == site_id,
                Shift.start_at >= week_start_at,
                Shift.start_at < week_end_at,
                Shift.status == "scheduled",
            )
            .order_by(Shift.start_at.asc())
        ).all()
    )


def _weekly_rota_response(
    *,
    site_id: uuid.UUID,
    week_start: date_type,
    shifts: list[Shift],
) -> WeeklyRotaRead:
    published_shift_count = sum(1 for shift in shifts if shift.published_at is not None)
    draft_shift_count = sum(1 for shift in shifts if shift.published_at is None)
    return WeeklyRotaRead(
        site_id=site_id,
        week_start=week_start,
        is_published=bool(shifts) and draft_shift_count == 0,
        published_shift_count=published_shift_count,
        draft_shift_count=draft_shift_count,
        shifts=[_to_weekly_shift_read(shift) for shift in shifts],
    )


def _site_is_operationally_ready(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
) -> bool:
    open_day_count = db.scalar(
        select(func.count())
        .select_from(StoreOpeningHours)
        .where(
            StoreOpeningHours.tenant_id == tenant_id,
            StoreOpeningHours.store_id == site_id,
            StoreOpeningHours.is_closed.is_(False),
            StoreOpeningHours.open_time.is_not(None),
            StoreOpeningHours.close_time.is_not(None),
        )
    )
    staff_count = db.scalar(
        select(func.count())
        .select_from(StaffProfile)
        .where(
            StaffProfile.tenant_id == tenant_id,
            StaffProfile.store_id == site_id,
            StaffProfile.is_active.is_(True),
        )
    )
    return bool(open_day_count) and bool(staff_count)


@router.get("/{site_id}/rota/week", response_model=WeeklyRotaRead)
def get_site_weekly_rota(
    site_id: uuid.UUID,
    week_start: date_type,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> WeeklyRotaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    shifts = _get_active_week_shifts(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        week_start=week_start,
    )
    return _weekly_rota_response(site_id=site_id, week_start=week_start, shifts=shifts)


@router.post("/{site_id}/rota/publish", response_model=WeeklyRotaRead)
def publish_site_rota(
    site_id: uuid.UUID,
    payload: RotaWeekActionRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WeeklyRotaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    if not _site_is_operationally_ready(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
    ):
        raise ApiError(
            status_code=409,
            code="SITE_NOT_READY",
            message="Site is not operationally ready for rota publishing",
        )

    shifts = _get_active_week_shifts(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        week_start=payload.week_start,
    )
    if not shifts:
        raise ApiError(
            status_code=409,
            code="ROTA_NO_SHIFTS",
            message="No active shifts exist for the selected week",
        )

    draft_shifts = [shift for shift in shifts if shift.published_at is None]
    if not draft_shifts:
        raise ApiError(
            status_code=409,
            code="ROTA_ALREADY_PUBLISHED",
            message="The selected rota is already published",
        )

    published_at = datetime.now(timezone.utc)
    for shift in draft_shifts:
        shift.published_at = published_at
        shift.published_by_user_id = membership.user_id

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="rota_published",
            entity_type="rota",
            entity_id=f"{site_id}:{payload.week_start.isoformat()}",
        )
    )
    db.commit()

    shifts = _get_active_week_shifts(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        week_start=payload.week_start,
    )
    return _weekly_rota_response(
        site_id=site_id,
        week_start=payload.week_start,
        shifts=shifts,
    )


@router.post("/{site_id}/rota/unpublish", response_model=WeeklyRotaRead)
def unpublish_site_rota(
    site_id: uuid.UUID,
    payload: RotaWeekActionRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WeeklyRotaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    shifts = _get_active_week_shifts(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        week_start=payload.week_start,
    )
    published_shifts = [shift for shift in shifts if shift.published_at is not None]
    if not published_shifts:
        raise ApiError(
            status_code=409,
            code="ROTA_NOT_PUBLISHED",
            message="No published rota exists for the selected week",
        )

    for shift in published_shifts:
        shift.published_at = None
        shift.published_by_user_id = None

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="rota_unpublished",
            entity_type="rota",
            entity_id=f"{site_id}:{payload.week_start.isoformat()}",
        )
    )
    db.commit()

    shifts = _get_active_week_shifts(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        week_start=payload.week_start,
    )
    return _weekly_rota_response(
        site_id=site_id,
        week_start=payload.week_start,
        shifts=shifts,
    )


@router.post("/{site_id}/shifts", response_model=WeeklyRotaShiftRead, status_code=201)
def create_site_shift(
    site_id: uuid.UUID,
    payload: SiteShiftCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WeeklyRotaShiftRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    _validate_shift_times(payload.start_time, payload.end_time)

    if payload.assigned_employee_account_id is not None:
        _validate_assigned_staff_for_site(
            db,
            tenant_id=membership.tenant_id,
            site_id=site_id,
            assigned_employee_account_id=payload.assigned_employee_account_id,
        )

    shift = Shift(
        tenant_id=membership.tenant_id,
        store_id=site_id,
        assigned_user_id=payload.assigned_employee_account_id,
        required_role=_normalize_role(payload.role_required),
        start_at=payload.start_time,
        end_at=payload.end_time,
        status="scheduled",
        published_at=None,
    )
    db.add(shift)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="shift_created",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.commit()
    db.refresh(shift)
    return _to_weekly_shift_read(shift)


@router.patch("/{site_id}/shifts/{shift_id}", response_model=WeeklyRotaShiftRead)
def update_site_shift(
    site_id: uuid.UUID,
    shift_id: uuid.UUID,
    payload: SiteShiftUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WeeklyRotaShiftRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    shift = _get_shift_for_site_or_404(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        shift_id=shift_id,
    )
    _ensure_shift_is_editable(shift)
    _validate_shift_times(payload.start_time, payload.end_time)

    if payload.assigned_employee_account_id is not None:
        _validate_assigned_staff_for_site(
            db,
            tenant_id=membership.tenant_id,
            site_id=site_id,
            assigned_employee_account_id=payload.assigned_employee_account_id,
        )

    shift.assigned_user_id = payload.assigned_employee_account_id
    shift.required_role = _normalize_role(payload.role_required)
    shift.start_at = payload.start_time
    shift.end_at = payload.end_time
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="shift_updated",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.commit()
    db.refresh(shift)
    return _to_weekly_shift_read(shift)


@router.post("/{site_id}/shifts/{shift_id}/cancel", response_model=WeeklyRotaShiftRead)
def cancel_site_shift(
    site_id: uuid.UUID,
    shift_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WeeklyRotaShiftRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    shift = _get_shift_for_site_or_404(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        shift_id=shift_id,
    )
    _ensure_shift_is_editable(shift)

    shift.status = "cancelled"
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="shift_cancelled",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.commit()
    db.refresh(shift)
    return _to_weekly_shift_read(shift)
