from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
import pyotp
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from apps.api.core.deps import (
    ADMIN_TENANT_ROLES,
    get_current_admin_user_and_session,
    get_current_employee_account,
    oauth2_scheme,
)
from apps.api.core.errors import ApiError
from apps.api.core.rate_limit import limiter
from apps.api.core.security import (
    BCRYPT_PASSWORD_TOO_LONG_MESSAGE,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.auth_token import AuthToken
from apps.api.models.auth_2fa_challenge import Auth2FAChallenge
from apps.api.models.admin_user_2fa import AdminUser2FA
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
    EmailVerificationConfirmRequest,
    EmailVerificationConfirmResponse,
    EmailVerificationRequestResponse,
    LogoutRequest,
    LogoutResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    TokenResponse,
    TwoFactorDisableRequest,
    TwoFactorDisableResponse,
    TwoFactorEnrolBeginResponse,
    TwoFactorEnrolConfirmRequest,
    TwoFactorEnrolConfirmResponse,
    TwoFactorRecoveryCodesRegenerateRequest,
    TwoFactorRecoveryCodesRegenerateResponse,
    TwoFactorStatusResponse,
    TwoFactorStepUpRequest,
    TwoFactorStepUpResponse,
    TwoFactorVerifyRequest,
    UserOut,
)
from apps.api.services.email import get_email_service
from apps.api.services.totp_crypto import decrypt_totp_secret, encrypt_totp_secret

router = APIRouter()

REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"
CSRF_REQUEST_HEADER = "x-requested-with"
CSRF_REQUEST_HEADER_VALUE = "ForecourtOS"
AUTH_EVENT_ISSUED = "auth.session.issued"
AUTH_EVENT_ROTATED = "auth.session.rotated"
AUTH_EVENT_REVOKED = "auth.session.revoked"
AUTH_EVENT_REJECTED = "auth.session.rejected"
AUTH_EVENT_BLOCKED_DISABLED_ADMIN = "auth.session.blocked_disabled_admin"
AUTH_EVENT_BLOCKED_DISABLED_EMPLOYEE = "auth.session.blocked_disabled_employee"
AUTH_EVENT_BLOCKED_INACTIVE_STAFF_PROFILE = "auth.session.blocked_inactive_staff_profile"
AUTH_EVENT_REUSE_DETECTED = "auth.session.reuse_detected"
AUTH_EVENT_REVOKED_BY_FAMILY_REUSE = "auth.session.revoked_by_family_reuse"
AUTH_EVENT_PASSWORD_RESET_REQUESTED = "auth.password_reset.requested"
AUTH_EVENT_PASSWORD_RESET_COMPLETED = "auth.password_reset.completed"
AUTH_EVENT_PASSWORD_RESET_TOKEN_REJECTED = "auth.password_reset.token_rejected"
AUTH_EVENT_PASSWORD_RESET_SESSION_REVOKED = "auth.password_reset.session_revoked"
AUTH_EVENT_EMAIL_VERIFICATION_REQUESTED = "auth.email_verification.requested"
AUTH_EVENT_EMAIL_VERIFICATION_COMPLETED = "auth.email_verification.completed"
AUTH_EVENT_EMAIL_VERIFICATION_TOKEN_REJECTED = "auth.email_verification.token_rejected"
AUTH_EVENT_EMAIL_VERIFICATION_ALREADY_VERIFIED = "auth.email_verification.already_verified"
AUTH_EVENT_2FA_ENROLMENT_STARTED = "auth.2fa.enrolment_started"
AUTH_EVENT_2FA_ENROLMENT_COMPLETED = "auth.2fa.enrolment_completed"
AUTH_EVENT_2FA_VERIFICATION_SUCCEEDED = "auth.2fa.verification_succeeded"
AUTH_EVENT_2FA_VERIFICATION_FAILED = "auth.2fa.verification_failed"
AUTH_EVENT_2FA_RECOVERY_CODE_USED = "auth.2fa.recovery_code_used"
AUTH_EVENT_2FA_DISABLED = "auth.2fa.disabled"
AUTH_EVENT_2FA_RECOVERY_CODES_REGENERATED = "auth.2fa.recovery_codes_regenerated"
AUTH_EVENT_2FA_STEP_UP_SUCCEEDED = "auth.2fa.step_up_succeeded"
AUTH_EVENT_2FA_STEP_UP_FAILED = "auth.2fa.step_up_failed"
ADMIN_PORTAL_ROLE_REQUIRED_CODE = "AUTH_ADMIN_PORTAL_ROLE_REQUIRED"
ADMIN_PORTAL_ROLE_REQUIRED_MESSAGE = "Admin portal access requires owner or admin role"
PASSWORD_RESET_TOKEN_TYPE = "password_reset"
EMAIL_VERIFICATION_TOKEN_TYPE = "email_verification"
RECOVERY_CODE_TOKEN_TYPE = "recovery_code"
PASSWORD_RESET_EXPIRY_HOURS = 1
EMAIL_VERIFICATION_EXPIRY_HOURS = 24
TWO_FACTOR_CHALLENGE_EXPIRY_MINUTES = 5
TWO_FACTOR_PENDING_EXPIRY_MINUTES = 10
TWO_FACTOR_MAX_FAILED_ATTEMPTS = 5
TOTP_INTERVAL_SECONDS = 30
TOTP_RECOVERY_CODE_COUNT = 10
PASSWORD_RESET_GENERIC_MESSAGE = "If an account exists for that email, instructions have been sent."
EMAIL_VERIFICATION_GENERIC_MESSAGE = "If email verification is required, instructions have been sent."
EMAIL_VERIFICATION_ALREADY_VERIFIED_MESSAGE = "Your email is already verified."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_ip_address(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _create_raw_auth_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_auth_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _is_totp_active(two_factor: AdminUser2FA | None) -> bool:
    return (
        two_factor is not None
        and two_factor.disabled_at is None
        and two_factor.totp_enrolled_at is not None
        and bool(two_factor.totp_secret_ciphertext)
        and bool(two_factor.totp_secret_nonce)
        and two_factor.totp_secret_key_version is not None
    )


def _load_or_create_admin_2fa(db: Session, user: User) -> AdminUser2FA:
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
    if two_factor is None:
        two_factor = AdminUser2FA(user_id=user.id)
        db.add(two_factor)
        db.flush()
    return two_factor


def _totp_time_step(value: datetime) -> int:
    return int(value.timestamp()) // TOTP_INTERVAL_SECONDS


def _accepted_totp_time_step(secret: str, code: str, at_time: datetime) -> int | None:
    normalized_code = code.strip()
    if len(normalized_code) != 6 or not normalized_code.isdigit():
        return None
    totp = pyotp.TOTP(secret, digits=6, interval=TOTP_INTERVAL_SECONDS)
    current_step = _totp_time_step(at_time)
    for candidate_step in (current_step - 1, current_step, current_step + 1):
        if totp.verify(
            normalized_code,
            for_time=candidate_step * TOTP_INTERVAL_SECONDS,
            valid_window=0,
        ):
            return candidate_step
    return None


def _generate_recovery_code() -> str:
    return secrets.token_urlsafe(24)


def _create_recovery_codes(
    db: Session,
    *,
    request: Request,
    user: User,
    count: int = TOTP_RECOVERY_CODE_COUNT,
) -> list[str]:
    raw_codes = [_generate_recovery_code() for _ in range(count)]
    for raw_code in raw_codes:
        db.add(
            AuthToken(
                token_type=RECOVERY_CODE_TOKEN_TYPE,
                user_id=user.id,
                token_hash=_hash_auth_token(raw_code),
                expires_at=None,
                created_ip=_request_ip_address(request),
                created_user_agent=request.headers.get("user-agent"),
                request_id=_request_id(request),
            )
        )
    return raw_codes


def _consume_recovery_code(
    db: Session,
    *,
    request: Request,
    user: User,
    recovery_code: str,
    now: datetime,
) -> bool:
    consumed_code = db.execute(
        update(AuthToken)
        .where(
            AuthToken.token_hash == _hash_auth_token(recovery_code),
            AuthToken.token_type == RECOVERY_CODE_TOKEN_TYPE,
            AuthToken.user_id == user.id,
            AuthToken.used_at.is_(None),
        )
        .values(
            used_at=now,
            consumed_ip=_request_ip_address(request),
            consumed_user_agent=request.headers.get("user-agent"),
        )
        .returning(AuthToken.id)
    ).first()
    return consumed_code is not None


def _invalidate_unused_recovery_codes(
    db: Session,
    *,
    request: Request,
    user: User,
    now: datetime,
) -> int:
    invalidated = db.execute(
        update(AuthToken)
        .where(
            AuthToken.token_type == RECOVERY_CODE_TOKEN_TYPE,
            AuthToken.user_id == user.id,
            AuthToken.used_at.is_(None),
        )
        .values(
            used_at=now,
            consumed_ip=_request_ip_address(request),
            consumed_user_agent=request.headers.get("user-agent"),
        )
        .returning(AuthToken.id)
    ).all()
    return len(invalidated)


def _create_2fa_challenge(
    db: Session,
    *,
    request: Request,
    user: User,
) -> str:
    raw_challenge = _create_raw_auth_token()
    db.add(
        Auth2FAChallenge(
            user_id=user.id,
            tenant_id=user.active_tenant_id,
            challenge_hash=_hash_auth_token(raw_challenge),
            expires_at=_now() + timedelta(minutes=TWO_FACTOR_CHALLENGE_EXPIRY_MINUTES),
            ip_address_hash=_hash_ip_address(_request_ip_address(request)),
            user_agent=request.headers.get("user-agent"),
            request_id=_request_id(request),
        )
    )
    return raw_challenge


def _build_password_reset_url(raw_token: str) -> str:
    base_url = settings.APP_BASE_URL.rstrip("/")
    return f"{base_url}/admin/reset-password?token={quote(raw_token)}"


def _build_email_verification_url(raw_token: str) -> str:
    base_url = settings.APP_BASE_URL.rstrip("/")
    return f"{base_url}/admin/verify-email?token={quote(raw_token)}"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=settings.ENV.lower() not in {"dev", "test", "local"},
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.ENV.lower() not in {"dev", "test", "local"},
        httponly=True,
        samesite="strict",
    )


