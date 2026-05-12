from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_session import AuthSession
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.user import User


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"
CSRF_HEADERS = {"X-Requested-With": "ForecourtOS"}


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q2_auth_sessions.db"
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
        "email": email,
        "active_tenant_id": register_body["active_tenant_id"],
        "token": login_body["access_token"],
        "refresh_token": login_body["refresh_token"],
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
            "full_name": "Phase Q2 Staff",
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
) -> tuple[dict, dict]:
    user = _create_tenant_member(
        client,
        admin,
        f"phase-q2-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase Q2 {username}",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return user, response.json()


def _create_employee_login(client: TestClient, *, site_id: str, username: str) -> dict:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def _create_admin_employee_context(client: TestClient) -> tuple[dict, dict, dict, dict]:
    admin = _register_and_login(client, f"phase-q2-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"Q2-{uuid.uuid4()}")
    user, profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    return admin, store, user, profile


def test_admin_login_refresh_logout_and_revocation(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q2-refresh-{uuid.uuid4()}@example.com")

    me_before_logout = client.get("/api/v1/auth/me", headers=_auth(admin["token"]))
    assert me_before_logout.status_code == 200
    assert admin["refresh_token"]

    with test_session_local() as db:
        sessions = db.scalars(select(AuthSession)).all()
    assert len(sessions) == 1
    assert sessions[0].portal == "admin"
    assert sessions[0].user_id == uuid.UUID(admin["id"])
    assert sessions[0].token_hash != admin["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["portal"] == "admin"
    assert refreshed["access_token"]
    assert refreshed["refresh_token"] != admin["refresh_token"]

    reused_old_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )
    assert reused_old_refresh.status_code == 401

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed["refresh_token"]},
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["revoked"] is True

    refresh_after_logout = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refreshed["refresh_token"], "portal": "admin"},
    )
    assert refresh_after_logout.status_code == 401
    assert refreshed["refresh_token"] not in refresh_after_logout.text


def test_employee_login_refresh_and_portal_boundary(client: TestClient) -> None:
    admin, store, _, profile = _create_admin_employee_context(client)
    employee_login = _create_employee_login(client, site_id=store["id"], username="alex")
    employee_token = employee_login["access_token"]
    employee_refresh = employee_login["refresh_token"]

    employee_me = client.get("/api/v1/auth/employee/me", headers=_auth(employee_token))
    auth_me = client.get("/api/v1/auth/me", headers=_auth(employee_token))
    employee_on_admin = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-06-01"},
        headers=_auth(employee_token),
    )
    admin_on_employee = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": "2026-06-01"},
        headers=_auth(admin["token"]),
    )

    assert employee_me.status_code == 200
    assert auth_me.status_code == 200
    assert auth_me.json()["employee_account_id"] == profile["employee_account_id"]
    assert employee_on_admin.status_code == 401
    assert admin_on_employee.status_code == 401

    wrong_portal = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_refresh, "portal": "admin"},
    )
    assert wrong_portal.status_code == 401
    assert employee_refresh not in wrong_portal.text

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_refresh, "portal": "employee"},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["portal"] == "employee"


def test_admin_refresh_token_rejects_employee_portal(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-q2-wrong-portal-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 401
    assert admin["refresh_token"] not in response.text


def test_expired_refresh_token_is_rejected_without_leaking_token(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q2-expired-refresh-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == uuid.UUID(admin["id"])))
        assert session is not None
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 401
    assert admin["refresh_token"] not in response.text


def test_expired_access_token_can_refresh_with_valid_session(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-q2-expired-access-{uuid.uuid4()}@example.com")
    expired_access_token = jwt.encode(
        {
            "sub": admin["id"],
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    expired_access = client.get("/api/v1/auth/me", headers=_auth(expired_access_token))
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert expired_access.status_code == 401
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


def test_refresh_and_logout_use_http_only_cookie_when_body_token_omitted(client: TestClient) -> None:
    _register_and_login(client, f"phase-q2-cookie-{uuid.uuid4()}@example.com")
    assert settings.AUTH_REFRESH_COOKIE_NAME in client.cookies

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"portal": "admin"},
        headers=CSRF_HEADERS,
    )
    assert refresh_response.status_code == 200
    rotated_refresh = refresh_response.json()["refresh_token"]
    assert settings.AUTH_REFRESH_COOKIE_NAME in client.cookies
    assert client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME) == rotated_refresh

    logout_response = client.post("/api/v1/auth/logout", json={}, headers=CSRF_HEADERS)
    set_cookie = logout_response.headers.get("set-cookie", "")

    assert logout_response.status_code == 200
    assert logout_response.json()["revoked"] is True
    assert settings.AUTH_REFRESH_COOKIE_NAME not in client.cookies
    assert settings.AUTH_REFRESH_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie

    refresh_after_cookie_logout = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated_refresh, "portal": "admin"},
    )
    assert refresh_after_cookie_logout.status_code == 401
    assert rotated_refresh not in refresh_after_cookie_logout.text


def test_invalid_refresh_error_does_not_echo_token(client: TestClient) -> None:
    invalid_refresh_token = "invalid-refresh-token-value"

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": invalid_refresh_token, "portal": "admin"},
    )

    assert response.status_code == 401
    assert invalid_refresh_token not in response.text


def test_disabled_admin_user_blocks_existing_access_and_refresh(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q2-disabled-admin-{uuid.uuid4()}@example.com")

    with test_session_local() as db:
        user = db.get(User, uuid.UUID(admin["id"]))
        assert user is not None
        user.is_active = False
        db.commit()

    protected_response = client.get("/api/v1/auth/me", headers=_auth(admin["token"]))
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert protected_response.status_code == 403
    assert refresh_response.status_code == 403
    assert admin["refresh_token"] not in refresh_response.text


def test_disabled_employee_and_inactive_staff_block_existing_sessions(
    client: TestClient,
    test_session_local,
) -> None:
    _, store, _, profile = _create_admin_employee_context(client)
    employee_login = _create_employee_login(client, site_id=store["id"], username="alex")

    with test_session_local() as db:
        account = db.get(EmployeeAccount, uuid.UUID(profile["employee_account_id"]))
        assert account is not None
        account.is_active = False
        db.commit()

    inactive_account_me = client.get(
        "/api/v1/auth/employee/me",
        headers=_auth(employee_login["access_token"]),
    )
    inactive_account_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_login["refresh_token"], "portal": "employee"},
    )
    assert inactive_account_me.status_code == 403
    assert inactive_account_refresh.status_code == 403

    with test_session_local() as db:
        account = db.get(EmployeeAccount, uuid.UUID(profile["employee_account_id"]))
        assert account is not None
        account.is_active = True
        db.commit()

    second_login = _create_employee_login(client, site_id=store["id"], username="alex")
    with test_session_local() as db:
        staff_profile = db.get(StaffProfile, uuid.UUID(profile["id"]))
        assert staff_profile is not None
        staff_profile.is_active = False
        db.commit()

    inactive_profile_me = client.get(
        "/api/v1/auth/employee/me",
        headers=_auth(second_login["access_token"]),
    )
    inactive_profile_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_login["refresh_token"], "portal": "employee"},
    )
    assert inactive_profile_me.status_code == 403
    assert inactive_profile_refresh.status_code == 403
