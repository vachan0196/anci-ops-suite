import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
from apps.api.models.store_opening_hours import StoreOpeningHours
from apps.api.models.store_settings import StoreSettings
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.store import (
    OpeningHoursBulkUpdate,
    OpeningHoursDay,
    OpeningHoursResponse,
    StoreCreate,
    StoreOut,
    StoreReadinessResponse,
    StoreSettingsResponse,
    StoreSettingsUpdate,
    StoreUpdate,
)

router = APIRouter()


def _get_store_for_tenant(db: Session, *, store_id: uuid.UUID, tenant_id: uuid.UUID) -> Store:
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


def _opening_hours_response(
    *,
    store_id: uuid.UUID,
    opening_hours: list[StoreOpeningHours],
) -> OpeningHoursResponse:
    return OpeningHoursResponse(
        store_id=store_id,
        opening_hours=[
            OpeningHoursDay(
                day_of_week=row.day_of_week,
                open_time=row.open_time,
                close_time=row.close_time,
                is_closed=row.is_closed,
            )
            for row in opening_hours
        ],
    )


def _settings_response(
    *,
    store_id: uuid.UUID,
    settings: StoreSettings | None,
) -> StoreSettingsResponse:
    return StoreSettingsResponse(
        store_id=store_id,
        business_week_start_day=settings.business_week_start_day if settings else 0,
    )


def _validate_manager_membership(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    manager_user_id: uuid.UUID,
) -> None:
    manager_membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == manager_user_id,
        )
    )
    if manager_membership is None:
        raise ApiError(
            status_code=400,
            code="STORE_MANAGER_NOT_TENANT_MEMBER",
            message="Store manager must be a member of the active tenant",
        )


@router.post("", response_model=StoreOut, status_code=201)
def create_store(
    payload: StoreCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StoreOut:
    if payload.manager_user_id is not None:
        _validate_manager_membership(
            db,
            tenant_id=membership.tenant_id,
            manager_user_id=payload.manager_user_id,
        )

    if payload.code is not None:
        existing = db.scalar(
            select(Store).where(
                Store.tenant_id == membership.tenant_id,
                Store.code == payload.code,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="STORE_CODE_EXISTS",
                message="Store code already exists in active tenant",
            )

    store = Store(tenant_id=membership.tenant_id, **payload.model_dump())
    db.add(store)
    db.flush()

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create",
            entity_type="store",
            entity_id=str(store.id),
        )
    )
    db.commit()
    db.refresh(store)
    return StoreOut.model_validate(store)


@router.get("", response_model=list[StoreOut])
def list_stores(
    include_inactive: bool = False,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> list[StoreOut]:
    query = select(Store).where(Store.tenant_id == membership.tenant_id)
    if not include_inactive:
        query = query.where(Store.is_active.is_(True))
    stores = db.scalars(query.order_by(Store.name.asc())).all()
    return [StoreOut.model_validate(store) for store in stores]


@router.get("/{store_id}", response_model=StoreOut)
def get_store(
    store_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> StoreOut:
    store = _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)
    return StoreOut.model_validate(store)


@router.get("/{store_id}/opening-hours", response_model=OpeningHoursResponse)
def get_store_opening_hours(
    store_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> OpeningHoursResponse:
    _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)
    rows = db.scalars(
        select(StoreOpeningHours)
        .where(
            StoreOpeningHours.tenant_id == membership.tenant_id,
            StoreOpeningHours.store_id == store_id,
        )
        .order_by(StoreOpeningHours.day_of_week.asc())
    ).all()
    return _opening_hours_response(store_id=store_id, opening_hours=list(rows))


@router.put("/{store_id}/opening-hours", response_model=OpeningHoursResponse)
def update_store_opening_hours(
    store_id: uuid.UUID,
    payload: OpeningHoursBulkUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> OpeningHoursResponse:
    _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)

    db.execute(
        delete(StoreOpeningHours).where(
            StoreOpeningHours.tenant_id == membership.tenant_id,
            StoreOpeningHours.store_id == store_id,
        )
    )

    now = datetime.now(UTC)
    rows = [
        StoreOpeningHours(
            tenant_id=membership.tenant_id,
            store_id=store_id,
            day_of_week=item.day_of_week,
            open_time=None if item.is_closed else item.open_time,
            close_time=None if item.is_closed else item.close_time,
            is_closed=item.is_closed,
            updated_at=now,
        )
        for item in payload.opening_hours
    ]
    db.add_all(rows)
    db.flush()

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="store_opening_hours_updated",
            entity_type="store",
            entity_id=str(store_id),
        )
    )
    db.commit()

    saved_rows = db.scalars(
        select(StoreOpeningHours)
        .where(
            StoreOpeningHours.tenant_id == membership.tenant_id,
            StoreOpeningHours.store_id == store_id,
        )
        .order_by(StoreOpeningHours.day_of_week.asc())
    ).all()
    return _opening_hours_response(store_id=store_id, opening_hours=list(saved_rows))