def _create_auth_session(
    db: Session,
    *,
    request: Request,
    portal: str,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None = None,
    employee_account_id: uuid.UUID | None = None,
    session_family_id: uuid.UUID | None = None,
    parent_session_id: uuid.UUID | None = None,
    create_root_family: bool = False,
) -> tuple[AuthSession, str]:
    if session_family_id is None:
        if create_root_family:
            session_family_id = uuid.uuid4()
        else:
            raise ValueError("auth session creation requires a session_family_id")

    refresh_token = create_refresh_token()
    session = AuthSession(
        tenant_id=tenant_id,
        user_id=user_id,
        employee_account_id=employee_account_id,
        session_family_id=session_family_id,
        parent_session_id=parent_session_id,
        portal=portal,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("user-agent"),
        ip_address_hash=_hash_ip_address(request.client.host if request.client else None),
    )
    db.add(session)
    return session, refresh_token


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _request_ip_address(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _add_auth_security_event(
    db: Session,
    *,
    request: Request,
    event_type: str,
    rejection_reason: str | None = None,
    portal: str | None = None,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    employee_account_id: uuid.UUID | None = None,
    auth_session_id: uuid.UUID | None = None,
    metadata_json: dict | None = None,
) -> None:
    db.add(
        AuthSecurityEvent(
            event_type=event_type,
            rejection_reason=rejection_reason,
            portal=portal,
            tenant_id=tenant_id,
            user_id=user_id,
            employee_account_id=employee_account_id,
            auth_session_id=auth_session_id,
            request_id=_request_id(request),
            ip_address=_request_ip_address(request),
            user_agent=request.headers.get("user-agent"),
            metadata_json=metadata_json,
        )
    )


def _event_context_from_session(session: AuthSession | None) -> dict:
    if session is None:
        return {}
    return {
        "portal": session.portal,
        "tenant_id": session.tenant_id,
        "user_id": session.user_id,
        "employee_account_id": session.employee_account_id,
        "auth_session_id": session.id,
    }


def _get_refresh_token_from_request(request: Request, payload_token: str | None) -> str | None:
    return payload_token or request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)


