from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app


PASSWORD = "password123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_i1_rota_week_read.db"
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
            "full_name": "Phase I1 Staff",
            "role": "member",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_shift(
    client: TestClient,
    admin: dict,
    *,
    store_id: str,
    start_at: str,
    end_at: str,
    assigned_user_id: str | None = None,
    required_role: str | None = None,
) -> dict:
    payload = {
        "store_id": store_id,
        "start_at": start_at,
        "end_at": end_at,
    }
    if assigned_user_id is not None:
        payload["assigned_user_id"] = assigned_user_id
    if required_role is not None:
        payload["required_role"] = required_role

    response = client.post("/api/v1/shifts", json=payload, headers=_auth(admin))
    assert response.status_code == 201
    return response.json()


def test_site_weekly_rota_returns_selected_site_week_shifts(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i1-admin-{uuid.uuid4()}@example.com")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i1-member-{uuid.uuid4()}@example.com",
    )
    store = _create_store(client, admin, f"I1-A-{uuid.uuid4()}")
    other_store = _create_store(client, admin, f"I1-B-{uuid.uuid4()}")

    included = _create_shift(
        client,
        admin,
        store_id=store["id"],
        assigned_user_id=member["id"],
        required_role="cashier",
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )
    _create_shift(
        client,
        admin,
        store_id=store["id"],
        start_at="2026-04-13T09:00:00Z",
        end_at="2026-04-13T17:00:00Z",
    )
    _create_shift(
        client,
        admin,
        store_id=other_store["id"],
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )

    response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-04-06"},
        headers=_auth(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["site_id"] == store["id"]
    assert body["week_start"] == "2026-04-06"
    assert body["shifts"] == [
        {
            "id": included["id"],
            "assigned_employee_account_id": member["id"],
            "role_required": "cashier",
            "start_time": included["start_at"],
            "end_time": included["end_at"],
        }
    ]


def test_site_weekly_rota_rejects_cross_tenant_site(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-i1-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-i1-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a, f"I1-X-{uuid.uuid4()}")

    response = client.get(
        f"/api/v1/sites/{store_a['id']}/rota/week",
        params={"week_start": "2026-04-06"},
        headers=_auth(admin_b),
    )

    assert response.status_code == 404
