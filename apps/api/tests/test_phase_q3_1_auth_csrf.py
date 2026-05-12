from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
import pytest

from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"
CSRF_HEADERS = {"X-Requested-With": "ForecourtOS"}


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q3_1_auth_csrf.db"
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


def _register_and_login(client: TestClient, email: str) -> dict:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login_response.status_code == 200
    body = login_response.json()
    return {
        "id": register_response.json()["id"],
        "token": body["access_token"],
        "refresh_token": body["refresh_token"],
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
            "full_name": "Phase Q3.1 Staff",
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
        f"phase-q3-1-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase Q3.1 {username}",
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


def _create_admin_employee_context(client: TestClient) -> tuple[dict, dict, dict]:
    admin = _register_and_login(client, f"phase-q3-1-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"Q31-{uuid.uuid4()}")
    profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    return admin, store, profile


def test_cookie_backed_refresh_requires_csrf_header(client: TestClient) -> None:
    _register_and_login(client, f"phase-q3-1-cookie-refresh-{uuid.uuid4()}@example.com")
    assert settings.AUTH_REFRESH_COOKIE_NAME in client.cookies

    response = client.post("/api/v1/auth/refresh", json={"portal": "admin"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_CSRF_REQUIRED"


def test_cookie_backed_refresh_with_csrf_header_succeeds(client: TestClient) -> None:
    _register_and_login(client, f"phase-q3-1-cookie-refresh-ok-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"portal": "admin"},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["portal"] == "admin"
    assert response.json()["access_token"]
    assert client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME) == response.json()["refresh_token"]


def test_cookie_backed_logout_requires_csrf_header(client: TestClient) -> None:
    _register_and_login(client, f"phase-q3-1-cookie-logout-{uuid.uuid4()}@example.com")

    response = client.post("/api/v1/auth/logout", json={})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_CSRF_REQUIRED"
    assert settings.AUTH_REFRESH_COOKIE_NAME in client.cookies


def test_cookie_backed_logout_with_csrf_header_revokes_and_clears_cookie(
    client: TestClient,
) -> None:
    _register_and_login(client, f"phase-q3-1-cookie-logout-ok-{uuid.uuid4()}@example.com")

    response = client.post("/api/v1/auth/logout", json={}, headers=CSRF_HEADERS)
    set_cookie = response.headers.get("set-cookie", "")

    assert response.status_code == 200
    assert response.json()["revoked"] is True
    assert settings.AUTH_REFRESH_COOKIE_NAME not in client.cookies
    assert settings.AUTH_REFRESH_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


def test_body_refresh_token_compatibility_does_not_require_csrf_header(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-q3-1-body-refresh-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["portal"] == "admin"


def test_bearer_protected_endpoints_do_not_require_csrf_header(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-q3-1-bearer-{uuid.uuid4()}@example.com")

    me_response = client.get("/api/v1/auth/me", headers=_auth(admin["token"]))
    stores_response = client.get("/api/v1/stores", headers=_auth(admin["token"]))

    assert me_response.status_code == 200
    assert stores_response.status_code == 200


def test_admin_refresh_token_rejects_employee_portal(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-q3-1-admin-boundary-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 401
    assert admin["refresh_token"] not in response.text


def test_employee_refresh_token_rejects_admin_portal(client: TestClient) -> None:
    _, store, _ = _create_admin_employee_context(client)
    employee_login = _create_employee_login(client, site_id=store["id"], username="alex")
    employee_refresh = employee_login["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_refresh, "portal": "admin"},
    )

    assert response.status_code == 401
    assert employee_refresh not in response.text
