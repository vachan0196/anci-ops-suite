from collections.abc import Generator, Iterable
from datetime import timedelta
import json
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.user import User
from apps.api.routers.auth import _now


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"
CSRF_HEADERS = {"X-Requested-With": "ForecourtOS"}


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q3_2_1_auth_security_events.db"
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def _register_and_login(client: TestClient, email: str) -> dict:
    register_body = _register(client, email)
    login_body = _login(client, email)
    return {
        "id": register_body["id"],
        "active_tenant_id": register_body["active_tenant_id"],
        "token": login_body["access_token"],
        "refresh_token": login_body["refresh_token"],
    }


def _create_store(client: TestClient, admin: dict, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={"code": code, "name": f"Store {code}", "timezone": "Europe/London"},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _create_tenant_member(client: TestClient, admin: dict, email: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Phase Q3.2.1 Staff",
            "role": "member",
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _create_staff_with_employee_account(
    client: TestClient,
    admin: dict,
    *,
    store_id: str,
    username: str,
) -> dict:
    user = _create_tenant_member(
        client,
        admin,
        f"phase-q3-2-1-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase Q3.2.1 {username}",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _create_employee_login(client: TestClient, *, site_id: str, username: str) -> dict:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def _create_admin_employee_context(client: TestClient) -> tuple[dict, dict, dict, dict]:
    admin = _register_and_login(client, f"phase-q3-2-1-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"Q321-{uuid.uuid4()}")
    profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    employee_login = _create_employee_login(client, site_id=store["id"], username="alex")
    return admin, store, profile, employee_login


def _events(
    db: Session,
    *,
    event_type: str | None = None,
    rejection_reason: str | None = None,
) -> list[AuthSecurityEvent]:
    statement = select(AuthSecurityEvent).order_by(AuthSecurityEvent.created_at, AuthSecurityEvent.id)
    if event_type is not None:
        statement = statement.where(AuthSecurityEvent.event_type == event_type)
    if rejection_reason is not None:
        statement = statement.where(AuthSecurityEvent.rejection_reason == rejection_reason)
    return list(db.scalars(statement).all())


def _event_payload(event: AuthSecurityEvent) -> str:
    values = {
        "id": str(event.id),
        "created_at": str(event.created_at),
        "event_type": event.event_type,
        "rejection_reason": event.rejection_reason,
        "portal": event.portal,
        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
        "user_id": str(event.user_id) if event.user_id else None,
        "employee_account_id": str(event.employee_account_id) if event.employee_account_id else None,
        "auth_session_id": str(event.auth_session_id) if event.auth_session_id else None,
        "request_id": event.request_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "metadata_json": event.metadata_json,
    }
    return json.dumps(values, sort_keys=True, default=str)


def _assert_no_secret_leakage(
    db: Session,
    events: Iterable[AuthSecurityEvent],
    *,
    raw_refresh_tokens: Iterable[str] = (),
    raw_access_tokens: Iterable[str] = (),
    passwords: Iterable[str] = (PASSWORD, EMPLOYEE_PASSWORD),
) -> None:
    token_hashes = db.scalars(select(AuthSession.token_hash)).all()
    forbidden_values = [
        *raw_refresh_tokens,
        *raw_access_tokens,
        *token_hashes,
        *passwords,
        "Bearer ",
        settings.AUTH_REFRESH_COOKIE_NAME,
    ]
    for event in events:
        payload = _event_payload(event)
        for value in forbidden_values:
            if value:
                assert value not in payload


def test_admin_login_creates_issued_event(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-issued-admin-{uuid.uuid4()}@example.com")

    with test_session_local() as db:
        issued = _events(db, event_type="auth.session.issued")
        assert len(issued) == 1
        event = issued[0]
        assert event.portal == "admin"
        assert str(event.tenant_id) == admin["active_tenant_id"]
        assert str(event.user_id) == admin["id"]
        assert event.auth_session_id is not None
        assert event.request_id
        assert event.ip_address
        assert event.user_agent
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_employee_login_creates_issued_event(client: TestClient, test_session_local) -> None:
    _, _, profile, employee_login = _create_admin_employee_context(client)

    with test_session_local() as db:
        issued = _events(db, event_type="auth.session.issued")
        employee_events = [event for event in issued if event.portal == "employee"]
        assert len(employee_events) == 1
        event = employee_events[0]
        assert str(event.tenant_id) == profile["tenant_id"]
        assert str(event.employee_account_id) == profile["employee_account_id"]
        assert event.user_id is None
        assert event.auth_session_id is not None
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[employee_login["refresh_token"]],
            raw_access_tokens=[employee_login["access_token"]],
        )


def test_successful_refresh_creates_rotated_event(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-rotated-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 200
    with test_session_local() as db:
        rotated = _events(db, event_type="auth.session.rotated")
        assert len(rotated) == 1
        assert rotated[0].portal == "admin"
        assert str(rotated[0].user_id) == admin["id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"], response.json()["refresh_token"]],
            raw_access_tokens=[admin["token"], response.json()["access_token"]],
        )


def test_successful_logout_creates_revoked_event(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-revoked-{uuid.uuid4()}@example.com")

    response = client.post("/api/v1/auth/logout", json={"refresh_token": admin["refresh_token"]})

    assert response.status_code == 200
    assert response.json()["revoked"] is True
    with test_session_local() as db:
        revoked = _events(db, event_type="auth.session.revoked")
        assert len(revoked) == 1
        assert str(revoked[0].user_id) == admin["id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_invalid_refresh_token_creates_rejected_invalid_event(
    client: TestClient,
    test_session_local,
) -> None:
    raw_invalid_refresh = f"invalid-refresh-{uuid.uuid4()}"

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_invalid_refresh, "portal": "admin"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="invalid",
        )
        assert len(rejected) == 1
        assert rejected[0].tenant_id is None
        assert rejected[0].user_id is None
        assert rejected[0].employee_account_id is None
        assert rejected[0].auth_session_id is None
        _assert_no_secret_leakage(db, _events(db), raw_refresh_tokens=[raw_invalid_refresh])


def test_revoked_refresh_token_creates_rejected_revoked_event(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-rejected-revoked-{uuid.uuid4()}@example.com")
    logout = client.post("/api/v1/auth/logout", json={"refresh_token": admin["refresh_token"]})
    assert logout.status_code == 200

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="revoked",
        )
        assert len(rejected) == 1
        assert str(rejected[0].user_id) == admin["id"]
        assert rejected[0].auth_session_id is not None
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_expired_refresh_token_creates_rejected_expired_event(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-rejected-expired-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == uuid.UUID(admin["id"])))
        assert session is not None
        session.expires_at = _now() - timedelta(minutes=1)
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="expired",
        )
        assert len(rejected) == 1
        assert str(rejected[0].user_id) == admin["id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_wrong_portal_refresh_creates_rejected_wrong_portal_event(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-wrong-portal-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="wrong_portal",
        )
        assert len(rejected) == 1
        assert rejected[0].portal == "admin"
        assert str(rejected[0].user_id) == admin["id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_cookie_backed_refresh_missing_csrf_creates_rejected_event(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-missing-csrf-{uuid.uuid4()}@example.com")

    response = client.post("/api/v1/auth/refresh", json={"portal": "admin"})

    assert response.status_code == 403
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="missing_csrf_header",
        )
        assert len(rejected) == 1
        assert rejected[0].metadata_json == {"cookie_backed": True}
        assert str(rejected[0].user_id) == admin["id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_disabled_admin_refresh_creates_blocked_event(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-2-1-disabled-admin-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        user = db.get(User, uuid.UUID(admin["id"]))
        assert user is not None
        user.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 403
    with test_session_local() as db:
        blocked = _events(db, event_type="auth.session.blocked_disabled_admin")
        assert len(blocked) == 1
        assert blocked[0].portal == "admin"
        assert str(blocked[0].user_id) == admin["id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"]],
            raw_access_tokens=[admin["token"]],
        )