@router.get("/{store_id}/settings", response_model=StoreSettingsResponse)
def get_store_settings(
    store_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> StoreSettingsResponse:
    _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)
    settings = db.scalar(
        select(StoreSettings).where(
            StoreSettings.tenant_id == membership.tenant_id,
            StoreSettings.store_id == store_id,
        )
    )
    return _settings_response(store_id=store_id, settings=settings)


@router.patch("/{store_id}/settings", response_model=StoreSettingsResponse)
def update_store_settings(
    store_id: uuid.UUID,
    payload: StoreSettingsUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StoreSettingsResponse:
    _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)
    settings = db.scalar(
        select(StoreSettings).where(
            StoreSettings.tenant_id == membership.tenant_id,
            StoreSettings.store_id == store_id,
        )
    )

    if settings is None:
        settings = StoreSettings(
            tenant_id=membership.tenant_id,
            store_id=store_id,
        )
        db.add(settings)

    updates = payload.model_dump(exclude_unset=True)
    if "business_week_start_day" in updates and updates["business_week_start_day"] is not None:
        settings.business_week_start_day = updates["business_week_start_day"]
    settings.updated_at = datetime.now(UTC)

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="store_settings_updated",
            entity_type="store",
            entity_id=str(store_id),
        )
    )
    db.commit()
    db.refresh(settings)
    return _settings_response(store_id=store_id, settings=settings)


@router.get("/{store_id}/readiness", response_model=StoreReadinessResponse)
def get_store_readiness(
    store_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> StoreReadinessResponse:
    _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)
    open_day_count = db.scalar(
        select(func.count())
        .select_from(StoreOpeningHours)
        .where(
            StoreOpeningHours.tenant_id == membership.tenant_id,
            StoreOpeningHours.store_id == store_id,
            StoreOpeningHours.is_closed.is_(False),
            StoreOpeningHours.open_time.is_not(None),
            StoreOpeningHours.close_time.is_not(None),
        )
    )
    staff_count = db.scalar(
        select(func.count())
        .select_from(StaffProfile)
        .where(
            StaffProfile.tenant_id == membership.tenant_id,
            StaffProfile.store_id == store_id,
            StaffProfile.is_active.is_(True),
        )
    )
    opening_hours_configured = bool(open_day_count)
    staff_configured = bool(staff_count)
    return StoreReadinessResponse(
        store_id=store_id,
        opening_hours_configured=opening_hours_configured,
        staff_configured=staff_configured,
        operational_ready=opening_hours_configured and staff_configured,
    )


@router.patch("/{store_id}", response_model=StoreOut)
def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StoreOut:
    store = _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)

    updates = payload.model_dump(exclude_unset=True)
    if "code" in updates and updates["code"] is not None:
        existing = db.scalar(
            select(Store).where(
                Store.tenant_id == membership.tenant_id,
                Store.code == updates["code"],
                Store.id != store.id,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="STORE_CODE_EXISTS",
                message="Store code already exists in active tenant",
            )

    if "manager_user_id" in updates and updates["manager_user_id"] is not None:
        _validate_manager_membership(
            db,
            tenant_id=membership.tenant_id,
            manager_user_id=updates["manager_user_id"],
        )

    for field_name, value in updates.items():
        setattr(store, field_name, value)

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="update",
            entity_type="store",
            entity_id=str(store.id),
        )
    )
    db.commit()
    db.refresh(store)
    return StoreOut.model_validate(store)


@router.post("/{store_id}/deactivate", response_model=StoreOut)
def deactivate_store(
    store_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StoreOut:
    store = _get_store_for_tenant(db, store_id=store_id, tenant_id=membership.tenant_id)

    store.is_active = False
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="deactivate",
            entity_type="store",
            entity_id=str(store.id),
        )
    )
    db.commit()
    db.refresh(store)
    return StoreOut.model_validate(store)