def _find_refresh_session(
    db: Session,
    refresh_token: str,
    *,
    lock_for_update: bool = False,
) -> AuthSession | None:
    statement = select(AuthSession).where(AuthSession.token_hash == hash_refresh_token(refresh_token))
    if lock_for_update:
        statement = statement.with_for_update(nowait=True)
    return db.scalar(statement)


def _require_csrf_header_for_cookie_refresh(
    db: Session,
    request: Request,
    payload_token: str | None,
) -> None:
    if payload_token is not None:
        return
    if settings.AUTH_REFRESH_COOKIE_NAME not in request.cookies:
        return
    if request.headers.get(CSRF_REQUEST_HEADER) == CSRF_REQUEST_HEADER_VALUE:
        return
    session = _find_refresh_session(db, request.cookies[settings.AUTH_REFRESH_COOKIE_NAME])
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_REJECTED,
        rejection_reason="missing_csrf_header",
        metadata_json={"cookie_backed": True},
        **_event_context_from_session(session),
    )
    db.commit()
    raise ApiError(
        status_code=403,
        code="AUTH_CSRF_REQUIRED",
        message="CSRF protection header is required",
    )


def _load_refresh_session(
    db: Session,
    *,
    request: Request,
    refresh_token: str,
    expected_portal: str | None = None,
) -> AuthSession:
    try:
        session = _find_refresh_session(db, refresh_token, lock_for_update=True)
    except OperationalError:
        db.rollback()
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            portal=expected_portal,
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        ) from None

    rejection_reason: str | None = None
    if session is None:
        rejection_reason = "invalid"
    elif _as_aware(session.expires_at) <= _now():
        rejection_reason = "expired"
    elif expected_portal is not None and session.portal != expected_portal:
        rejection_reason = "wrong_portal"
    elif session.is_revoked and _family_was_revoked_for_reuse(db, session):
        rejection_reason = "family_revoked"
    elif session.is_revoked and _should_trigger_reuse_detection(db, session):
        _revoke_session_family_for_reuse(db, request=request, reused_session=session)
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        )
    elif session.is_revoked:
        rejection_reason = "revoked"

    if rejection_reason is not None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason=rejection_reason,
            **_event_context_from_session(session),
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        )
    return session


def _revoke_session(session: AuthSession) -> None:
    session.is_revoked = True
    session.revoked_at = _now()


def _revoke_active_admin_sessions_for_password_reset(
    db: Session,
    *,
    request: Request,
    user: User,
) -> int:
    sessions = list(
        db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.is_revoked.is_(False),
            )
            .with_for_update()
        ).all()
    )
    for session in sessions:
        _revoke_session(session)
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_PASSWORD_RESET_SESSION_REVOKED,
            portal="admin",
            tenant_id=session.tenant_id,
            user_id=user.id,
            auth_session_id=session.id,
        )
    return len(sessions)


def _classify_auth_token_rejection(db: Session, token_hash: str, expected_token_type: str) -> str:
    token = db.scalar(select(AuthToken).where(AuthToken.token_hash == token_hash))
    if token is None:
        return "invalid"
    if token.token_type != expected_token_type:
        return "wrong_type"
    if token.used_at is not None:
        return "used"
    if token.expires_at is not None and _as_aware(token.expires_at) <= _now():
        return "expired"
    return "invalid"


def _raise_password_reset_token_rejected(
    db: Session,
    *,
    request: Request,
    token_hash: str,
) -> None:
    rejection_reason = _classify_auth_token_rejection(db, token_hash, PASSWORD_RESET_TOKEN_TYPE)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_PASSWORD_RESET_TOKEN_REJECTED,
        rejection_reason=rejection_reason,
        portal="admin",
    )
    db.commit()
    raise ApiError(
        status_code=400,
        code="AUTH_PASSWORD_RESET_INVALID",
        message="Invalid password reset token",
    )


def _raise_email_verification_token_rejected(
    db: Session,
    *,
    request: Request,
    token_hash: str,
) -> None:
    rejection_reason = _classify_auth_token_rejection(db, token_hash, EMAIL_VERIFICATION_TOKEN_TYPE)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_EMAIL_VERIFICATION_TOKEN_REJECTED,
        rejection_reason=rejection_reason,
        portal="admin",
    )
    db.commit()
    raise ApiError(
        status_code=400,
        code="AUTH_EMAIL_VERIFICATION_INVALID",
        message="Invalid email verification token",
    )


def _should_trigger_reuse_detection(db: Session, session: AuthSession) -> bool:
    if session.session_family_id is None:
        return False
    child_id = db.scalar(
        select(AuthSession.id)
        .where(AuthSession.parent_session_id == session.id)
        .limit(1)
    )
    return child_id is not None


def _family_was_revoked_for_reuse(db: Session, session: AuthSession) -> bool:
    if session.session_family_id is None:
        return False
    detected_session_id = db.scalar(
        select(AuthSession.id)
        .where(
            AuthSession.session_family_id == session.session_family_id,
            AuthSession.reuse_detected_at.is_not(None),
        )
        .limit(1)
    )
    return detected_session_id is not None


def _revoke_session_family_for_reuse(
    db: Session,
    *,
    request: Request,
    reused_session: AuthSession,
) -> None:
    if reused_session.session_family_id is None:
        return

    if reused_session.reuse_detected_at is None:
        reused_session.reuse_detected_at = _now()

    family_members = list(
        db.scalars(
            select(AuthSession)
            .where(AuthSession.session_family_id == reused_session.session_family_id)
            .with_for_update()
        ).all()
    )
    for family_member in family_members:
        if not family_member.is_revoked:
            _revoke_session(family_member)

    family_metadata = {
        "family_id": str(reused_session.session_family_id),
        "revoked_count": len(family_members),
    }
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_REUSE_DETECTED,
        metadata_json=family_metadata,
        **_event_context_from_session(reused_session),
    )
    for family_member in family_members:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REVOKED_BY_FAMILY_REUSE,
            metadata_json={"family_id": str(reused_session.session_family_id)},
            **_event_context_from_session(family_member),
        )


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
    if not _has_active_staff_profile_for_employee(db, account):
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


