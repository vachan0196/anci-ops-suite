from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.shift import Shift
from apps.api.models.shift_request import ShiftRequest
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers.shifts import _apply_assignment
from apps.api.schemas.shift_request import (
    ShiftRequestCreate,
    ShiftRequestRead,
    ShiftRequestStatus,
    ShiftRequestType,
)

router = APIRouter()


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


def _get_shift_request_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    request_id: uuid.UUID,
) -> ShiftRequest:
    shift_request = db.scalar(
        select(ShiftRequest).where(
            ShiftRequest.id == request_id,
            ShiftRequest.tenant_id == tenant_id,
        )
    )
    if shift_request is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_REQUEST_NOT_FOUND",
            message="Shift request not found in active tenant",
        )
    return shift_request


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validate_tenant_user_or_raise(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(
            status_code=404,
            code="SHIFT_REQUEST_TARGET_USER_NOT_FOUND",
            message="Target user not found",
        )
    membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == user_id,
        )
    )
    if membership is None:
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_TARGET_NOT_TENANT_MEMBER",
            message="Target user is not a member of the active tenant",
        )


def _enforce_shift_change_min_hours(shift: Shift) -> None:
    now = datetime.now(timezone.utc)
    delta = _as_utc(shift.start_at) - now
    min_seconds = settings.SHIFT_CHANGE_MIN_HOURS * 3600
    if delta.total_seconds() < min_seconds:
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_TOO_CLOSE_TO_START",
            message=f"Shift changes require at least {settings.SHIFT_CHANGE_MIN_HOURS} hours before shift start",
        )


@router.post("", response_model=ShiftRequestRead, status_code=201)
def create_shift_request(
    payload: ShiftRequestCreate,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> ShiftRequestRead:
    shift = _get_shift_or_404(db, tenant_id=membership.tenant_id, shift_id=payload.shift_id)
    if shift.status != "scheduled":
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_SHIFT_STATUS",
            message="Shift requests can only be created for scheduled shifts",
        )

    if payload.type == "pickup" and shift.assigned_user_id is not None:
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_PICKUP_REQUIRES_OPEN_SHIFT",
            message="Pickup request requires an open shift",
        )
    if payload.type in {"drop", "swap"} and shift.assigned_user_id != membership.user_id:
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_OWNERSHIP_REQUIRED",
            message="Drop and swap requests require ownership of the shift",
        )
    if payload.type in {"drop", "swap"}:
        _enforce_shift_change_min_hours(shift)

    if payload.type == "swap":
        if payload.target_user_id is None:
            raise ApiError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="target_user_id is required for swap requests",
            )
        if payload.target_user_id == membership.user_id:
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_INVALID_TARGET",
                message="Target user must be different from requester",
            )
        _validate_tenant_user_or_raise(
            db,
            tenant_id=membership.tenant_id,
            user_id=payload.target_user_id,
        )

    existing_pending = db.scalar(
        select(ShiftRequest).where(
            ShiftRequest.tenant_id == membership.tenant_id,
            ShiftRequest.shift_id == payload.shift_id,
            ShiftRequest.requester_user_id == membership.user_id,
            ShiftRequest.status.in_(["pending", "pending_target", "target_accepted"]),
        )
    )
    if existing_pending is not None:
        raise ApiError(
            status_code=409,
            code="SHIFT_REQUEST_DUPLICATE_PENDING",
            message="A pending request already exists for this shift and requester",
        )

    shift_request = ShiftRequest(
        tenant_id=membership.tenant_id,
        shift_id=payload.shift_id,
        requester_user_id=membership.user_id,
        target_user_id=payload.target_user_id if payload.type == "swap" else None,
        type=payload.type,
        status="pending_target" if payload.type == "swap" else "pending",
        notes=payload.notes,
    )
    db.add(shift_request)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create",
            entity_type="shift_request",
            entity_id=str(shift_request.id),
        )
    )
    db.commit()
    db.refresh(shift_request)
    return ShiftRequestRead.model_validate(shift_request)


