from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_l_employee_availability.db"
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


def _future_monday(days_ahead: int = 14) -> date:
    today = datetime.now(timezone.utc).date()
    target = today + timedelta(days=days_ahead)
    return target - timedelta(days=target.weekday())


def _date(value: date, days: int = 0) -> str:
    return (value + timedelta(days=days)).isoformat()


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
    user = _register(client, email)
    return {
        "id": user["id"],
        "active_tenant_id": user["active_tenant_id"],
        "token": _login(client, email),
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


def _configure_opening_hours(client: TestClient, admin: dict, store_id: str) -> None:
    response = client.put(
        f"/api/v1/stores/{store_id}/opening-hours",
        json={
            "opening_hours": [
                {
                    "day_of_week": day,
                    "open_time": "06:00",
                    "close_time": "22:00",
                    "is_closed": False,
                }
                for day in range(7)
            ]
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200


def _create_tenant_member(client: TestClient, admin: dict, username: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"phase-l-{username}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Phase L {username}",
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
    user = _create_tenant_member(client, admin, username)
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase L {username}",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


def _create_site_with_employee(client: TestClient, username: str = "alex") -> tuple[dict, dict, dict]:
    admin = _register_and_login(client, f"phase-l-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"L-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    staff = _create_staff_with_employee_account(client, admin, store_id=store["id"], username=username)
    return admin, store, staff


def _employee_login(client: TestClient, *, site_id: str, username: str) -> str:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_availability(client: TestClient, token: str, week: date, **overrides) -> TestClient:
    payload = {
        "week_start": week.isoformat(),
        "date": _date(week, 1),
        "start_time": "09:00",
        "end_time": "17:00",
        "type": "available",
        "notes": "Available",
    }
    payload.update(overrides)
    return client.post(
        "/api/v1/employee/me/availability",
        json=payload,
        headers=_auth(token),
    )


def _create_shift(client: TestClient, admin: dict, store_id: str, user_id: str, week: date) -> None:
    response = client.post(
        f"/api/v1/sites/{store_id}/shifts",
        json={
            "assigned_employee_account_id": user_id,
            "role_required": "Cashier",
            "start_time": f"{_date(week, 1)}T09:00:00Z",
            "end_time": f"{_date(week, 1)}T17:00:00Z",
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201


def _publish_rota(client: TestClient, admin: dict, store_id: str, week: date) -> None:
    response = client.post(
        f"/api/v1/sites/{store_id}/rota/publish",
        json={"week_start": week.isoformat()},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200


def test_employee_can_create_list_empty_and_delete_own_future_availability(client: TestClient) -> None:
    _, store, _ = _create_site_with_employee(client, username="alex")
    token = _employee_login(client, site_id=store["id"], username="alex")
    week = _future_monday()

    empty = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat()},
        headers=_auth(token),
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    created = _create_availability(client, token, week)
    assert created.status_code == 201
    body = created.json()
    assert body["employee_account_id"]
    assert body["site_id"] == store["id"]

    listed = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat()},
        headers=_auth(token),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [body["id"]]

    deleted = client.delete(
        f"/api/v1/employee/me/availability/{body['id']}",
        headers=_auth(token),
    )
    assert deleted.status_code == 200


def test_duplicate_availability_returns_conflict(client: TestClient) -> None:
    _, store, _ = _create_site_with_employee(client, username="casey")
    token = _employee_login(client, site_id=store["id"], username="casey")
    week = _future_monday()

    assert _create_availability(client, token, week).status_code == 201
    duplicate = _create_availability(client, token, week)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "AVAILABILITY_DUPLICATE"


def test_employee_availability_is_locked_by_published_rota(client: TestClient) -> None:
    admin, store, staff = _create_site_with_employee(client, username="jamie")
    token = _employee_login(client, site_id=store["id"], username="jamie")
    week = _future_monday()

    created = _create_availability(client, token, week, type="available_extra")
    assert created.status_code == 201
    _create_shift(client, admin, store["id"], staff["user"]["id"], week)
    _publish_rota(client, admin, store["id"], week)

    locked_create = _create_availability(client, token, week, type="unavailable")
    assert locked_create.status_code == 409
    assert locked_create.json()["error"]["code"] == "AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA"

    locked_delete = client.delete(
        f"/api/v1/employee/me/availability/{created.json()['id']}",
        headers=_auth(token),
    )
    assert locked_delete.status_code == 409
    assert locked_delete.json()["error"]["code"] == "AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA"


def test_employee_cannot_access_other_employee_tenant_or_site_availability(client: TestClient) -> None:
    _, store_a, _ = _create_site_with_employee(client, username="alex")
    token_a = _employee_login(client, site_id=store_a["id"], username="alex")
    _, store_b, _ = _create_site_with_employee(client, username="blair")
    token_b = _employee_login(client, site_id=store_b["id"], username="blair")
    week = _future_monday()

    created = _create_availability(client, token_a, week)
    assert created.status_code == 201

    foreign_delete = client.delete(
        f"/api/v1/employee/me/availability/{created.json()['id']}",
        headers=_auth(token_b),
    )
    assert foreign_delete.status_code == 404
    assert foreign_delete.json()["error"]["code"] == "AVAILABILITY_NOT_FOUND"

    wrong_site = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat(), "store_id": store_b["id"]},
        headers=_auth(token_a),
    )
    assert wrong_site.status_code == 404
    assert wrong_site.json()["error"]["code"] == "STORE_NOT_FOUND"


def test_admin_token_cannot_access_employee_availability_and_employee_token_cannot_access_admin_api(
    client: TestClient,
) -> None:
    admin, store, _ = _create_site_with_employee(client, username="alex")
    employee_token = _employee_login(client, site_id=store["id"], username="alex")
    week = _future_monday()

    admin_on_employee = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat()},
        headers=_auth(admin["token"]),
    )
    assert admin_on_employee.status_code == 401

    employee_on_admin = client.get(
        "/api/v1/stores",
        headers=_auth(employee_token),
    )
    assert employee_on_admin.status_code == 401


def test_availability_validation_returns_safe_errors(client: TestClient) -> None:
    _, store, _ = _create_site_with_employee(client, username="riley")
    token = _employee_login(client, site_id=store["id"], username="riley")
    week = _future_monday()

    not_monday = _create_availability(client, token, week + timedelta(days=1))
    assert not_monday.status_code == 422

    out_of_week = _create_availability(client, token, week, date=_date(week, 8))
    assert out_of_week.status_code == 422

    bad_time = _create_availability(client, token, week, start_time="17:00", end_time="09:00")
    assert bad_time.status_code == 422

    past = _create_availability(
        client,
        token,
        week,
        date=(datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
    )
    assert past.status_code == 422


def test_regressions_employee_rota_and_public_lookup_still_work(client: TestClient) -> None:
    admin, store, staff = _create_site_with_employee(client, username="morgan")
    token = _employee_login(client, site_id=store["id"], username="morgan")
    week = _future_monday()
    _create_shift(client, admin, store["id"], staff["user"]["id"], week)
    _publish_rota(client, admin, store["id"], week)

    rota = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": week.isoformat()},
        headers=_auth(token),
    )
    assert rota.status_code == 200
    assert len(rota.json()["shifts"]) == 1

    lookup = client.get("/api/v1/public/sites/lookup", params={"code": store["code"]})
    assert lookup.status_code == 200
    assert lookup.json() == {
        "site_id": store["id"],
        "site_code": store["code"],
        "site_name": store["name"],
    }