def _require_admin_portal_role(db: Session, user: User) -> TenantUser:
    if user.active_tenant_id is None:
        raise ApiError(
            status_code=403,
            code=ADMIN_PORTAL_ROLE_REQUIRED_CODE,
            message=ADMIN_PORTAL_ROLE_REQUIRED_MESSAGE,
        )
    membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == user.active_tenant_id,
            TenantUser.user_id == user.id,
        )
    )
    if membership is None or membership.role not in ADMIN_TENANT_ROLES:
        raise ApiError(
            status_code=403,
            code=ADMIN_PORTAL_ROLE_REQUIRED_CODE,
            message=ADMIN_PORTAL_ROLE_REQUIRED_MESSAGE,
        )
    return membership


def _get_current_admin_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_from_subject(db, decode_access_token(token))
    _require_admin_portal_role(db, user)
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


def _load_active_employee_account_for_refresh(
    db: Session,
    *,
    request: Request,
    session: AuthSession,
) -> EmployeeAccount:
    if session.employee_account_id is None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            **_event_context_from_session(session),
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        )

    account = db.get(EmployeeAccount, session.employee_account_id)
    if account is None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            **_event_context_from_session(session),
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_EMPLOYEE_NOT_FOUND",
            message="Authenticated employee account not found",
        )
    if not account.is_active:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_BLOCKED_DISABLED_EMPLOYEE,
            portal="employee",
            tenant_id=account.tenant_id,
            employee_account_id=account.id,
            auth_session_id=session.id,
        )
        db.commit()
        raise ApiError(
            status_code=403,
            code="AUTH_EMPLOYEE_INACTIVE",
            message="Employee account is inactive",
        )
    if not _has_active_staff_profile_for_employee(db, account):
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_BLOCKED_INACTIVE_STAFF_PROFILE,
            portal="employee",
            tenant_id=account.tenant_id,
            employee_account_id=account.id,
            auth_session_id=session.id,
        )
        db.commit()
        raise ApiError(
            status_code=403,
            code="AUTH_EMPLOYEE_INACTIVE",
            message="Employee account is inactive",
        )
    return account


def _load_active_admin_user_for_refresh(
    db: Session,
    *,
    request: Request,
    session: AuthSession,
) -> User:
    if session.user_id is None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            **_event_context_from_session(session),
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        )

    user = db.get(User, session.user_id)
    if not user:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            **_event_context_from_session(session),
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_USER_NOT_FOUND",
            message="Authenticated user not found",
        )
    if not user.is_active:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_BLOCKED_DISABLED_ADMIN,
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
            auth_session_id=session.id,
        )
        db.commit()
        raise ApiError(
            status_code=403,
            code="AUTH_USER_INACTIVE",
            message="User account is inactive",
        )
    try:
        _require_admin_portal_role(db, user)
    except ApiError:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            **_event_context_from_session(session),
        )
        db.commit()
        raise
    return user


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

    membership = TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner")
    user.active_tenant_id = tenant.id
    db.add(membership)
    db.commit()
    db.refresh(user)
    return _to_user_out(db, user)


@router.post("/login", response_model=TokenResponse, response_model_exclude_none=True)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    response: Response,
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
    _require_admin_portal_role(db, user)
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
    if _is_totp_active(two_factor):
        raw_challenge = _create_2fa_challenge(db, request=request, user=user)
        db.commit()
        return TokenResponse(
            token_type="2fa_pending",
            requires_2fa=True,
            two_factor_challenge_token=raw_challenge,
        )

    session, refresh_token = _create_auth_session(
        db,
        request=request,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        create_root_family=True,
    )
    db.flush()
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_ISSUED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        auth_session_id=session.id,
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=create_access_token(str(user.id), auth_session_id=str(session.id)),
        refresh_token=refresh_token,
    )


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
def get_2fa_status(
    user: User = Depends(_get_current_admin_user),
    db: Session = Depends(get_db),
) -> TwoFactorStatusResponse:
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
    now = _now()
    pending_enrolment = (
        two_factor is not None
        and two_factor.pending_secret_ciphertext is not None
        and two_factor.pending_secret_nonce is not None
        and two_factor.pending_expires_at is not None
        and _as_aware(two_factor.pending_expires_at) > now
    )
    recovery_codes_remaining = db.scalar(
        select(func.count(AuthToken.id)).where(
            AuthToken.user_id == user.id,
            AuthToken.token_type == RECOVERY_CODE_TOKEN_TYPE,
            AuthToken.used_at.is_(None),
        )
    )
    return TwoFactorStatusResponse(
        totp_enrolled=_is_totp_active(two_factor),
        totp_enrolled_at=two_factor.totp_enrolled_at if two_factor else None,
        pending_enrolment=pending_enrolment,
        pending_expires_at=two_factor.pending_expires_at if pending_enrolment else None,
        recovery_codes_remaining=int(recovery_codes_remaining or 0),
    )


@router.post("/2fa/totp/enrol/begin", response_model=TwoFactorEnrolBeginResponse)
def begin_totp_enrolment(
    request: Request,
    user: User = Depends(_get_current_admin_user),
    db: Session = Depends(get_db),
) -> TwoFactorEnrolBeginResponse:
    two_factor = _load_or_create_admin_2fa(db, user)
    if _is_totp_active(two_factor):
        raise ApiError(
            status_code=409,
            code="AUTH_2FA_ALREADY_ENABLED",
            message="Two-factor authentication is already enabled",
        )

    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)
    now = _now()
    expires_at = now + timedelta(minutes=TWO_FACTOR_PENDING_EXPIRY_MINUTES)
    two_factor.pending_secret_ciphertext = encrypted_secret.ciphertext
    two_factor.pending_secret_nonce = encrypted_secret.nonce
    two_factor.pending_secret_key_version = encrypted_secret.key_version
    two_factor.pending_started_at = now
    two_factor.pending_expires_at = expires_at
    two_factor.updated_at = now

    otpauth_url = pyotp.TOTP(secret, digits=6, interval=TOTP_INTERVAL_SECONDS).provisioning_uri(
        name=user.email,
        issuer_name="Anci Ops Suite",
    )
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_ENROLMENT_STARTED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"pending_expires_in_minutes": TWO_FACTOR_PENDING_EXPIRY_MINUTES},
    )
    db.commit()
    return TwoFactorEnrolBeginResponse(
        status="pending",
        otpauth_url=otpauth_url,
        manual_secret=secret,
        expires_at=expires_at,
    )


