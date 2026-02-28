import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.errors import ApiError
from apps.api.core.security import decode_access_token
from apps.api.db.deps import get_db
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    subject = decode_access_token(token)
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid authentication token",
        ) from exc

    user = db.get(User, user_id)
    if not user:
        raise ApiError(
            status_code=401,
            code="AUTH_USER_NOT_FOUND",
            message="Authenticated user not found",
        )
    if not user.is_active:
        raise ApiError(
            status_code=403,
            code="AUTH_USER_INACTIVE",
            message="User account is inactive",
        )
    return user


def get_current_tenant_id(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    membership = _get_active_tenant_membership(current_user=current_user, db=db)
    return membership.tenant_id


def _get_active_tenant_membership(current_user: User, db: Session) -> TenantUser:
    tenant_id = current_user.active_tenant_id
    if tenant_id is None:
        raise ApiError(
            status_code=400,
            code="TENANT_CONTEXT_MISSING",
            message="No active tenant selected for user",
        )

    membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == current_user.id,
        )
    )
    if membership is None:
        raise ApiError(
            status_code=403,
            code="TENANT_MEMBERSHIP_INVALID",
            message="User is not a member of the active tenant",
        )
    return membership


def require_tenant_member(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantUser:
    return _get_active_tenant_membership(current_user=current_user, db=db)


def require_tenant_role(required_role: str = "admin"):
    def _dependency(
        membership: TenantUser = Depends(require_tenant_member),
    ) -> TenantUser:
        if membership.role != required_role:
            raise ApiError(
                status_code=403,
                code="TENANT_ROLE_REQUIRED",
                message=f"Role '{required_role}' is required",
            )
        return membership

    return _dependency
