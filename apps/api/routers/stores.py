import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.store import StoreCreate, StoreOut, StoreUpdate

router = APIRouter()


@router.post("", response_model=StoreOut, status_code=201)
def create_store(
    payload: StoreCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StoreOut:
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
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == membership.tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )
    return StoreOut.model_validate(store)


@router.patch("/{store_id}", response_model=StoreOut)
def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StoreOut:
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == membership.tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )

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
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == membership.tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )

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