@router.post("/2fa/totp/enrol/confirm", response_model=TwoFactorEnrolConfirmResponse)
def confirm_totp_enrolment(
    payload: TwoFactorEnrolConfirmRequest,
    request: Request,
    user: User = Depends(_get_current_admin_user),
    db: Session = Depends(get_db),
) -> TwoFactorEnrolConfirmResponse:
    now = _now()
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
    if (
        two_factor is None
        or two_factor.pending_secret_ciphertext is None
        or two_factor.pending_secret_nonce is None
        or two_factor.pending_secret_key_version is None
        or two_factor.pending_expires_at is None
        or _as_aware(two_factor.pending_expires_at) <= now
    ):
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_2FA_VERIFICATION_FAILED,
            rejection_reason="challenge_expired",
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
        )
        db.commit()
        raise ApiError(
            status_code=400,
            code="AUTH_2FA_ENROLMENT_INVALID",
            message="Invalid or expired 2FA enrolment",
        )

    pending_secret = decrypt_totp_secret(
        ciphertext=two_factor.pending_secret_ciphertext,
        nonce=two_factor.pending_secret_nonce,
        key_version=two_factor.pending_secret_key_version,
    )
    accepted_step = _accepted_totp_time_step(pending_secret, payload.code, now)
    if accepted_step is None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_2FA_VERIFICATION_FAILED,
            rejection_reason="invalid_code",
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
        )
        db.commit()
        raise ApiError(
            status_code=400,
            code="AUTH_2FA_INVALID_CODE",
            message="Invalid 2FA code",
        )

    two_factor.totp_secret_ciphertext = two_factor.pending_secret_ciphertext
    two_factor.totp_secret_nonce = two_factor.pending_secret_nonce
    two_factor.totp_secret_key_version = two_factor.pending_secret_key_version
    two_factor.totp_enrolled_at = now
    two_factor.totp_last_used_time_step = None
    two_factor.disabled_at = None
    two_factor.pending_secret_ciphertext = None
    two_factor.pending_secret_nonce = None
    two_factor.pending_secret_key_version = None
    two_factor.pending_started_at = None
    two_factor.pending_expires_at = None
    two_factor.updated_at = now
    recovery_codes = _create_recovery_codes(db, request=request, user=user)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_ENROLMENT_COMPLETED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"codes_issued_count": len(recovery_codes)},
    )
    db.commit()
    return TwoFactorEnrolConfirmResponse(status="enabled", recovery_codes=recovery_codes)


def _raise_2fa_verify_rejected(
    db: Session,
    *,
    request: Request,
    challenge: Auth2FAChallenge | None,
    user: User | None,
    rejection_reason: str,
    status_code: int = 400,
) -> None:
    if challenge is not None and rejection_reason in {"invalid_code", "code_reused"}:
        challenge.failed_attempts += 1
        if challenge.failed_attempts >= TWO_FACTOR_MAX_FAILED_ATTEMPTS:
            challenge.locked_at = _now()
            rejection_reason = "rate_limited"
            status_code = 429

    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_VERIFICATION_FAILED,
        rejection_reason=rejection_reason,
        portal="admin",
        tenant_id=challenge.tenant_id if challenge is not None else None,
        user_id=user.id if user is not None else None,
    )
    db.commit()
    raise ApiError(
        status_code=status_code,
        code="AUTH_2FA_INVALID",
        message="Invalid or expired 2FA challenge",
    )


def _raise_2fa_not_enabled() -> None:
    raise ApiError(
        status_code=409,
        code="AUTH_2FA_NOT_ENABLED",
        message="Two-factor authentication is not enabled",
    )


def _raise_2fa_action_verification_failed(
    db: Session,
    *,
    request: Request,
    user: User,
    rejection_reason: str = "invalid_code",
    event_type: str = AUTH_EVENT_2FA_VERIFICATION_FAILED,
    auth_session_id: uuid.UUID | None = None,
) -> None:
    _add_auth_security_event(
        db,
        request=request,
        event_type=event_type,
        rejection_reason=rejection_reason,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        auth_session_id=auth_session_id,
    )
    db.commit()
    raise ApiError(
        status_code=400,
        code="AUTH_2FA_VERIFICATION_FAILED",
        message="2FA verification failed",
    )


def _verify_2fa_action_factor(
    db: Session,
    *,
    request: Request,
    user: User,
    two_factor: AdminUser2FA,
    code: str | None,
    recovery_code: str | None,
    now: datetime,
    failure_event_type: str = AUTH_EVENT_2FA_VERIFICATION_FAILED,
    failure_auth_session_id: uuid.UUID | None = None,
) -> bool:
    if code is not None:
        active_secret = decrypt_totp_secret(
            ciphertext=two_factor.totp_secret_ciphertext,
            nonce=two_factor.totp_secret_nonce,
            key_version=two_factor.totp_secret_key_version,
        )
        accepted_step = _accepted_totp_time_step(active_secret, code, now)
        if accepted_step is None:
            _raise_2fa_action_verification_failed(
                db,
                request=request,
                user=user,
                rejection_reason="invalid_code",
                event_type=failure_event_type,
                auth_session_id=failure_auth_session_id,
            )
        if (
            two_factor.totp_last_used_time_step is not None
            and accepted_step <= two_factor.totp_last_used_time_step
        ):
            _raise_2fa_action_verification_failed(
                db,
                request=request,
                user=user,
                rejection_reason="code_reused",
                event_type=failure_event_type,
                auth_session_id=failure_auth_session_id,
            )
        two_factor.totp_last_used_time_step = accepted_step
        two_factor.updated_at = now
        return False

    if recovery_code is None or not _consume_recovery_code(
        db,
        request=request,
        user=user,
        recovery_code=recovery_code,
        now=now,
    ):
        _raise_2fa_action_verification_failed(
            db,
            request=request,
            user=user,
            rejection_reason="invalid_code",
            event_type=failure_event_type,
            auth_session_id=failure_auth_session_id,
        )
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_RECOVERY_CODE_USED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
    )
    return True


