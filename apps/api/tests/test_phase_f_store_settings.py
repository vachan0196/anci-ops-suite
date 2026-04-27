from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog


PASSWORD = "password123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_f_store_settings.db"
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


def _create_store(client: TestClient, admin: dict, name: str = "Phase F Store") -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"PH-F-{uuid.uuid4()}",
            "name": name,
            "timezone": "Europe/London",
            "address_line1": "1 Opening Road",
            "city": None,
            "postcode": None,
            "phone": "07111111111",
            "manager_user_id": None,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _opening_hours_payload() -> dict:
    return {
        "opening_hours": [
            {
                "day_of_week": 0,
                "open_time": "06:00",
                "close_time": "22:00",
                "is_closed": False,
            },
            {
                "day_of_week": 1,
                "open_time": None,
                "close_time": None,
                "is_closed": True,
            },
        ]
    }


def test_unauthenticated_store_settings_endpoints_rejected(client: TestClient) -> None:
    store_id = uuid.uuid4()

    opening_hours_response = client.get(f"/api/v1/stores/{store_id}/opening-hours")
    settings_response = client.get(f"/api/v1/stores/{store_id}/settings")

    assert opening_hours_response.status_code == 401
    assert settings_response.status_code == 401


def test_valid_store_opening_hours_fetch_defaults_to_empty(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-f-fetch-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)

    response = client.get(
        f"/api/v1/stores/{store['id']}/opening-hours",
        headers=_auth(admin),
    )

    assert response.status_code == 200
    assert response.json() == {"store_id": store["id"], "opening_hours": []}


def test_opening_hours_save_and_fetch_persists(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-f-hours-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)

    save_response = client.put(
        f"/api/v1/stores/{store['id']}/opening-hours",
        json=_opening_hours_payload(),
        headers=_auth(admin),
    )
    assert save_response.status_code == 200
    assert save_response.json()["store_id"] == store["id"]
    assert save_response.json()["opening_hours"][0]["day_of_week"] == 0
    assert save_response.json()["opening_hours"][0]["open_time"].startswith("06:00")
    assert save_response.json()["opening_hours"][1]["is_closed"] is True
    assert save_response.json()["opening_hours"][1]["open_time"] is None

    fetch_response = client.get(
        f"/api/v1/stores/{store['id']}/opening-hours",
        headers=_auth(admin),
    )
    assert fetch_response.status_code == 200
    assert fetch_response.json() == save_response.json()


def test_invalid_opening_hours_day_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-f-day-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)

    response = client.put(
        f"/api/v1/stores/{store['id']}/opening-hours",
        json={
            "opening_hours": [
                {
                    "day_of_week": 7,
                    "open_time": "06:00",
                    "close_time": "22:00",
                    "is_closed": False,
                }
            ]
        },
        headers=_auth(admin),
    )

    assert response.status_code == 422


def test_invalid_opening_hours_time_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-f-time-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)

    response = client.put(
        f"/api/v1/stores/{store['id']}/opening-hours",
        json={
            "opening_hours": [
                {
                    "day_of_week": 0,
                    "open_time": "22:00",
                    "close_time": "06:00",
                    "is_closed": False,
                }
            ]
        },
        headers=_auth(admin),
    )

    assert response.status_code == 422


def test_cross_tenant_store_opening_hours_blocked(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-f-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-f-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a)

    response = client.put(
        f"/api/v1/stores/{store_a['id']}/opening-hours",
        json=_opening_hours_payload(),
        headers=_auth(admin_b),
    )

    assert response.status_code == 404


def test_store_settings_update_persists(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-f-settings-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)

    default_response = client.get(
        f"/api/v1/stores/{store['id']}/settings",
        headers=_auth(admin),
    )
    assert default_response.status_code == 200
    assert default_response.json() == {
        "store_id": store["id"],
        "business_week_start_day": 0,
    }

    update_response = client.patch(
        f"/api/v1/stores/{store['id']}/settings",
        json={"business_week_start_day": 1},
        headers=_auth(admin),
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "store_id": store["id"],
        "business_week_start_day": 1,
    }

    fetch_response = client.get(
        f"/api/v1/stores/{store['id']}/settings",
        headers=_auth(admin),
    )
    assert fetch_response.status_code == 200
    assert fetch_response.json()["business_week_start_day"] == 1


def test_store_opening_hours_and_settings_audit_logs_created(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-f-audit-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)

    client.put(
        f"/api/v1/stores/{store['id']}/opening-hours",
        json=_opening_hours_payload(),
        headers=_auth(admin),
    )
    client.patch(
        f"/api/v1/stores/{store['id']}/settings",
        json={"business_week_start_day": 1},
        headers=_auth(admin),
    )

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "store",
                AuditLog.entity_id == store["id"],
            )
        ).all()
        actions = {log.action for log in logs}
    finally:
        db.close()

    assert "store_opening_hours_updated" in actions
    assert "store_settings_updated" in actions
