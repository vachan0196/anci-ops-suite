import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.shift import Shift
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.staff_role import StaffRole
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers.rota_recommendations import build_recalibrated_recommendation_for_shift
from apps.api.schemas.shift import (
    ShiftAssignRequest,
    ShiftAssignResponse,
    ShiftCreate,
    ShiftPublishRangeRequest,
    ShiftPublishRangeResponse,
    ShiftRead,
    ShiftStatus,
    ShiftUpdate,
)

router = APIRouter()
_AVAILABLE_TYPES = {"available", "available_extra"}


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = role.strip().lower()
    return normalized or None


def _validate_shift_times(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="end_at must be after start_at",
        )


def _validate_range(from_at: datetime, to_at: datetime) -> None:
    if to_at <= from_at:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="'to' must be after 'from'",
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


def _get_shift_or_404(db: Session, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == shift_id,
            Shift.tenant_id == tenant_id,
        )
    )
    if shift is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_NOT_FOUND",
            message="Shift not found in active tenant",
        )
    return shift


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


def _validate_assigned_user_in_tenant_or_404(
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
            message="Assigned user not found in active tenant",
        )

    membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == assigned_user_id,
        )
    )
    if membership is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_ASSIGNED_USER_NOT_FOUND",
            message="Assigned user not found in active tenant",
        )


def _get_staff_profile_for_user_or_404(
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
    return profile


def _availability_covers_shift(entries: list[AvailabilityEntry], shift: Shift) -> bool:
    shift_start = _as_utc(shift.start_at)
    shift_end = _as_utc(shift.end_at)
    shift_date = shift_start.date()
    shift_starts_and_ends_same_day = shift_start.date() == shift_end.date()
    shift_start_time = shift_start.time().replace(tzinfo=None)
    shift_end_time = shift_end.time().replace(tzinfo=None)

    for entry in entries:
        if entry.date != shift_date:
            continue
        if entry.start_time is None and entry.end_time is None:
            return True
        if not shift_starts_and_ends_same_day:
            continue
        if entry.start_time is not None and entry.end_time is not None:
            if entry.start_time <= shift_start_time and entry.end_time >= shift_end_time:
                return True
    return False


def _has_required_role(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    required_role: str | None,
) -> bool:
    normalized_required_role = _normalize_role(required_role)
    if normalized_required_role is None:
        return True

    profile = _get_staff_profile_for_user_or_404(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    role = db.scalar(
        select(StaffRole).where(
            StaffRole.tenant_id == tenant_id,
            StaffRole.staff_id == profile.id,
            StaffRole.role == normalized_required_role,
        )
    )
    return role is not None


def _is_available_for_shift(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    shift: Shift,
) -> bool:
    shift_start = _as_utc(shift.start_at)
    week_start = shift_start.date() - timedelta(days=shift_start.date().weekday())
    entries = db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.tenant_id == tenant_id,
            AvailabilityEntry.user_id == user_id,
            AvailabilityEntry.week_start == week_start,
            AvailabilityEntry.date == shift_start.date(),
            AvailabilityEntry.type.in_(tuple(_AVAILABLE_TYPES)),
            or_(
                AvailabilityEntry.store_id == shift.store_id,
                AvailabilityEntry.store_id.is_(None),
            ),
        )
    ).all()
    return _availability_covers_shift(entries, shift)


def _apply_assignment(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    shift: Shift,
    assigned_user_id: uuid.UUID,
    override_reason: str | None = None,
) -> tuple[bool, bool]:
    _validate_assigned_user_in_tenant_or_404(db, tenant_id=tenant_id, assigned_user_id=assigned_user_id)

    role_override = not _has_required_role(
        db,
        tenant_id=tenant_id,
        user_id=assigned_user_id,
        required_role=shift.required_role,
    )
    availability_override = not _is_available_for_shift(
        db,
        tenant_id=tenant_id,
        user_id=assigned_user_id,
        shift=shift,
    )

    shift.assigned_user_id = assigned_user_id
    shift.role_override = role_override
    shift.availability_override = availability_override
    shift.overridden_by_user_id = actor_user_id
    shift.overridden_at = datetime.now(timezone.utc)
    shift.override_reason = override_reason
    return role_override, availability_override


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
        required_role=_normalize_role(payload.required_role),
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
    shift = _get_shift_or_404(db, tenant_id=membership.tenant_id, shift_id=shift_id)

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
        if field_name == "required_role":
            value = _normalize_role(value)
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