@router.post("/2fa/verify", response_model=TokenResponse, response_model_exclude_none=True)
@limiter.limit(settings.RATE_LIMIT_2FA_VERIFY)
def verify_2fa_challenge(
    payload: TwoFactorVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    has_totp_code = payload.code is not None
    has_recovery_code = payload.recovery_code is not None
    if has_totp_code == has_recovery_code:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Provide exactly one 2FA code or recovery code",
        )

    now = _now()
    challenge_hash = _hash_auth_token(payload.two_factor_challenge_token)
    challenge = db.scalar(
        select(Auth2FAChallenge)
        .where(Auth2FAChallenge.challenge_hash == challenge_hash)
        .with_for_update()
    )
    if challenge is None:
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=None,
            user=None,
            rejection_reason="challenge_invalid",
        )
    user = db.get(User, challenge.user_id)
    if user is None or not user.is_active:
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=challenge,
            user=user,
            rejection_reason="challenge_invalid",
        )
    try:
        _require_admin_portal_role(db, user)
    except ApiError:
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=challenge,
            user=user,
            rejection_reason="challenge_invalid",
        )
    if challenge.used_at is not None:
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=challenge,
            user=user,
            rejection_reason="challenge_invalid",
        )
    if challenge.locked_at is not None:
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=challenge,
            user=user,
            rejection_reason="rate_limited",
            status_code=429,
        )
    if _as_aware(challenge.expires_at) <= now:
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=challenge,
            user=user,
            rejection_reason="challenge_expired",
        )

    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id).with_for_update())
    if not _is_totp_active(two_factor):
        _raise_2fa_verify_rejected(
            db,
            request=request,
            challenge=challenge,
            user=user,
            rejection_reason="challenge_invalid",
        )

    if has_totp_code:
        active_secret = decrypt_totp_secret(
            ciphertext=two_factor.totp_secret_ciphertext,
            nonce=two_factor.totp_secret_nonce,
            key_version=two_factor.totp_secret_key_version,
        )
        accepted_step = _accepted_totp_time_step(active_secret, payload.code or "", now)
        if accepted_step is None:
            _raise_2fa_verify_rejected(
                db,
                request=request,
                challenge=challenge,
                user=user,
                rejection_reason="invalid_code",
            )
        if (
            two_factor.totp_last_used_time_step is not None
            and accepted_step <= two_factor.totp_last_used_time_step
        ):
            _raise_2fa_verify_rejected(
                db,
                request=request,
                challenge=challenge,
                user=user,
                rejection_reason="code_reused",
            )
        two_factor.totp_last_used_time_step = accepted_step
        two_factor.updated_at = now
    else:
        if not _consume_recovery_code(
            db,
            request=request,
            user=user,
            recovery_code=payload.recovery_code or "",
            now=now,
        ):
            _raise_2fa_verify_rejected(
                db,
                request=request,
                challenge=challenge,
                user=user,
                rejection_reason="invalid_code",
            )
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_2FA_RECOVERY_CODE_USED,
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
        )

    challenge.used_at = now
    session, refresh_token = _create_auth_session(
        db,
        request=request,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        create_root_family=True,
    )
    db.flush()
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_VERIFICATION_SUCCEEDED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        auth_session_id=session.id,
    )
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_ISSUED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        auth_session_id=session.id,
        metadata_json={"after_2fa": True},
    )
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=create_access_token(str(user.id), auth_session_id=str(session.id)),
        refresh_token=refresh_token,
    )


@router.post("/2fa/disable", response_model=TwoFactorDisableResponse)
@limiter.limit(settings.RATE_LIMIT_2FA_DISABLE)
def disable_2fa(
    payload: TwoFactorDisableRequest,
    request: Request,
    user: User = Depends(_get_current_admin_user),
    db: Session = Depends(get_db),
) -> TwoFactorDisableResponse:
    now = _now()
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id).with_for_update())
    if not _is_totp_active(two_factor):
        _raise_2fa_not_enabled()

    if not verify_password(payload.current_password, user.hashed_password):
        _raise_2fa_action_verification_failed(db, request=request, user=user)

    _verify_2fa_action_factor(
        db,
        request=request,
        user=user,
        two_factor=two_factor,
        code=payload.code,
        recovery_code=payload.recovery_code,
        now=now,
    )
    invalidated_count = _invalidate_unused_recovery_codes(
        db,
        request=request,
        user=user,
        now=now,
    )

    two_factor.totp_secret_ciphertext = None
    two_factor.totp_secret_nonce = None
    two_factor.totp_secret_key_version = None
    two_factor.totp_enrolled_at = None
    two_factor.totp_last_used_time_step = None
    two_factor.pending_secret_ciphertext = None
    two_factor.pending_secret_nonce = None
    two_factor.pending_secret_key_version = None
    two_factor.pending_started_at = None
    two_factor.pending_expires_at = None
    two_factor.disabled_at = now
    two_factor.updated_at = now
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_DISABLED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"unused_codes_invalidated": invalidated_count},
    )
    db.commit()
    return TwoFactorDisableResponse(status="disabled")


@router.post(
    "/2fa/recovery-codes/regenerate",
    response_model=TwoFactorRecoveryCodesRegenerateResponse,
)
@limiter.limit(settings.RATE_LIMIT_2FA_RECOVERY_REGEN)
def regenerate_2fa_recovery_codes(
    payload: TwoFactorRecoveryCodesRegenerateRequest,
    request: Request,
    user: User = Depends(_get_current_admin_user),
    db: Session = Depends(get_db),
) -> TwoFactorRecoveryCodesRegenerateResponse:
    now = _now()
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id).with_for_update())
    if not _is_totp_active(two_factor):
        _raise_2fa_not_enabled()

    _verify_2fa_action_factor(
        db,
        request=request,
        user=user,
        two_factor=two_factor,
        code=payload.code,
        recovery_code=payload.recovery_code,
        now=now,
    )
    invalidated_count = _invalidate_unused_recovery_codes(
        db,
        request=request,
        user=user,
        now=now,
    )
    recovery_codes = _create_recovery_codes(db, request=request, user=user)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_RECOVERY_CODES_REGENERATED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={
            "unused_codes_invalidated": invalidated_count,
            "codes_issued_count": len(recovery_codes),
        },
    )
    db.commit()
    return TwoFactorRecoveryCodesRegenerateResponse(
        status="regenerated",
        recovery_codes=recovery_codes,
    )


