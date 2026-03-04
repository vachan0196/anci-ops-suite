from datetime import time
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.coverage_template import CoverageTemplateCreate, CoverageTemplateRead, CoverageTemplateUpdate

router = APIRouter()


def _get_store_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
) -> Store:
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


def _validate_time_window(start_time: time, end_time: time) -> None:
    if end_time <= start_time:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="end_time must be after start_time",
        )


@router.post("", response_model=CoverageTemplateRead, status_code=201)
def create_coverage_template(
    payload: CoverageTemplateCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> CoverageTemplateRead:
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=payload.store_id)
    _validate_time_window(payload.start_time, payload.end_time)

    template = CoverageTemplate(
        tenant_id=membership.tenant_id,
        store_id=payload.store_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        required_headcount=payload.required_headcount,
        required_role=payload.required_role,
        is_active=payload.is_active,
    )
    db.add(template)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create",
            entity_type="coverage_template",
            entity_id=str(template.id),
        )
    )
    db.commit()
    db.refresh(template)
    return CoverageTemplateRead.model_validate(template)


@router.get("", response_model=list[CoverageTemplateRead])
def list_coverage_templates(
    store_id: uuid.UUID,
    is_active: bool | None = None,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[CoverageTemplateRead]:
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=store_id)

    query = select(CoverageTemplate).where(
        CoverageTemplate.tenant_id == membership.tenant_id,
        CoverageTemplate.store_id == store_id,
    )
    if is_active is not None:
        query = query.where(CoverageTemplate.is_active == is_active)

    templates = db.scalars(
        query.order_by(
            CoverageTemplate.day_of_week.asc(),
            CoverageTemplate.start_time.asc(),
            CoverageTemplate.created_at.asc(),
        )
    ).all()
    return [CoverageTemplateRead.model_validate(template) for template in templates]


@router.patch("/{id}", response_model=CoverageTemplateRead)
def update_coverage_template(
    id: uuid.UUID,
    payload: CoverageTemplateUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> CoverageTemplateRead:
    template = db.scalar(
        select(CoverageTemplate).where(
            CoverageTemplate.id == id,
            CoverageTemplate.tenant_id == membership.tenant_id,
        )
    )
    if template is None:
        raise ApiError(
            status_code=404,
            code="COVERAGE_TEMPLATE_NOT_FOUND",
            message="Coverage template not found in active tenant",
        )

    updates = payload.model_dump(exclude_unset=True)
    start_time = updates.get("start_time", template.start_time)
    end_time = updates.get("end_time", template.end_time)
    _validate_time_window(start_time, end_time)

    for field_name, value in updates.items():
        setattr(template, field_name, value)

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="update",
            entity_type="coverage_template",
            entity_id=str(template.id),
        )
    )
    db.commit()
    db.refresh(template)
    return CoverageTemplateRead.model_validate(template)


@router.delete("/{id}", response_model=CoverageTemplateRead)
def delete_coverage_template(
    id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> CoverageTemplateRead:
    template = db.scalar(
        select(CoverageTemplate).where(
            CoverageTemplate.id == id,
            CoverageTemplate.tenant_id == membership.tenant_id,
        )
    )
    if template is None:
        raise ApiError(
            status_code=404,
            code="COVERAGE_TEMPLATE_NOT_FOUND",
            message="Coverage template not found in active tenant",
        )

    response = CoverageTemplateRead.model_validate(template)
    db.delete(template)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="delete",
            entity_type="coverage_template",
            entity_id=str(template.id),
        )
    )
    db.commit()
    return response