@router.patch("/{shift_id}/assign", response_model=ShiftAssignResponse)
def assign_shift_with_override(
    shift_id: uuid.UUID,
    payload: ShiftAssignRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftAssignResponse:
    shift = _get_shift_or_404(db, tenant_id=membership.tenant_id, shift_id=shift_id)
    role_override, availability_override = _apply_assignment(
        db,
        tenant_id=membership.tenant_id,
        actor_user_id=membership.user_id,
        shift=shift,
        assigned_user_id=payload.assigned_user_id,
        override_reason=payload.override_reason,
    )

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="manager_override_assignment",
            entity_type="shift",
            entity_id=str(shift.id),
        )
    )
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="manager_override_assigned_user",
            entity_type="user",
            entity_id=str(payload.assigned_user_id),
        )
    )
    if role_override:
        db.add(
            AuditLog(
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                action="manager_override_role_mismatch",
                entity_type="shift",
                entity_id=str(shift.id),
            )
        )
    if availability_override:
        db.add(
            AuditLog(
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                action="manager_override_availability_mismatch",
                entity_type="shift",
                entity_id=str(shift.id),
            )
        )
    if payload.override_reason:
        db.add(
            AuditLog(
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                action="manager_override_reason",
                entity_type="note",
                entity_id=payload.override_reason[:64],
            )
        )

    recommendations_payload = None
    if payload.mode == "recalibrate":
        db.flush()
        recommendations = build_recalibrated_recommendation_for_shift(
            db,
            tenant_id=membership.tenant_id,
            actor_user_id=membership.user_id,
            shift=shift,
        )
        db.refresh(shift)
        recommendations_payload = recommendations.model_dump(mode="json")
    else:
        db.commit()
        db.refresh(shift)

    return ShiftAssignResponse(
        shift=ShiftRead.model_validate(shift),
        recommendations=recommendations_payload,
    )


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


@router.post("/publish", response_model=ShiftPublishRangeResponse)
def publish_shift_range(
    payload: ShiftPublishRangeRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftPublishRangeResponse:
    _validate_range(payload.from_at, payload.to_at)
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=payload.store_id)

    now = datetime.now(timezone.utc)
    shifts = db.scalars(
        select(Shift).where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == payload.store_id,
            Shift.start_at >= payload.from_at,
            Shift.start_at < payload.to_at,
        )
    ).all()
    for shift in shifts:
        shift.published_at = now
        shift.published_by_user_id = membership.user_id

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="publish_range",
            entity_type="shift",
            entity_id=str(payload.store_id),
        )
    )
    db.commit()
    return ShiftPublishRangeResponse(updated_count=len(shifts))


@router.post("/unpublish", response_model=ShiftPublishRangeResponse)
def unpublish_shift_range(
    payload: ShiftPublishRangeRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftPublishRangeResponse:
    _validate_range(payload.from_at, payload.to_at)
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=payload.store_id)

    shifts = db.scalars(
        select(Shift).where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == payload.store_id,
            Shift.start_at >= payload.from_at,
            Shift.start_at < payload.to_at,
        )
    ).all()
    for shift in shifts:
        shift.published_at = None
        shift.published_by_user_id = None

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="unpublish_range",
            entity_type="shift",
            entity_id=str(payload.store_id),
        )
    )
    db.commit()
    return ShiftPublishRangeResponse(updated_count=len(shifts))


@router.get("/publish-status")
def get_shift_publish_status(
    store_id: uuid.UUID,
    from_at: datetime = Query(alias="from"),
    to_at: datetime = Query(alias="to"),
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> dict:
    _validate_range(from_at, to_at)
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=store_id)

    total = db.scalar(
        select(func.count(Shift.id)).where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == store_id,
            Shift.start_at >= from_at,
            Shift.start_at < to_at,
        )
    )
    published = db.scalar(
        select(func.count(Shift.id)).where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == store_id,
            Shift.start_at >= from_at,
            Shift.start_at < to_at,
            Shift.published_at.is_not(None),
        )
    )
    total_shifts = int(total or 0)
    published_count = int(published or 0)
    return {
        "store_id": str(store_id),
        "total": total_shifts,
        "published": published_count,
        "unpublished": total_shifts - published_count,
    }


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
