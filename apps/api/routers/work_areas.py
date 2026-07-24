import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.site_work_area import SiteWorkArea
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.work_area import WorkAreaCreate, WorkAreaPatch, WorkAreaRead

router = APIRouter()


def _get_site_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
) -> Store:
    site = db.scalar(
        select(Store).where(
            Store.id == site_id,
            Store.tenant_id == tenant_id,
        )
    )
    if site is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Site not found in active tenant",
        )
    return site


def _get_work_area_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    work_area_id: uuid.UUID,
) -> SiteWorkArea:
    work_area = db.scalar(
        select(SiteWorkArea)
        .where(
            SiteWorkArea.id == work_area_id,
            SiteWorkArea.tenant_id == tenant_id,
            SiteWorkArea.store_id == site_id,
        )
        .with_for_update()
    )
    if work_area is None:
        raise ApiError(
            status_code=404,
            code="WORK_AREA_NOT_FOUND",
            message="Work area not found in active tenant and site",
        )
    return work_area


def _commit_work_area_mutation(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            status_code=409,
            code="WORK_AREA_LABEL_EXISTS",
            message="An active work area already uses this label",
        ) from exc


def _ensure_unique_active_label(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    label: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    query = select(SiteWorkArea.id).where(
        SiteWorkArea.tenant_id == tenant_id,
        SiteWorkArea.store_id == site_id,
        SiteWorkArea.is_active.is_(True),
        func.lower(SiteWorkArea.label) == label.lower(),
    )
    if exclude_id is not None:
        query = query.where(SiteWorkArea.id != exclude_id)
    if db.scalar(query) is not None:
        raise ApiError(
            status_code=409,
            code="WORK_AREA_LABEL_EXISTS",
            message="An active work area already uses this label",
        )


@router.post("/{site_id}/work-areas", response_model=WorkAreaRead, status_code=201)
def create_work_area(
    site_id: uuid.UUID,
    payload: WorkAreaCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WorkAreaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    _ensure_unique_active_label(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        label=payload.label,
    )
    work_area = SiteWorkArea(
        id=uuid.uuid4(),
        tenant_id=membership.tenant_id,
        store_id=site_id,
        label=payload.label,
        is_active=True,
    )
    db.add(work_area)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create",
            entity_type="site_work_area",
            entity_id=str(work_area.id),
        )
    )
    _commit_work_area_mutation(db)
    db.refresh(work_area)
    return WorkAreaRead.model_validate(work_area)


@router.get("/{site_id}/work-areas", response_model=list[WorkAreaRead])
def list_work_areas(
    site_id: uuid.UUID,
    is_active: bool | None = None,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[WorkAreaRead]:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    query = select(SiteWorkArea).where(
        SiteWorkArea.tenant_id == membership.tenant_id,
        SiteWorkArea.store_id == site_id,
    )
    if is_active is not None:
        query = query.where(SiteWorkArea.is_active == is_active)
    work_areas = db.scalars(
        query.order_by(func.lower(SiteWorkArea.label).asc(), SiteWorkArea.created_at.asc())
    ).all()
    return [WorkAreaRead.model_validate(work_area) for work_area in work_areas]


@router.patch("/{site_id}/work-areas/{work_area_id}", response_model=WorkAreaRead)
def update_work_area(
    site_id: uuid.UUID,
    work_area_id: uuid.UUID,
    payload: WorkAreaPatch,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WorkAreaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    work_area = _get_work_area_or_404(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        work_area_id=work_area_id,
    )
    if work_area.is_active:
        _ensure_unique_active_label(
            db,
            tenant_id=membership.tenant_id,
            site_id=site_id,
            label=payload.label,
            exclude_id=work_area.id,
        )
    work_area.label = payload.label
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="update",
            entity_type="site_work_area",
            entity_id=str(work_area.id),
        )
    )
    _commit_work_area_mutation(db)
    db.refresh(work_area)
    return WorkAreaRead.model_validate(work_area)


@router.delete("/{site_id}/work-areas/{work_area_id}", response_model=WorkAreaRead)
def deactivate_work_area(
    site_id: uuid.UUID,
    work_area_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> WorkAreaRead:
    _get_site_or_404(db, tenant_id=membership.tenant_id, site_id=site_id)
    work_area = _get_work_area_or_404(
        db,
        tenant_id=membership.tenant_id,
        site_id=site_id,
        work_area_id=work_area_id,
    )
    active_reference = db.scalar(
        select(CoverageTemplate.id).where(
            CoverageTemplate.tenant_id == membership.tenant_id,
            CoverageTemplate.store_id == site_id,
            CoverageTemplate.work_area_id == work_area.id,
            CoverageTemplate.is_active.is_(True),
        )
    )
    if active_reference is not None:
        raise ApiError(
            status_code=409,
            code="WORK_AREA_IN_USE",
            message="Active coverage templates still reference this work area",
        )
    work_area.is_active = False
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="deactivate",
            entity_type="site_work_area",
            entity_id=str(work_area.id),
        )
    )
    _commit_work_area_mutation(db)
    db.refresh(work_area)
    return WorkAreaRead.model_validate(work_area)