@router.post("/2fa/step-up", response_model=TwoFactorStepUpResponse)
@limiter.limit(settings.RATE_LIMIT_2FA_STEP_UP)
def step_up_2fa(
    payload: TwoFactorStepUpRequest,
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> TwoFactorStepUpResponse:
    user, auth_session = get_current_admin_user_and_session(token=token, db=db)
    _require_admin_portal_role(db, user)
    now = _now()
    two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id).with_for_update())
    if not _is_totp_active(two_factor):
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_2FA_STEP_UP_FAILED,
            rejection_reason="challenge_invalid",
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
            auth_session_id=auth_session.id,
        )
        db.commit()
        raise ApiError(
            status_code=403,
            code="AUTH_2FA_ENROLMENT_REQUIRED",
            message="Two-factor authentication is required for this action",
        )

    _verify_2fa_action_factor(
        db,
        request=request,
        user=user,
        two_factor=two_factor,
        code=payload.code,
        recovery_code=payload.recovery_code,
        now=now,
        failure_event_type=AUTH_EVENT_2FA_STEP_UP_FAILED,
        failure_auth_session_id=auth_session.id,
    )
    auth_session.last_2fa_step_up_at = now
    expires_at = now + timedelta(minutes=settings.TWO_FACTOR_STEP_UP_TTL_MINUTES)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_2FA_STEP_UP_SUCCEEDED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        auth_session_id=auth_session.id,
        metadata_json={"expires_in_minutes": settings.TWO_FACTOR_STEP_UP_TTL_MINUTES},
    )
    db.commit()
    return TwoFactorStepUpResponse(status="verified", expires_at=expires_at)


@router.get("/me", response_model=UserOut | EmployeeMeResponse)
def me(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserOut | EmployeeMeResponse:
    subject = decode_access_token(token)
    if subject.startswith("employee:"):
        return _to_employee_me(_get_employee_account_from_subject(db, subject))

    return _to_user_out(db, _get_user_from_subject(db, subject))


@router.post(
    "/email-verification/request",
    response_model=EmailVerificationRequestResponse,
    status_code=202,
)
@limiter.limit(settings.RATE_LIMIT_EMAIL_VERIFICATION_REQUEST)
def request_email_verification(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> EmailVerificationRequestResponse:
    subject = decode_access_token(token)
    user = _get_user_from_subject(db, subject)

    if user.email_verified_at is not None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_EMAIL_VERIFICATION_ALREADY_VERIFIED,
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
        )
        db.commit()
        response.status_code = 200
        return EmailVerificationRequestResponse(message=EMAIL_VERIFICATION_ALREADY_VERIFIED_MESSAGE)

    raw_token = _create_raw_auth_token()
    token_hash = _hash_auth_token(raw_token)
    expires_at = _now() + timedelta(hours=EMAIL_VERIFICATION_EXPIRY_HOURS)
    auth_token = AuthToken(
        token_type=EMAIL_VERIFICATION_TOKEN_TYPE,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_ip=_request_ip_address(request),
        created_user_agent=request.headers.get("user-agent"),
        request_id=_request_id(request),
    )
    db.add(auth_token)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_EMAIL_VERIFICATION_REQUESTED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"already_verified": False},
    )
    get_email_service().send_email(
        to=user.email,
        template_id=EMAIL_VERIFICATION_TOKEN_TYPE,
        context={
            "user_id": str(user.id),
            "verification_url": _build_email_verification_url(raw_token),
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()
    return EmailVerificationRequestResponse(message=EMAIL_VERIFICATION_GENERIC_MESSAGE)


@router.post("/email-verification/confirm", response_model=EmailVerificationConfirmResponse)
@limiter.limit(settings.RATE_LIMIT_EMAIL_VERIFICATION_CONFIRM)
def confirm_email_verification(
    payload: EmailVerificationConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> EmailVerificationConfirmResponse:
    token_hash = _hash_auth_token(payload.token)
    consumed_at = _now()
    consumed_token = db.execute(
        update(AuthToken)
        .where(
            AuthToken.token_hash == token_hash,
            AuthToken.token_type == EMAIL_VERIFICATION_TOKEN_TYPE,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > consumed_at,
        )
        .values(
            used_at=consumed_at,
            consumed_ip=_request_ip_address(request),
            consumed_user_agent=request.headers.get("user-agent"),
        )
        .returning(AuthToken.id, AuthToken.user_id)
    ).first()

    if consumed_token is None:
        _raise_email_verification_token_rejected(
            db,
            request=request,
            token_hash=token_hash,
        )

    user = db.get(User, consumed_token.user_id)
    if user is None or not user.is_active:
        db.rollback()
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_EMAIL_VERIFICATION_TOKEN_REJECTED,
            rejection_reason="invalid",
            portal="admin",
        )
        db.commit()
        raise ApiError(
            status_code=400,
            code="AUTH_EMAIL_VERIFICATION_INVALID",
            message="Invalid email verification token",
        )

    already_verified = user.email_verified_at is not None
    if not already_verified:
        user.email_verified_at = consumed_at
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_EMAIL_VERIFICATION_COMPLETED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"already_verified": already_verified},
    )
    db.commit()
    return EmailVerificationConfirmResponse(success=True)


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=202,
)
@limiter.limit(settings.RATE_LIMIT_PASSWORD_RESET_REQUEST)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetRequestResponse:
    normalized_email = payload.email.strip().lower()

    dummy_token = _create_raw_auth_token()
    _hash_auth_token(dummy_token)

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not user.is_active:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_PASSWORD_RESET_REQUESTED,
            portal="admin",
            metadata_json={"resolved_user": False},
        )
        db.commit()
        return PasswordResetRequestResponse(message=PASSWORD_RESET_GENERIC_MESSAGE)

    raw_token = _create_raw_auth_token()
    token_hash = _hash_auth_token(raw_token)
    expires_at = _now() + timedelta(hours=PASSWORD_RESET_EXPIRY_HOURS)
    auth_token = AuthToken(
        token_type=PASSWORD_RESET_TOKEN_TYPE,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_ip=_request_ip_address(request),
        created_user_agent=request.headers.get("user-agent"),
        request_id=_request_id(request),
    )
    db.add(auth_token)
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_PASSWORD_RESET_REQUESTED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"resolved_user": True},
    )
    get_email_service().send_email(
        to=user.email,
        template_id=PASSWORD_RESET_TOKEN_TYPE,
        context={
            "user_id": str(user.id),
            "reset_url": _build_password_reset_url(raw_token),
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()
    return PasswordResetRequestResponse(message=PASSWORD_RESET_GENERIC_MESSAGE)


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
@limiter.limit(settings.RATE_LIMIT_PASSWORD_RESET_CONFIRM)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetConfirmResponse:
    if payload.new_password != payload.confirm_password:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Passwords do not match",
        )

    try:
        new_password_hash = get_password_hash(payload.new_password)
    except ValueError as exc:
        if str(exc) != BCRYPT_PASSWORD_TOO_LONG_MESSAGE:
            raise
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc

    token_hash = _hash_auth_token(payload.token)
    consumed_at = _now()
    consumed_token = db.execute(
        update(AuthToken)
        .where(
            AuthToken.token_hash == token_hash,
            AuthToken.token_type == PASSWORD_RESET_TOKEN_TYPE,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > consumed_at,
        )
        .values(
            used_at=consumed_at,
            consumed_ip=_request_ip_address(request),
            consumed_user_agent=request.headers.get("user-agent"),
        )
        .returning(AuthToken.id, AuthToken.user_id)
    ).first()

    if consumed_token is None:
        _raise_password_reset_token_rejected(
            db,
            request=request,
            token_hash=token_hash,
        )

    user = db.get(User, consumed_token.user_id)
    if user is None or not user.is_active:
        db.rollback()
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_PASSWORD_RESET_TOKEN_REJECTED,
            rejection_reason="invalid",
            portal="admin",
        )
        db.commit()
        raise ApiError(
            status_code=400,
            code="AUTH_PASSWORD_RESET_INVALID",
            message="Invalid password reset token",
        )

    user.hashed_password = new_password_hash
    revoked_count = _revoke_active_admin_sessions_for_password_reset(
        db,
        request=request,
        user=user,
    )
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_PASSWORD_RESET_COMPLETED,
        portal="admin",
        tenant_id=user.active_tenant_id,
        user_id=user.id,
        metadata_json={"revoked_session_count": revoked_count},
    )
    db.commit()
    return PasswordResetConfirmResponse(success=True)


