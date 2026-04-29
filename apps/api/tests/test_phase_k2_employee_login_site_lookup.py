from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.store import Store


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_k2_employee_login_site_lookup.db"
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


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _register_and_login(client: TestClient, email: str) -> dict:
    register_body = _register(client, email)
    token = _login(client, email)
    return {
        "id": register_body["id"],
        "email": email,
        "active_tenant_id": register_body["active_tenant_id"],
        "token": token,
    }


def _auth(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['token']}"}


def _create_store(client: TestClient, admin: dict, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": code,
            "name": f"Store {code}",
            "timezone": "Europe/London",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_tenant_member(client: TestClient, admin: dict, email: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Phase K2 Staff",
            "role": "member",
        },
        headers=_auth(admin),
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
        f"phase-k2-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase K2 {username}",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    assert "hashed_password" not in profile
    return user, profile


def _create_site_with_employee(
    client: TestClient,
    *,
    code: str,
    username: str,
) -> tuple[dict, dict, dict, dict]:
    admin = _register_and_login(client, f"phase-k2-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, code)
    user, profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username=username,
    )
    return admin, store, user, profile


def _employee_login(
    client: TestClient,
    *,
    site_id: str,
    username: str,
    password: str = EMPLOYEE_PASSWORD,
):
    return client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": password},
    )


def test_public_lookup_succeeds_for_active_site_code(client: TestClient) -> None:
    _, store, _, _ = _create_site_with_employee(
        client,
        code=f"K2-{uuid.uuid4()}",
        username="alex",
    )

    response = client.get("/api/v1/public/sites/lookup", params={"code": store["code"]})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "site_id": store["id"],
        "site_code": store["code"],
        "site_name": store["name"],
    }
    assert "tenant_id" not in body
    assert "staff" not in body


def test_public_lookup_fails_safely_for_unknown_or_inactive_site(
    client: TestClient,
    test_session_local,
) -> None:
    _, store, _, _ = _create_site_with_employee(
        client,
        code=f"K2-INACTIVE-{uuid.uuid4()}",
        username="inactive",
    )
    with test_session_local() as db:
        site = db.get(Store, uuid.UUID(store["id"]))
        assert site is not None
        site.is_active = False
        db.commit()

    unknown = client.get("/api/v1/public/sites/lookup", params={"code": "missing-site"})
    inactive = client.get("/api/v1/public/sites/lookup", params={"code": store["code"]})

    assert unknown.status_code == 404
    assert inactive.status_code == 404
    assert unknown.json()["error"]["code"] == "SITE_LOOKUP_NOT_FOUND"
    assert inactive.json()["error"]["code"] == "SITE_LOOKUP_NOT_FOUND"
    assert "tenant" not in str(unknown.json()).lower()


def test_employee_can_login_through_lookup_then_existing_site_id_login(
    client: TestClient,
) -> None:
    _, store, _, profile = _create_site_with_employee(
        client,
        code=f"K2-LOGIN-{uuid.uuid4()}",
        username="jamie",
    )

    lookup = client.get("/api/v1/public/sites/lookup", params={"code": store["code"]})
    assert lookup.status_code == 200
    login = _employee_login(
        client,
        site_id=lookup.json()["site_id"],
        username="jamie",
    )

    assert login.status_code == 200
    body = login.json()
    assert body["employee_account"]["id"] == profile["employee_account_id"]
    assert body["employee_account"]["site_id"] == store["id"]


def test_wrong_username_or_password_returns_generic_invalid_credentials(
    client: TestClient,
) -> None:
    _, store, _, _ = _create_site_with_employee(
        client,
        code=f"K2-WRONG-{uuid.uuid4()}",
        username="casey",
    )

    wrong_user = _employee_login(client, site_id=store["id"], username="unknown")
    wrong_password = _employee_login(
        client,
        site_id=store["id"],
        username="casey",
        password="wrong-password",
    )

    for response in (wrong_user, wrong_password):
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "AUTH_INVALID_EMPLOYEE_CREDENTIALS"
        assert body["error"]["message"] == "Invalid site, username, or password"


def test_duplicate_active_site_code_is_ambiguous_and_safe(client: TestClient) -> None:
    duplicate_code = f"K2-DUP-{uuid.uuid4()}"
    _create_site_with_employee(client, code=duplicate_code, username="first")
    _create_site_with_employee(client, code=duplicate_code, username="second")

    response = client.get("/api/v1/public/sites/lookup", params={"code": duplicate_code})

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "SITE_LOOKUP_AMBIGUOUS"
    assert "tenant" not in str(body).lower()
    assert "staff" not in str(body).lower()


def test_existing_site_id_employee_login_still_works(client: TestClient) -> None:
    _, store, _, profile = _create_site_with_employee(
        client,
        code=f"K2-SITE-ID-{uuid.uuid4()}",
        username="morgan",
    )

    response = _employee_login(client, site_id=store["id"], username="morgan")

    assert response.status_code == 200
    assert response.json()["employee_account"]["id"] == profile["employee_account_id"]


def test_admin_login_and_auth_me_still_work(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-k2-auth-{uuid.uuid4()}@example.com")

    response = client.get("/api/v1/auth/me", headers=_auth(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == admin["id"]
    assert body["email"] == admin["email"]
    assert body["active_tenant_id"] == admin["active_tenant_id"]
    assert body["active_tenant_role"] == "admin"
