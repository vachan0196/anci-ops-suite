from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import (
    get_current_employee_account,
    oauth2_scheme,
)
from apps.api.core.errors import ApiError
from apps.api.core.rate_limit import limiter
from apps.api.core.security import (
    BCRYPT_PASSWORD_TOO_LONG_MESSAGE,
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.auth import (
    EmployeeAccountSummary,
    EmployeeLoginRequest,
    EmployeeLoginResponse,
    EmployeeMeResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter()


def _to_user_out(db: Session, user: User) -> UserOut:
    active_tenant_role: str | None = None
    if user.active_tenant_id is not None:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == user.active_tenant_id,
                TenantUser.user_id == user.id,
            )
        )
        if membership is not None:
            active_tenant_role = membership.role

    return UserOut.model_validate(
        {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "active_tenant_id": user.active_tenant_id,
            "active_tenant_role": active_tenant_role,
            "created_at": user.created_at,
        }
    )


def _employee_summary(account: EmployeeAccount) -> EmployeeAccountSummary:
    return EmployeeAccountSummary(
        id=account.id,
        display_name=account.display_name,
        tenant_id=account.tenant_id,
        site_id=account.store_id,
    )


def _to_employee_me(account: EmployeeAccount) -> EmployeeMeResponse:
    return EmployeeMeResponse(
        employee_account_id=account.id,
        tenant_id=account.tenant_id,
        site_id=account.store_id,
        display_name=account.display_name,
    )


def _get_employee_account_from_subject(db: Session, subject: str) -> EmployeeAccount:
    try:
        account_id = uuid.UUID(subject.removeprefix("employee:"))
    except (TypeError, ValueError) as exc:
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid employee authentication token",
        ) from exc

    account = db.get(EmployeeAccount, account_id)
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
    return account


def _get_user_from_subject(db: Session, subject: str) -> User:
    try:
        user_id = uuid.UUID(subject)
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
    return user


def _has_active_staff_profile_for_employee(db: Session, account: EmployeeAccount) -> bool:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == account.tenant_id,
            StaffProfile.store_id == account.store_id,
            StaffProfile.employee_account_id == account.id,
            StaffProfile.is_active.is_(True),
        )
    )
    return profile is not None


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> UserOut:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
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
    )
    tenant = Tenant(name=f"{payload.email}'s tenant")
    db.add_all([tenant, user])
    db.flush()

    membership = TenantUser(tenant_id=tenant.id, user_id=user.id, role="admin")
    user.active_tenant_id = tenant.id
    db.add(membership)
    db.commit()
    db.refresh(user)
    return _to_user_out(db, user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == form_data.username))
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_CREDENTIALS",
            message="Invalid email or password",
        )
    if not user.is_active:
        raise ApiError(
            status_code=403,
            code="AUTH_USER_INACTIVE",
            message="User account is inactive",
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut | EmployeeMeResponse)
def me(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserOut | EmployeeMeResponse:
    subject = decode_access_token(token)
    if subject.startswith("employee:"):
        return _to_employee_me(_get_employee_account_from_subject(db, subject))

    return _to_user_out(db, _get_user_from_subject(db, subject))


@router.post("/employee/login", response_model=EmployeeLoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def employee_login(
    request: Request,
    payload: EmployeeLoginRequest,
    db: Session = Depends(get_db),
) -> EmployeeLoginResponse:
    site = db.scalar(
        select(Store).where(
            Store.id == payload.site_id,
            Store.is_active.is_(True),
        )
    )
    normalized_username = payload.username.strip().lower()
    account: EmployeeAccount | None = None
    if site is not None and normalized_username:
        account = db.scalar(
            select(EmployeeAccount).where(
                EmployeeAccount.tenant_id == site.tenant_id,
                EmployeeAccount.store_id == site.id,
                EmployeeAccount.username == normalized_username,
            )
        )

    if (
        site is None
        or account is None
        or not verify_password(payload.password, account.hashed_password)
    ):
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_EMPLOYEE_CREDENTIALS",
            message="Invalid site, username, or password",
        )
    if not account.is_active:
        raise ApiError(
            status_code=403,
            code="AUTH_EMPLOYEE_INACTIVE",
            message="Employee account is inactive",
        )
    if not _has_active_staff_profile_for_employee(db, account):
        raise ApiError(
            status_code=403,
            code="AUTH_EMPLOYEE_INACTIVE",
            message="Employee account is inactive",
        )

    account.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(account)
    return EmployeeLoginResponse(
        access_token=create_access_token(f"employee:{account.id}"),
        employee_account=_employee_summary(account),
    )


@router.get("/employee/me", response_model=EmployeeMeResponse)
def employee_me(
    account: EmployeeAccount = Depends(get_current_employee_account),
) -> EmployeeMeResponse:
    return _to_employee_me(account)
