import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.errors import ApiError
from apps.api.core.security import decode_access_token, decode_access_token_payload
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.admin_user_2fa import AdminUser2FA
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

OWNER_TENANT_ROLE = "owner"
ADMIN_TENANT_ROLE = "admin"
MEMBER_TENANT_ROLE = "member"
ADMIN_TENANT_ROLES = frozenset({OWNER_TENANT_ROLE, ADMIN_TENANT_ROLE})
TENANT_ROLES = frozenset({OWNER_TENANT_ROLE, ADMIN_TENANT_ROLE, MEMBER_TENANT_ROLE})
AUTH_EVENT_SENSITIVE_ACTION_BLOCKED = "auth.sensitive_action.blocked"


def is_admin_tenant_role(role: str) -> bool:
    return role in ADMIN_TENANT_ROLES


@dataclass(frozen=True)
class SensitiveAdminActionContext:
    user: User
    membership: TenantUser
    auth_session: AuthSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _request_ip_address(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _is_totp_active(two_factor: AdminUser2FA | None) -> bool:
    return (
        two_factor is not None
        and two_factor.disabled_at is None
        and two_factor.totp_enrolled_at is not None
        and bool(two_factor.totp_secret_ciphertext)
        and bool(two_factor.totp_secret_nonce)
        and two_factor.totp_secret_key_version is not None
    )


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
        if required_role == ADMIN_TENANT_ROLE:
            allowed_roles = ADMIN_TENANT_ROLES
        else:
            allowed_roles = frozenset({required_role})

        if membership.role not in allowed_roles:
            required_label = " or ".join(sorted(allowed_roles))
            raise ApiError(
                status_code=403,
                code="TENANT_ROLE_REQUIRED",
                message=f"Role '{required_label}' is required",
            )
        return membership

    return _dependency


def get_current_admin_user_and_session(
    *,
    token: str,
    db: Session,
) -> tuple[User, AuthSession]:
    payload = decode_access_token_payload(token)
    subject = payload.get("sub")
    if not isinstance(subject, str) or subject.startswith("employee:"):
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid authentication token",
        )
    session_id_raw = payload.get("sid")
    try:
        user_id = uuid.UUID(subject)
        session_id = uuid.UUID(session_id_raw)
    except (TypeError, ValueError) as exc:
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

    auth_session = db.get(AuthSession, session_id)
    if (
        auth_session is None
        or auth_session.portal != "admin"
        or auth_session.user_id != user.id
        or auth_session.tenant_id != user.active_tenant_id
        or auth_session.is_revoked
        or _as_aware(auth_session.expires_at) <= _now()
    ):
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid authentication token",
        )
    return user, auth_session


def _add_sensitive_action_blocked_event(
    db: Session,
    *,
    request: Request,
    user: User,
    auth_session: AuthSession,
    action: str,
    reason: str,
) -> None:
    db.add(
        AuthSecurityEvent(
            event_type=AUTH_EVENT_SENSITIVE_ACTION_BLOCKED,
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
            auth_session_id=auth_session.id,
            request_id=_request_id(request),
            ip_address=_request_ip_address(request),
            user_agent=request.headers.get("user-agent"),
            metadata_json={"action": action, "reason": reason},
        )
    )


def require_sensitive_admin_action(
    action: str,
    *,
    required_role: str = OWNER_TENANT_ROLE,
):
    def _dependency(
        request: Request,
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db),
    ) -> SensitiveAdminActionContext:
        user, auth_session = get_current_admin_user_and_session(token=token, db=db)
        membership = _get_active_tenant_membership(current_user=user, db=db)
        if membership.role != required_role:
            raise ApiError(
                status_code=403,
                code="TENANT_ROLE_REQUIRED",
                message=f"Role '{required_role}' is required",
            )

        if user.email_verified_at is None:
            _add_sensitive_action_blocked_event(
                db,
                request=request,
                user=user,
                auth_session=auth_session,
                action=action,
                reason="email_verification_required",
            )
            db.commit()
            raise ApiError(
                status_code=403,
                code="AUTH_EMAIL_VERIFICATION_REQUIRED",
                message="Email verification is required for this action",
            )

        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        if not _is_totp_active(two_factor):
            _add_sensitive_action_blocked_event(
                db,
                request=request,
                user=user,
                auth_session=auth_session,
                action=action,
                reason="2fa_enrolment_required",
            )
            db.commit()
            raise ApiError(
                status_code=403,
                code="AUTH_2FA_ENROLMENT_REQUIRED",
                message="Two-factor authentication is required for this action",
            )

        step_up_at = auth_session.last_2fa_step_up_at
        step_up_cutoff = _now() - timedelta(minutes=settings.TWO_FACTOR_STEP_UP_TTL_MINUTES)
        if step_up_at is None or _as_aware(step_up_at) < step_up_cutoff:
            _add_sensitive_action_blocked_event(
                db,
                request=request,
                user=user,
                auth_session=auth_session,
                action=action,
                reason="step_up_required",
            )
            db.commit()
            raise ApiError(
                status_code=403,
                code="AUTH_2FA_STEP_UP_REQUIRED",
                message="Recent two-factor verification is required for this action",
            )

        return SensitiveAdminActionContext(
            user=user,
            membership=membership,
            auth_session=auth_session,
        )

    return _dependency


def get_current_employee_account(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> EmployeeAccount:
    subject = decode_access_token(token)
    if not subject.startswith("employee:"):
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid employee authentication token",
        )

    try:
        employee_account_id = uuid.UUID(subject.removeprefix("employee:"))
    except ValueError as exc:
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid employee authentication token",
        ) from exc

    account = db.get(EmployeeAccount, employee_account_id)
    if account is None:
        raise ApiError(
            status_code=401,
            code="AUTH_EMPLOYEE_NOT_FOUND",
            message="Authenticated employee account not found",
        )
    if not account.is_active:
        raise ApiError(
            status_code=403,
            code="AUTH_EMPLOYEE_INACTIVE",
            message="Employee account is inactive",
        )
    active_profile_id = db.scalar(
        select(StaffProfile.id).where(
            StaffProfile.tenant_id == account.tenant_id,
            StaffProfile.store_id == account.store_id,
            StaffProfile.employee_account_id == account.id,
            StaffProfile.is_active.is_(True),
        )
    )
    if active_profile_id is None:
        raise ApiError(
            status_code=403,
            code="AUTH_EMPLOYEE_INACTIVE",
            message="Employee account is inactive",
        )
    return account
