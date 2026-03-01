from datetime import date as date_type, timedelta
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.availability import AvailabilityCreate, AvailabilityRead, AvailabilityType

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


def _validate_availability_payload(payload: AvailabilityCreate) -> None:
    if payload.date < payload.week_start or payload.date >= (payload.week_start + timedelta(days=7)):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="date must be within the specified week_start window",
        )
    if (payload.start_time is None) ^ (payload.end_time is None):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="start_time and end_time must both be set together",
        )
    if payload.start_time is not None and payload.end_time is not None and payload.end_time <= payload.start_time:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="end_time must be after start_time",
        )


@router.post("", response_model=AvailabilityRead, status_code=201)
def create_availability(
    payload: AvailabilityCreate,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> AvailabilityRead:
    _validate_availability_payload(payload)
    if payload.store_id is not None:
        _validate_store_belongs_to_tenant(
            db,
            tenant_id=membership.tenant_id,
            store_id=payload.store_id,
        )

    duplicate_query = select(AvailabilityEntry).where(
        AvailabilityEntry.tenant_id == membership.tenant_id,
        AvailabilityEntry.user_id == membership.user_id,
        AvailabilityEntry.week_start == payload.week_start,
        AvailabilityEntry.date == payload.date,
        AvailabilityEntry.type == payload.type,
    )
    if payload.store_id is None:
        duplicate_query = duplicate_query.where(AvailabilityEntry.store_id.is_(None))
    else:
        duplicate_query = duplicate_query.where(AvailabilityEntry.store_id == payload.store_id)
    if payload.start_time is None:
        duplicate_query = duplicate_query.where(AvailabilityEntry.start_time.is_(None))
    else:
        duplicate_query = duplicate_query.where(AvailabilityEntry.start_time == payload.start_time)
    if payload.end_time is None:
        duplicate_query = duplicate_query.where(AvailabilityEntry.end_time.is_(None))
    else:
        duplicate_query = duplicate_query.where(AvailabilityEntry.end_time == payload.end_time)

    existing = db.scalar(duplicate_query)
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="AVAILABILITY_DUPLICATE",
            message="Duplicate availability entry already exists",
        )

    entry = AvailabilityEntry(
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        store_id=payload.store_id,
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
            user_id=membership.user_id,
            action="create",
            entity_type="availability_entry",
            entity_id=str(entry.id),
        )
    )
    db.commit()
    db.refresh(entry)
    return AvailabilityRead.model_validate(entry)


@router.get("", response_model=list[AvailabilityRead])
def list_availability(
    week_start: date_type,
    date: date_type | None = None,
    type: AvailabilityType | None = None,
    store_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> list[AvailabilityRead]:
    query = select(AvailabilityEntry).where(
        AvailabilityEntry.tenant_id == membership.tenant_id,
        AvailabilityEntry.week_start == week_start,
    )
    if membership.role != "admin":
        query = query.where(AvailabilityEntry.user_id == membership.user_id)
    elif user_id is not None:
        query = query.where(AvailabilityEntry.user_id == user_id)

    if date is not None:
        query = query.where(AvailabilityEntry.date == date)
    if type is not None:
        query = query.where(AvailabilityEntry.type == type)
    if store_id is not None:
        query = query.where(AvailabilityEntry.store_id == store_id)

    rows = db.scalars(query.order_by(AvailabilityEntry.date.asc(), AvailabilityEntry.created_at.asc())).all()
    return [AvailabilityRead.model_validate(row) for row in rows]


@router.delete("/{entry_id}", response_model=AvailabilityRead)
def delete_availability(
    entry_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> AvailabilityRead:
    entry = db.scalar(
        select(AvailabilityEntry).where(
            AvailabilityEntry.id == entry_id,
            AvailabilityEntry.tenant_id == membership.tenant_id,
        )
    )
    if entry is None:
        raise ApiError(
            status_code=404,
            code="AVAILABILITY_NOT_FOUND",
            message="Availability entry not found in active tenant",
        )
    if entry.user_id != membership.user_id:
        raise ApiError(
            status_code=403,
            code="AVAILABILITY_DELETE_FORBIDDEN",
            message="You can only delete your own availability entries",
        )

    response = AvailabilityRead.model_validate(entry)
    db.delete(entry)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="delete",
            entity_type="availability_entry",
            entity_id=str(entry.id),
        )
    )
    db.commit()
    return response
