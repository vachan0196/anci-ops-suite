from datetime import date as date_type
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.hour_target import HourTarget
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.hour_target import HourTargetRead, HourTargetUpsert

router = APIRouter()


def _validate_store_belongs_to_tenant(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
) -> None:
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


def _validate_target_user_membership(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(
            status_code=404,
            code="HOUR_TARGET_USER_NOT_FOUND",
            message="User not found",
        )

    tenant_membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == user_id,
        )
    )
    if tenant_membership is None:
        raise ApiError(
            status_code=400,
            code="HOUR_TARGET_USER_NOT_TENANT_MEMBER",
            message="User is not a member of the active tenant",
        )


def _validate_hour_values(payload: HourTargetUpsert) -> None:
    for field_name in ["min_hours", "max_hours", "target_hours"]:
        value = getattr(payload, field_name)
        if value is not None and value < 0:
            raise ApiError(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"{field_name} must be >= 0",
            )

    if (
        payload.min_hours is not None
        and payload.max_hours is not None
        and payload.min_hours > payload.max_hours
    ):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="min_hours must be <= max_hours",
        )

    if payload.target_hours is not None:
        if payload.min_hours is not None and payload.target_hours < payload.min_hours:
            raise ApiError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="target_hours must be >= min_hours when min_hours is set",
            )
        if payload.max_hours is not None and payload.target_hours > payload.max_hours:
            raise ApiError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="target_hours must be <= max_hours when max_hours is set",
            )


@router.put("", response_model=HourTargetRead)
def upsert_hour_target(
    payload: HourTargetUpsert,
    response: Response,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> HourTargetRead:
    _validate_hour_values(payload)
    _validate_target_user_membership(
        db,
        tenant_id=membership.tenant_id,
        user_id=payload.user_id,
    )
    if payload.store_id is not None:
        _validate_store_belongs_to_tenant(
            db,
            tenant_id=membership.tenant_id,
            store_id=payload.store_id,
        )

    query = select(HourTarget).where(
        HourTarget.tenant_id == membership.tenant_id,
        HourTarget.user_id == payload.user_id,
        HourTarget.week_start == payload.week_start,
    )
    if payload.store_id is None:
        query = query.where(HourTarget.store_id.is_(None))
    else:
        query = query.where(HourTarget.store_id == payload.store_id)

    target = db.scalar(query)
    is_create = target is None
    if is_create:
        target = HourTarget(
            tenant_id=membership.tenant_id,
            user_id=payload.user_id,
            store_id=payload.store_id,
            week_start=payload.week_start,
            min_hours=payload.min_hours,
            max_hours=payload.max_hours,
            target_hours=payload.target_hours,
            notes=payload.notes,
        )
        db.add(target)
    else:
        target.min_hours = payload.min_hours
        target.max_hours = payload.max_hours
        target.target_hours = payload.target_hours
        target.notes = payload.notes

    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="upsert",
            entity_type="hour_target",
            entity_id=str(target.id),
        )
    )
    db.commit()
    db.refresh(target)
    response.status_code = status.HTTP_201_CREATED if is_create else status.HTTP_200_OK
    return HourTargetRead.model_validate(target)


@router.get("", response_model=list[HourTargetRead])
def list_hour_targets(
    week_start: date_type,
    store_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[HourTargetRead]:
    query = select(HourTarget).where(
        HourTarget.tenant_id == membership.tenant_id,
        HourTarget.week_start == week_start,
    )
    if store_id is not None:
        query = query.where(HourTarget.store_id == store_id)
    if user_id is not None:
        query = query.where(HourTarget.user_id == user_id)

    rows = db.scalars(
        query.order_by(HourTarget.user_id.asc(), HourTarget.created_at.asc())
    ).all()
    return [HourTargetRead.model_validate(row) for row in rows]


@router.get("/me", response_model=list[HourTargetRead])
def list_my_hour_targets(
    week_start: date_type,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> list[HourTargetRead]:
    rows = db.scalars(
        select(HourTarget)
        .where(
            HourTarget.tenant_id == membership.tenant_id,
            HourTarget.user_id == membership.user_id,
            HourTarget.week_start == week_start,
        )
        .order_by(HourTarget.created_at.asc())
    ).all()
    return [HourTargetRead.model_validate(row) for row in rows]


@router.delete("/{target_id}", response_model=HourTargetRead)
def delete_hour_target(
    target_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> HourTargetRead:
    target = db.scalar(
        select(HourTarget).where(
            HourTarget.id == target_id,
            HourTarget.tenant_id == membership.tenant_id,
        )
    )
    if target is None:
        raise ApiError(
            status_code=404,
            code="HOUR_TARGET_NOT_FOUND",
            message="Hour target not found in active tenant",
        )

    response = HourTargetRead.model_validate(target)
    db.delete(target)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="delete",
            entity_type="hour_target",
            entity_id=str(target.id),
        )
    )
    db.commit()
    return response
