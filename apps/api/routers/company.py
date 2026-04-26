from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_member
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.company import CompanyProfileRead, CompanyProfileUpdate

router = APIRouter()

_REQUIRED_COMPANY_FIELDS = (
    "company_name",
    "owner_name",
    "business_email",
    "phone_number",
    "registered_address",
)


def _get_active_tenant(db: Session, membership: TenantUser) -> Tenant:
    tenant = db.get(Tenant, membership.tenant_id)
    if tenant is None:
        raise ApiError(
            status_code=404,
            code="TENANT_NOT_FOUND",
            message="Active tenant was not found",
        )
    return tenant


def _is_company_profile_complete(tenant: Tenant) -> bool:
    return all(bool((getattr(tenant, field_name) or "").strip()) for field_name in _REQUIRED_COMPANY_FIELDS)


def _to_company_profile_read(tenant: Tenant) -> CompanyProfileRead:
    return CompanyProfileRead.model_validate(
        {
            "tenant_id": tenant.id,
            "company_name": tenant.company_name,
            "owner_name": tenant.owner_name,
            "business_email": tenant.business_email,
            "phone_number": tenant.phone_number,
            "registered_address": tenant.registered_address,
            "company_setup_completed": tenant.company_setup_completed,
            "company_setup_completed_at": tenant.company_setup_completed_at,
        }
    )


@router.get("/profile", response_model=CompanyProfileRead)
def get_company_profile(
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> CompanyProfileRead:
    tenant = _get_active_tenant(db, membership)
    return _to_company_profile_read(tenant)


@router.patch("/profile", response_model=CompanyProfileRead)
def update_company_profile(
    payload: CompanyProfileUpdate,
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> CompanyProfileRead:
    tenant = _get_active_tenant(db, membership)
    updates = payload.model_dump(exclude_unset=True)

    for field_name, value in updates.items():
        setattr(tenant, field_name, value)

    was_complete = tenant.company_setup_completed
    is_complete = _is_company_profile_complete(tenant)
    tenant.company_setup_completed = is_complete

    if is_complete and (not was_complete or tenant.company_setup_completed_at is None):
        tenant.company_setup_completed_at = datetime.now(UTC)
    elif not is_complete:
        tenant.company_setup_completed_at = None

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="company_profile.updated",
            entity_type="tenant/company_profile",
            entity_id=str(tenant.id),
        )
    )
    db.commit()
    db.refresh(tenant)
    return _to_company_profile_read(tenant)
