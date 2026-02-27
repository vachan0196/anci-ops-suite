from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import get_current_user
from apps.api.core.errors import ApiError
from apps.api.core.rate_limit import limiter
from apps.api.core.security import (
    BCRYPT_PASSWORD_TOO_LONG_MESSAGE,
    create_access_token,
    get_password_hash,
    verify_password,
)
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.auth import RegisterRequest, TokenResponse, UserOut

router = APIRouter()


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
    return UserOut.model_validate(user)


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


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
