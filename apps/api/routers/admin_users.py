from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.core.security import BCRYPT_PASSWORD_TOO_LONG_MESSAGE, get_password_hash
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.admin_users import AdminUserCreate, AdminUserCreateResponse

router = APIRouter()

_ALLOWED_ROLES = {"admin", "member"}


@router.post("/users", response_model=AdminUserCreateResponse, status_code=201)
def create_user_in_tenant(
    payload: AdminUserCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> AdminUserCreateResponse:
    if payload.role not in _ALLOWED_ROLES:
        raise ApiError(
            status_code=400,
            code="TENANT_ROLE_INVALID",
            message="Role must be one of: admin, member",
        )

    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="AUTH_EMAIL_EXISTS",
            message="Email is already registered",
        )

    try:
        hashed_password = get_password_hash(payload.password)
    except ValueError as exc:
        if str(exc) != BCRYPT_PASSWORD_TOO_LONG_MESSAGE:
            raise
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
            details=[
                {
                    "loc": ["body", "password"],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ],
        ) from exc

    user = User(
        email=payload.email,
        hashed_password=hashed_password,
        is_active=True,
        active_tenant_id=membership.tenant_id,
    )
    db.add(user)
    db.flush()

    tenant_membership = TenantUser(
        tenant_id=membership.tenant_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(tenant_membership)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create_in_tenant",
            entity_type="user",
            entity_id=str(user.id),
        )
    )
    db.commit()

    return AdminUserCreateResponse(
        id=user.id,
        email=user.email,
        active_tenant_id=membership.tenant_id,
        role=payload.role,
    )