def test_disabled_employee_refresh_creates_blocked_event(
    client: TestClient,
    test_session_local,
) -> None:
    _, _, profile, employee_login = _create_admin_employee_context(client)
    with test_session_local() as db:
        account = db.get(EmployeeAccount, uuid.UUID(profile["employee_account_id"]))
        assert account is not None
        account.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_login["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 403
    with test_session_local() as db:
        blocked = _events(db, event_type="auth.session.blocked_disabled_employee")
        assert len(blocked) == 1
        assert blocked[0].portal == "employee"
        assert str(blocked[0].employee_account_id) == profile["employee_account_id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[employee_login["refresh_token"]],
            raw_access_tokens=[employee_login["access_token"]],
        )


def test_inactive_staff_profile_refresh_creates_blocked_event(
    client: TestClient,
    test_session_local,
) -> None:
    _, _, profile, employee_login = _create_admin_employee_context(client)
    with test_session_local() as db:
        staff_profile = db.get(StaffProfile, uuid.UUID(profile["id"]))
        assert staff_profile is not None
        staff_profile.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_login["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 403
    with test_session_local() as db:
        blocked = _events(db, event_type="auth.session.blocked_inactive_staff_profile")
        assert len(blocked) == 1
        assert blocked[0].portal == "employee"
        assert str(blocked[0].employee_account_id) == profile["employee_account_id"]
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[employee_login["refresh_token"]],
            raw_access_tokens=[employee_login["access_token"]],
        )