@router.get("", response_model=list[ShiftRequestRead])
def list_shift_requests(
    status: ShiftRequestStatus | None = None,
    type: ShiftRequestType | None = None,
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    store_id: uuid.UUID | None = None,
    requester_user_id: uuid.UUID | None = None,
    target_user_id: uuid.UUID | None = None,
    include_incoming: bool = False,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> list[ShiftRequestRead]:
    query = (
        select(ShiftRequest)
        .join(Shift, Shift.id == ShiftRequest.shift_id)
        .where(
            ShiftRequest.tenant_id == membership.tenant_id,
            Shift.tenant_id == membership.tenant_id,
        )
    )

    if membership.role != "admin":
        if include_incoming:
            query = query.where(
                or_(
                    ShiftRequest.requester_user_id == membership.user_id,
                    ShiftRequest.target_user_id == membership.user_id,
                )
            )
        else:
            query = query.where(ShiftRequest.requester_user_id == membership.user_id)
    else:
        if requester_user_id is not None:
            query = query.where(ShiftRequest.requester_user_id == requester_user_id)
        if target_user_id is not None:
            query = query.where(ShiftRequest.target_user_id == target_user_id)

    if status is not None:
        query = query.where(ShiftRequest.status == status)
    if type is not None:
        query = query.where(ShiftRequest.type == type)
    if from_at is not None:
        query = query.where(ShiftRequest.created_at >= from_at)
    if to_at is not None:
        query = query.where(ShiftRequest.created_at <= to_at)
    if store_id is not None:
        query = query.where(Shift.store_id == store_id)

    requests = db.scalars(query.order_by(ShiftRequest.created_at.desc())).all()
    return [ShiftRequestRead.model_validate(item) for item in requests]


@router.post("/{request_id}/cancel", response_model=ShiftRequestRead)
def cancel_shift_request(
    request_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> ShiftRequestRead:
    shift_request = _get_shift_request_or_404(
        db,
        tenant_id=membership.tenant_id,
        request_id=request_id,
    )

    if shift_request.requester_user_id != membership.user_id:
        raise ApiError(
            status_code=403,
            code="SHIFT_REQUEST_CANCEL_FORBIDDEN",
            message="Only the requester can cancel this shift request",
        )
    if shift_request.type == "swap":
        allowed_status = "pending_target"
    else:
        allowed_status = "pending"
    if shift_request.status != allowed_status:
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_STATE",
            message="Only pending shift requests can be cancelled",
        )

    shift_request.status = "cancelled"
    shift_request.resolved_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="cancel",
            entity_type="shift_request",
            entity_id=str(shift_request.id),
        )
    )
    db.commit()
    db.refresh(shift_request)
    return ShiftRequestRead.model_validate(shift_request)


@router.post("/{request_id}/accept", response_model=ShiftRequestRead)
def accept_swap_request(
    request_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> ShiftRequestRead:
    shift_request = _get_shift_request_or_404(
        db,
        tenant_id=membership.tenant_id,
        request_id=request_id,
    )
    if shift_request.type != "swap":
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_TYPE",
            message="Only swap requests can be accepted",
        )
    if shift_request.status != "pending_target":
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_STATE",
            message="Only pending_target swap requests can be accepted",
        )
    if shift_request.target_user_id != membership.user_id:
        raise ApiError(
            status_code=403,
            code="SHIFT_REQUEST_ACCEPT_FORBIDDEN",
            message="Only the target user can accept this swap request",
        )

    shift_request.status = "target_accepted"
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="accept",
            entity_type="shift_request",
            entity_id=str(shift_request.id),
        )
    )
    db.commit()
    db.refresh(shift_request)
    return ShiftRequestRead.model_validate(shift_request)