@router.post("/employee/login", response_model=EmployeeLoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def employee_login(
    request: Request,
    response: Response,
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
    session, refresh_token = _create_auth_session(
        db,
        request=request,
        portal="employee",
        tenant_id=account.tenant_id,
        employee_account_id=account.id,
        create_root_family=True,
    )
    db.flush()
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_ISSUED,
        portal="employee",
        tenant_id=account.tenant_id,
        employee_account_id=account.id,
        auth_session_id=session.id,
    )
    db.commit()
    db.refresh(account)
    _set_refresh_cookie(response, refresh_token)
    return EmployeeLoginResponse(
        access_token=create_access_token(
            f"employee:{account.id}",
            auth_session_id=str(session.id),
        ),
        refresh_token=refresh_token,
        employee_account=_employee_summary(account),
    )


@router.get("/employee/me", response_model=EmployeeMeResponse)
def employee_me(
    account: EmployeeAccount = Depends(get_current_employee_account),
) -> EmployeeMeResponse:
    return _to_employee_me(account)


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> RefreshTokenResponse:
    _require_csrf_header_for_cookie_refresh(db, request, payload.refresh_token)
    refresh_token = _get_refresh_token_from_request(request, payload.refresh_token)
    if refresh_token is None:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            portal=payload.portal,
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        )

    session = _load_refresh_session(
        db,
        request=request,
        refresh_token=refresh_token,
        expected_portal=payload.portal,
    )

    if session.portal == "admin":
        user = _load_active_admin_user_for_refresh(db, request=request, session=session)
        _revoke_session(session)
        new_session, new_refresh_token = _create_auth_session(
            db,
            request=request,
            portal="admin",
            tenant_id=user.active_tenant_id,
            user_id=user.id,
            session_family_id=session.session_family_id,
            parent_session_id=session.id,
        )
        db.flush()
        access_token = create_access_token(str(user.id), auth_session_id=str(new_session.id))
        portal = "admin"
    elif session.portal == "employee":
        account = _load_active_employee_account_for_refresh(db, request=request, session=session)
        _revoke_session(session)
        new_session, new_refresh_token = _create_auth_session(
            db,
            request=request,
            portal="employee",
            tenant_id=account.tenant_id,
            employee_account_id=account.id,
            session_family_id=session.session_family_id,
            parent_session_id=session.id,
        )
        db.flush()
        access_token = create_access_token(
            f"employee:{account.id}",
            auth_session_id=str(new_session.id),
        )
        portal = "employee"
    else:
        _add_auth_security_event(
            db,
            request=request,
            event_type=AUTH_EVENT_REJECTED,
            rejection_reason="invalid",
            **_event_context_from_session(session),
        )
        db.commit()
        raise ApiError(
            status_code=401,
            code="AUTH_REFRESH_INVALID",
            message="Invalid refresh session",
        )

    session.last_used_at = _now()
    _add_auth_security_event(
        db,
        request=request,
        event_type=AUTH_EVENT_ROTATED,
        **_event_context_from_session(session),
    )
    db.commit()
    _set_refresh_cookie(response, new_refresh_token)
    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        portal=portal,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    db: Session = Depends(get_db),
) -> LogoutResponse:
    payload_token = payload.refresh_token if payload is not None else None
    _require_csrf_header_for_cookie_refresh(db, request, payload_token)
    refresh_token = _get_refresh_token_from_request(
        request,
        payload_token,
    )
    revoked = False
    if refresh_token is not None:
        session = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_refresh_token(refresh_token))
        )
        if session is not None and not session.is_revoked:
            _revoke_session(session)
            _add_auth_security_event(
                db,
                request=request,
                event_type=AUTH_EVENT_REVOKED,
                **_event_context_from_session(session),
            )
            revoked = True
            db.commit()
        elif session is not None and _family_was_revoked_for_reuse(db, session):
            revoked = True
    _clear_refresh_cookie(response)
    return LogoutResponse(revoked=revoked)
