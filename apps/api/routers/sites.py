import uuid
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.shift import Shift
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.rota import SiteShiftCreate, WeeklyRotaRead, WeeklyRotaShiftRead

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


def _to_weekly_shift_read(shift: Shift) -> WeeklyRotaShiftRead:
    return WeeklyRotaShiftRead(
        id=shift.id,
        assigned_employee_account_id=shift.assigned_user_id,
        role_required=shift.required_role,
        start_time=shift.start_at,
        end_time=shift.end_at,
    )


@router.get("/{site_id}/rota/week", response_model=WeeklyRotaRead)
def get_site_weekly_rota(
    site_id: uuid.UUID,
    week_start: date_type,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> WeeklyRotaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    week_start_at, week_end_at = _week_bounds(week_start)

    shifts = db.scalars(
        select(Shift)
        .where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == site_id,
            Shift.start_at >= week_start_at,
            Shift.start_at < week_end_at,
            Shift.status == "scheduled",
        )
        .order_by(Shift.start_at.asc())
    ).all()

    return WeeklyRotaRead(
        site_id=site_id,
        week_start=week_start,
        shifts=[_to_weekly_shift_read(shift) for shift in shifts],
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