@router.post("/{request_id}/decline", response_model=ShiftRequestRead)
def decline_swap_request(
    request_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> ShiftRequestRead:
    shift_request = _get_shift_request_or_404(
        db,
        tenant_id=membership.tenant_id,
        request_id=request_id,
    )
    if shift_request.type != "swap":
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_TYPE",
            message="Only swap requests can be declined",
        )
    if shift_request.status != "pending_target":
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_STATE",
            message="Only pending_target swap requests can be declined",
        )
    if shift_request.target_user_id != membership.user_id:
        raise ApiError(
            status_code=403,
            code="SHIFT_REQUEST_DECLINE_FORBIDDEN",
            message="Only the target user can decline this swap request",
        )

    shift_request.status = "target_declined"
    shift_request.resolved_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="decline",
            entity_type="shift_request",
            entity_id=str(shift_request.id),
        )
    )
    db.commit()
    db.refresh(shift_request)
    return ShiftRequestRead.model_validate(shift_request)


@router.post("/{request_id}/approve", response_model=ShiftRequestRead)
def approve_shift_request(
    request_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftRequestRead:
    shift_request = _get_shift_request_or_404(
        db,
        tenant_id=membership.tenant_id,
        request_id=request_id,
    )
    shift = _get_shift_or_404(db, tenant_id=membership.tenant_id, shift_id=shift_request.shift_id)

    shift_changed = False
    if shift_request.type == "pickup":
        if shift_request.status != "pending":
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_INVALID_STATE",
                message="Only pending pickup requests can be approved",
            )
        if shift.assigned_user_id is not None:
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_PICKUP_REQUIRES_OPEN_SHIFT",
                message="Pickup request requires an open shift",
            )
        _apply_assignment(
            db,
            tenant_id=membership.tenant_id,
            actor_user_id=membership.user_id,
            shift=shift,
            assigned_user_id=shift_request.requester_user_id,
            override_reason=f"shift_request:{shift_request.id}",
        )
        shift_changed = True
    elif shift_request.type == "drop":
        if shift_request.status != "pending":
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_INVALID_STATE",
                message="Only pending drop requests can be approved",
            )
        if shift.assigned_user_id != shift_request.requester_user_id:
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_OWNERSHIP_REQUIRED",
                message="Drop request requires ownership of the shift",
            )
        shift.assigned_user_id = None
        shift.role_override = False
        shift.availability_override = False
        shift.overridden_by_user_id = None
        shift.overridden_at = None
        shift.override_reason = None
        shift_changed = True
    elif shift_request.type == "swap":
        if shift_request.status != "target_accepted":
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_INVALID_STATE",
                message="Swap request must be target_accepted before admin approval",
            )
        if shift_request.target_user_id is None:
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_INVALID_TARGET",
                message="Swap request missing target user",
            )
        _validate_tenant_user_or_raise(
            db,
            tenant_id=membership.tenant_id,
            user_id=shift_request.target_user_id,
        )
        _apply_assignment(
            db,
            tenant_id=membership.tenant_id,
            actor_user_id=membership.user_id,
            shift=shift,
            assigned_user_id=shift_request.target_user_id,
            override_reason=f"shift_request:{shift_request.id}",
        )
        shift_changed = True

    shift_request.status = "approved"
    shift_request.resolved_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="approve",
            entity_type="shift_request",
            entity_id=str(shift_request.id),
        )
    )
    if shift_changed:
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
    db.refresh(shift_request)
    return ShiftRequestRead.model_validate(shift_request)


@router.post("/{request_id}/reject", response_model=ShiftRequestRead)
def reject_shift_request(
    request_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ShiftRequestRead:
    shift_request = _get_shift_request_or_404(
        db,
        tenant_id=membership.tenant_id,
        request_id=request_id,
    )
    if shift_request.type == "swap":
        if shift_request.status not in {"pending_target", "target_accepted"}:
            raise ApiError(
                status_code=400,
                code="SHIFT_REQUEST_INVALID_STATE",
                message="Swap request can be rejected only from pending_target or target_accepted",
            )
    elif shift_request.status != "pending":
        raise ApiError(
            status_code=400,
            code="SHIFT_REQUEST_INVALID_STATE",
            message="Only pending shift requests can be rejected",
        )

    shift_request.status = "rejected"
    shift_request.resolved_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="reject",
            entity_type="shift_request",
            entity_id=str(shift_request.id),
        )
    )
    db.commit()
    db.refresh(shift_request)
    return ShiftRequestRead.model_validate(shift_request)
