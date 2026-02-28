import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.shift import Shift
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.shift import ShiftCreate, ShiftRead, ShiftStatus, ShiftUpdate

router = APIRouter()


def _validate_shift_times(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="end_at must be after start_at",
        )


def _get_store_or_404(db: Session, *, tenant_id: uuid.UUID, store_id: uuid.UUID) -> Store:
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )
    return store


def _validate_assigned_user(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    assigned_user_id: uuid.UUID,
) -> None:
    user = db.get(User, assigned_user_id)
    if user is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_ASSIGNED_USER_NOT_FOUND",
            message="Assigned user not found",
        )

    membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == assigned_user_id,
        )
    )
    if membership is None:
        raise ApiError(
            status_code=400,
            code="SHIFT_ASSIGNED_USER_NOT_TENANT_MEMBER",
            message="Assigned user is not a member of the active tenant",
        )


@router.post("", response_model=ShiftRead, status_code=201)
def create_shift(
    payload: ShiftCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftRead:
    _validate_shift_times(payload.start_at, payload.end_at)
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=payload.store_id)

    if payload.assigned_user_id is not None:
        _validate_assigned_user(
            db,
            tenant_id=membership.tenant_id,
            assigned_user_id=payload.assigned_user_id,
        )

    shift = Shift(
        tenant_id=membership.tenant_id,
        store_id=payload.store_id,
        assigned_user_id=payload.assigned_user_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        status="scheduled",
    )
    db.add(shift)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.commit()
    db.refresh(shift)
    return ShiftRead.model_validate(shift)


@router.patch("/{shift_id}", response_model=ShiftRead)
def update_shift(
    shift_id: uuid.UUID,
    payload: ShiftUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftRead:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == shift_id,
            Shift.tenant_id == membership.tenant_id,
        )
    )
    if shift is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "assigned_user_id" in updates and updates["assigned_user_id"] is not None:
        _validate_assigned_user(
            db,
            tenant_id=membership.tenant_id,
            assigned_user_id=updates["assigned_user_id"],
        )

    updated_start_at = updates.get("start_at", shift.start_at)
    updated_end_at = updates.get("end_at", shift.end_at)
    _validate_shift_times(updated_start_at, updated_end_at)

    for field_name, value in updates.items():
        setattr(shift, field_name, value)

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="update",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.commit()
    db.refresh(shift)
    return ShiftRead.model_validate(shift)


@router.post("/{shift_id}/cancel", response_model=ShiftRead)
def cancel_shift(
    shift_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftRead:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == shift_id,
            Shift.tenant_id == membership.tenant_id,
        )
    )
    if shift is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )

    shift.status = "cancelled"
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="cancel",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.commit()
    db.refresh(shift)
    return ShiftRead.model_validate(shift)


@router.get("", response_model=list[ShiftRead])
def list_shifts(
    store_id: uuid.UUID | None = None,
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    status: ShiftStatus | None = None,
    include_open: bool = False,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> list[ShiftRead]:
    query = select(Shift).where(Shift.tenant_id == membership.tenant_id)

    if membership.role != "admin":
        if include_open:
            query = query.where(
                or_(
                    Shift.assigned_user_id == membership.user_id,
                    Shift.assigned_user_id.is_(None),
                )
            )
        else:
            query = query.where(Shift.assigned_user_id == membership.user_id)

    if store_id is not None:
        query = query.where(Shift.store_id == store_id)
    if from_at is not None:
        query = query.where(Shift.start_at >= from_at)
    if to_at is not None:
        query = query.where(Shift.start_at <= to_at)
    if status is not None:
        query = query.where(Shift.status == status)

    shifts = db.scalars(query.order_by(Shift.start_at.asc())).all()
    return [ShiftRead.model_validate(shift) for shift in shifts]


@router.get("/{shift_id}", response_model=ShiftRead)
def get_shift(
    shift_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> ShiftRead:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == shift_id,
            Shift.tenant_id == membership.tenant_id,
        )
    )
    if shift is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )

    if membership.role != "admin" and shift.assigned_user_id != membership.user_id:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )
    return ShiftRead.model_validate(shift)
