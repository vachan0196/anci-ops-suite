from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.shift import Shift
from apps.api.models.staff_profile import StaffProfile


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_p1_employee_request_targets.db"
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


def _future_monday(days_ahead: int = 21) -> datetime:
    today = datetime.now(timezone.utc).date()
    target = today + timedelta(days=days_ahead)
    monday = target - timedelta(days=target.weekday())
    return datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
            "email": f"phase-p1-{username}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Phase P1 {username}",
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
    job_title: str = "Cashier",
) -> dict:
    user = _create_tenant_member(client, admin, username)
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase P1 {username}",
            "job_title": job_title,
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


def _employee_login(client: TestClient, *, site_id: str, username: str) -> str:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_shift(
    client: TestClient,
    admin: dict,
    store_id: str,
    assigned_user_id: str,
    *,
    week: datetime | None = None,
) -> dict:
    start_at = (week or _future_monday()) + timedelta(days=1, hours=9)
    end_at = start_at + timedelta(hours=8)
    response = client.post(
        f"/api/v1/sites/{store_id}/shifts",
        json={
            "assigned_employee_account_id": assigned_user_id,
            "role_required": "Cashier",
            "start_time": start_at.isoformat().replace("+00:00", "Z"),
            "end_time": end_at.isoformat().replace("+00:00", "Z"),
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _publish_rota(client: TestClient, admin: dict, store_id: str, week: datetime) -> None:
    response = client.post(
        f"/api/v1/sites/{store_id}/rota/publish",
        json={"week_start": week.date().isoformat()},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200


def test_employee_target_list_returns_only_safe_same_site_active_targets(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-p1-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"P1-{uuid.uuid4()}")
    other_store = _create_store(client, admin, f"P1O-{uuid.uuid4()}")
    requester = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    target = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="blair",
    )
    inactive_account = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="casey",
    )
    inactive_profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="devon",
    )
    other_site = _create_staff_with_employee_account(
        client,
        admin,
        store_id=other_store["id"],
        username="ellis",
    )
    other_tenant_admin = _register_and_login(
        client,
        f"phase-p1-other-admin-{uuid.uuid4()}@example.com",
    )
    other_tenant_store = _create_store(client, other_tenant_admin, f"P1X-{uuid.uuid4()}")
    other_tenant = _create_staff_with_employee_account(
        client,
        other_tenant_admin,
        store_id=other_tenant_store["id"],
        username="finley",
    )

    role_response = client.post(
        f"/api/v1/staff/{target['profile']['id']}/roles",
        json={"role": "cashier"},
        headers=_auth(admin["token"]),
    )
    assert role_response.status_code == 200

    with test_session_local() as db:
        db.get(
            EmployeeAccount,
            uuid.UUID(inactive_account["profile"]["employee_account_id"]),
        ).is_active = False
        db.get(StaffProfile, uuid.UUID(inactive_profile["profile"]["id"])).is_active = False
        db.commit()

    token = _employee_login(client, site_id=store["id"], username="alex")
    response = client.get(
        "/api/v1/employee/me/request-targets?request_type=swap",
        headers=_auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_store"]["id"] == store["id"]
    assert len(body["available_stores"]) == 1
    items = body["items"]
    assert [item["employee_account_id"] for item in items] == [
        target["profile"]["employee_account_id"]
    ]
    assert items[0] == {
        "employee_account_id": target["profile"]["employee_account_id"],
        "display_name": "Phase P1 blair",
        "role_labels": ["cashier"],
        "is_active": True,
    }

    encoded = str(items)
    assert requester["profile"]["employee_account_id"] not in encoded
    assert inactive_account["profile"]["employee_account_id"] not in encoded
    assert inactive_profile["profile"]["employee_account_id"] not in encoded
    assert other_site["profile"]["employee_account_id"] not in encoded
    assert other_tenant["profile"]["employee_account_id"] not in encoded
    forbidden_fields = {
        "tenant_id",
        "username",
        "email",
        "phone",
        "pay_type",
        "hourly_rate",
        "rtw_status",
        "notes",
        "hashed_password",
    }
    assert forbidden_fields.isdisjoint(items[0].keys())


def test_employee_target_list_shift_context_validation(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-p1-shift-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"P1S-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    requester = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    target = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="blair",
    )
    week = _future_monday()
    own_shift = _create_shift(
        client,
        admin,
        store["id"],
        requester["user"]["id"],
        week=week,
    )
    other_employee_shift = _create_shift(
        client,
        admin,
        store["id"],
        target["user"]["id"],
        week=week + timedelta(days=7),
    )
    draft_shift = _create_shift(
        client,
        admin,
        store["id"],
        requester["user"]["id"],
        week=week + timedelta(days=14),
    )
    cancelled_shift = _create_shift(
        client,
        admin,
        store["id"],
        requester["user"]["id"],
        week=week + timedelta(days=21),
    )
    _publish_rota(client, admin, store["id"], week)
    _publish_rota(client, admin, store["id"], week + timedelta(days=7))
    _publish_rota(client, admin, store["id"], week + timedelta(days=21))
    with test_session_local() as db:
        db.get(Shift, uuid.UUID(cancelled_shift["id"])).status = "cancelled"
        db.commit()

    token = _employee_login(client, site_id=store["id"], username="alex")
    valid = client.get(
        f"/api/v1/employee/me/request-targets?request_type=swap&shift_id={own_shift['id']}",
        headers=_auth(token),
    )
    assert valid.status_code == 200
    assert [item["employee_account_id"] for item in valid.json()["items"]] == [
        target["profile"]["employee_account_id"]
    ]

    for shift in [draft_shift, cancelled_shift, other_employee_shift]:
        response = client.get(
            f"/api/v1/employee/me/request-targets?request_type=cover&shift_id={shift['id']}",
            headers=_auth(token),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SHIFT_NOT_FOUND"


def test_employee_target_list_auth_boundaries(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-p1-auth-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"P1A-{uuid.uuid4()}")
    _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    employee_token = _employee_login(client, site_id=store["id"], username="alex")

    admin_response = client.get(
        "/api/v1/employee/me/request-targets",
        headers=_auth(admin["token"]),
    )
    assert admin_response.status_code in {401, 403}

    employee_admin_response = client.get(
        f"/api/v1/sites/{store['id']}/requests",
        headers=_auth(employee_token),
    )
    assert employee_admin_response.status_code in {401, 403}
