from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import base64
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token, get_password_hash
from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.auth_token import AuthToken
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers import auth as auth_router

PASSWORD = "password123"
TEST_KEY_BYTES = b"0123456789abcdef0123456789abcdef"
TEST_KEY = base64.b64encode(TEST_KEY_BYTES).decode("ascii")


@pytest.fixture(autouse=True)
def totp_key(monkeypatch):
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", TEST_KEY)


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q5_2a_step_up.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=test_engine)
    try:
        yield session_local
    finally:
        test_engine.dispose()


@pytest.fixture
def client(test_session_local) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _totp_code(secret: str, offset_seconds: int = 0) -> str:
    at_time = auth_router._now() + timedelta(seconds=offset_seconds)
    return pyotp.TOTP(secret).at(int(at_time.timestamp()))


def _register_and_login(client: TestClient, email: str) -> dict:
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    body = register.json()
    body["access_token"] = login.json()["access_token"]
    body["email"] = email
    return body


def _set_email_verified(test_session_local, email: str) -> None:
    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _create_admin_side_user(
    test_session_local,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: str,
) -> None:
    db = test_session_local()
    try:
        user = User(
            email=email,
            hashed_password=get_password_hash(PASSWORD),
            is_active=True,
            active_tenant_id=tenant_id,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()
        db.add(TenantUser(tenant_id=tenant_id, user_id=user.id, role=role))
        db.commit()
    finally:
        db.close()


def _login(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _begin_enrol(client: TestClient, access_token: str) -> dict:
    response = client.post(
        "/api/v1/auth/2fa/totp/enrol/begin",
        headers=_auth(access_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _confirm_enrol(client: TestClient, access_token: str, secret: str) -> dict:
    response = client.post(
        "/api/v1/auth/2fa/totp/enrol/confirm",
        headers=_auth(access_token),
        json={"code": _totp_code(secret)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _enable_2fa(client: TestClient, access_token: str) -> dict:
    begin = _begin_enrol(client, access_token)
    confirm = _confirm_enrol(client, access_token, begin["manual_secret"])
    return {
        "manual_secret": begin["manual_secret"],
        "recovery_codes": confirm["recovery_codes"],
    }


def _step_up_with_totp(client: TestClient, access_token: str, secret: str, offset_seconds: int = 30) -> dict:
    response = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(access_token),
        json={"code": _totp_code(secret, offset_seconds=offset_seconds)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_store(client: TestClient, access_token: str, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        headers=_auth(access_token),
        json={"code": code, "name": f"Store {code}", "timezone": "UTC"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _current_admin_session(test_session_local, email: str) -> AuthSession:
    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        session = db.scalar(
            select(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.portal == "admin",
                AuthSession.is_revoked.is_(False),
            )
            .order_by(AuthSession.created_at.desc())
        )
        assert session is not None
        db.expunge(session)
        return session
    finally:
        db.close()


def _unused_recovery_code_count(test_session_local, email: str) -> int:
    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return int(
            db.scalar(
                select(func.count(AuthToken.id)).where(
                    AuthToken.user_id == user.id,
                    AuthToken.token_type == "recovery_code",
                    AuthToken.used_at.is_(None),
                )
            )
            or 0
        )
    finally:
        db.close()


def test_step_up_succeeds_with_valid_totp_and_stamps_current_session(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q52-step-up-totp@example.com")
    _set_email_verified(test_session_local, owner["email"])
    two_factor = _enable_2fa(client, owner["access_token"])

    result = _step_up_with_totp(client, owner["access_token"], two_factor["manual_secret"])

    assert result["status"] == "verified"
    session = _current_admin_session(test_session_local, owner["email"])
    assert session.last_2fa_step_up_at is not None


def test_step_up_succeeds_with_recovery_code_and_consumes_it(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q52-step-up-recovery@example.com")
    _set_email_verified(test_session_local, owner["email"])
    two_factor = _enable_2fa(client, owner["access_token"])

    response = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(owner["access_token"]),
        json={"recovery_code": two_factor["recovery_codes"][0]},
    )

    assert response.status_code == 200
    assert _unused_recovery_code_count(test_session_local, owner["email"]) == 9


def test_step_up_failures_replay_and_employee_token_blocking(
    client: TestClient,
) -> None:
    owner = _register_and_login(client, "q52-step-up-fail@example.com")

    not_enabled = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(owner["access_token"]),
        json={"code": "123456"},
    )
    assert not_enabled.status_code == 403
    assert not_enabled.json()["error"]["code"] == "AUTH_2FA_ENROLMENT_REQUIRED"

    two_factor = _enable_2fa(client, owner["access_token"])
    invalid = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(owner["access_token"]),
        json={"code": "000000"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"

    code = _totp_code(two_factor["manual_secret"], offset_seconds=30)
    first = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(owner["access_token"]),
        json={"code": code},
    )
    assert first.status_code == 200
    replay = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(owner["access_token"]),
        json={"code": code},
    )
    assert replay.status_code == 400
    assert replay.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"

    employee_token = create_access_token(f"employee:{uuid.uuid4()}")
    employee_response = client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(employee_token),
        json={"code": "123456"},
    )
    assert employee_response.status_code == 401


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED,
    reason="Rate limiting disabled for test run",
)
def test_2fa_step_up_rate_limit_when_enabled(client: TestClient) -> None:
    owner = _register_and_login(client, f"q52-step-up-rate-limit-{uuid.uuid4()}@example.com")
    two_factor = _enable_2fa(client, owner["access_token"])

    for attempt in range(6):
        response = client.post(
            "/api/v1/auth/2fa/step-up",
            headers=_auth(owner["access_token"]),
            json={"code": "000000"},
        )
        if attempt < 5:
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"
        else:
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    assert two_factor["manual_secret"]


def test_store_deactivate_sensitive_action_gates(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q52-store-owner@example.com")
    store = _create_store(client, owner["access_token"], "Q52-GATE")
    two_factor = _enable_2fa(client, owner["access_token"])
    _step_up_with_totp(client, owner["access_token"], two_factor["manual_secret"])

    unverified = client.post(
        f"/api/v1/stores/{store['id']}/deactivate",
        headers=_auth(owner["access_token"]),
    )
    assert unverified.status_code == 403
    assert unverified.json()["error"]["code"] == "AUTH_EMAIL_VERIFICATION_REQUIRED"

    _set_email_verified(test_session_local, owner["email"])
    no_step_owner = _register_and_login(client, "q52-store-no-step@example.com")
    _set_email_verified(test_session_local, no_step_owner["email"])
    no_step_store = _create_store(client, no_step_owner["access_token"], "Q52-NOSTEP")
    no_step_2fa = _enable_2fa(client, no_step_owner["access_token"])
    missing_step = client.post(
        f"/api/v1/stores/{no_step_store['id']}/deactivate",
        headers=_auth(no_step_owner["access_token"]),
    )
    assert missing_step.status_code == 403
    assert missing_step.json()["error"]["code"] == "AUTH_2FA_STEP_UP_REQUIRED"

    _step_up_with_totp(client, no_step_owner["access_token"], no_step_2fa["manual_secret"])
    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == no_step_owner["email"]))
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        session.last_2fa_step_up_at = auth_router._now() - timedelta(minutes=6)
        db.commit()
    finally:
        db.close()
    stale_step = client.post(
        f"/api/v1/stores/{no_step_store['id']}/deactivate",
        headers=_auth(no_step_owner["access_token"]),
    )
    assert stale_step.status_code == 403
    assert stale_step.json()["error"]["code"] == "AUTH_2FA_STEP_UP_REQUIRED"

    plain_owner = _register_and_login(client, "q52-store-no-2fa@example.com")
    _set_email_verified(test_session_local, plain_owner["email"])
    plain_store = _create_store(client, plain_owner["access_token"], "Q52-NO2FA")
    no_2fa = client.post(
        f"/api/v1/stores/{plain_store['id']}/deactivate",
        headers=_auth(plain_owner["access_token"]),
    )
    assert no_2fa.status_code == 403
    assert no_2fa.json()["error"]["code"] == "AUTH_2FA_ENROLMENT_REQUIRED"


def test_store_deactivate_succeeds_after_fresh_step_up_and_keeps_audit(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q52-store-success@example.com")
    _set_email_verified(test_session_local, owner["email"])
    store = _create_store(client, owner["access_token"], "Q52-OK")
    two_factor = _enable_2fa(client, owner["access_token"])
    _step_up_with_totp(client, owner["access_token"], two_factor["manual_secret"])

    response = client.post(
        f"/api/v1/stores/{store['id']}/deactivate",
        headers=_auth(owner["access_token"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False
    db = test_session_local()
    try:
        store_row = db.get(Store, uuid.UUID(store["id"]))
        assert store_row.is_active is False
        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_type == "store",
                AuditLog.entity_id == store["id"],
                AuditLog.action == "deactivate",
            )
        )
        assert audit_log is not None
        event = db.scalar(
            select(AuthSecurityEvent).where(
                AuthSecurityEvent.event_type == "auth.2fa.step_up_succeeded"
            )
        )
        assert event is not None
    finally:
        db.close()


def test_store_deactivate_is_owner_only_and_tenant_isolated(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q52-owner-only-owner@example.com")
    _set_email_verified(test_session_local, owner["email"])
    store = _create_store(client, owner["access_token"], "Q52-OWNER")
    tenant_id = uuid.UUID(owner["active_tenant_id"])

    for role in ("admin", "member"):
        email = f"q52-owner-only-{role}@example.com"
        _create_admin_side_user(test_session_local, tenant_id=tenant_id, email=email, role=role)
        login = _login(client, email)
        two_factor = _enable_2fa(client, login["access_token"])
        _step_up_with_totp(client, login["access_token"], two_factor["manual_secret"])
        response = client.post(
            f"/api/v1/stores/{store['id']}/deactivate",
            headers=_auth(login["access_token"]),
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    outsider = _register_and_login(client, "q52-outsider@example.com")
    _set_email_verified(test_session_local, outsider["email"])
    outsider_2fa = _enable_2fa(client, outsider["access_token"])
    _step_up_with_totp(client, outsider["access_token"], outsider_2fa["manual_secret"])
    cross_tenant = client.post(
        f"/api/v1/stores/{store['id']}/deactivate",
        headers=_auth(outsider["access_token"]),
    )
    assert cross_tenant.status_code == 404


def test_sensitive_action_events_do_not_store_secret_values(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q52-events@example.com")
    store = _create_store(client, owner["access_token"], "Q52-EVENTS")
    two_factor = _enable_2fa(client, owner["access_token"])
    recovery_code = two_factor["recovery_codes"][0]

    client.post(
        "/api/v1/auth/2fa/step-up",
        headers=_auth(owner["access_token"]),
        json={"recovery_code": recovery_code},
    )
    blocked = client.post(
        f"/api/v1/stores/{store['id']}/deactivate",
        headers=_auth(owner["access_token"]),
    )
    assert blocked.status_code == 403

    db = test_session_local()
    try:
        events = list(db.scalars(select(AuthSecurityEvent)).all())
        assert any(event.event_type == "auth.sensitive_action.blocked" for event in events)
        forbidden_values = {
            two_factor["manual_secret"],
            recovery_code,
            "123456",
            "000000",
            PASSWORD,
        }
        for event in events:
            metadata = event.metadata_json or {}
            metadata_text = repr(metadata)
            assert not any(value in metadata_text for value in forbidden_values)
            assert "token_hash" not in metadata_text
            assert "secret" not in metadata_text
            assert "password" not in metadata_text
            assert "recovery_code" not in metadata_text
    finally:
        db.close()
