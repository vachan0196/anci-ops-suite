from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.shift import Shift
from apps.api.models.shift_request import ShiftRequest


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_m_employee_requests.db"
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
            "email": f"phase-m-{username}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Phase M {username}",
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
            "display_name": f"Phase M {username}",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


def _create_site_with_employees(
    client: TestClient,
    usernames: list[str],
) -> tuple[dict, dict, dict[str, dict]]:
    admin = _register_and_login(client, f"phase-m-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"M-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    staff = {
        username: _create_staff_with_employee_account(
            client,
            admin,
            store_id=store["id"],
            username=username,
        )
        for username in usernames
    }
    return admin, store, staff


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
    user_id: str,
    *,
    week: datetime | None = None,
) -> dict:
    start_at = (week or _future_monday()) + timedelta(days=1, hours=9)
    end_at = start_at + timedelta(hours=8)
    response = client.post(
        f"/api/v1/sites/{store_id}/shifts",
        json={
            "assigned_employee_account_id": user_id,
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


def _published_shift(client: TestClient, admin: dict, store: dict, staff: dict) -> dict:
    week = _future_monday()
    shift = _create_shift(client, admin, store["id"], staff["user"]["id"], week=week)
    _publish_rota(client, admin, store["id"], week)
    return shift


def test_employee_can_submit_leave_cover_swap_list_and_cancel_pending_request(client: TestClient) -> None:
    admin, store, staff = _create_site_with_employees(client, ["alex", "blair"])
    token = _employee_login(client, site_id=store["id"], username="alex")
    shift = _published_shift(client, admin, store, staff["alex"])

    empty = client.get("/api/v1/employee/me/requests", headers=_auth(token))
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    leave = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "end_date": (_future_monday().date() + timedelta(days=3)).isoformat(),
            "reason": "Family commitment",
        },
        headers=_auth(token),
    )
    assert leave.status_code == 201
    assert leave.json()["status"] == "pending"
    assert leave.json()["request_type"] == "leave"

    cover = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": shift["id"], "reason": "Need cover"},
        headers=_auth(token),
    )
    assert cover.status_code == 201
    assert cover.json()["request_type"] == "cover"

    swap = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shift["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
            "reason": "Need to swap",
        },
        headers=_auth(token),
    )
    assert swap.status_code == 201
    assert swap.json()["request_type"] == "swap"

    listed = client.get("/api/v1/employee/me/requests", headers=_auth(token))
    assert listed.status_code == 200
    assert {item["request_type"] for item in listed.json()["items"]} == {"leave", "cover", "swap"}

    cancelled = client.post(
        f"/api/v1/employee/me/requests/{leave.json()['id']}/cancel",
        headers=_auth(token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None


def test_employee_request_duplicate_and_non_pending_cancel_errors(
    client: TestClient,
    test_session_local,
) -> None:
    _, store, _ = _create_site_with_employees(client, ["alex"])
    token = _employee_login(client, site_id=store["id"], username="alex")
    payload = {
        "request_type": "leave",
        "start_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
        "end_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
        "reason": "Appointment",
    }

    created = client.post("/api/v1/employee/me/requests", json=payload, headers=_auth(token))
    assert created.status_code == 201
    duplicate = client.post("/api/v1/employee/me/requests", json=payload, headers=_auth(token))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "REQUEST_DUPLICATE"

    with test_session_local() as db:
        request = db.get(ShiftRequest, uuid.UUID(created.json()["id"]))
        assert request is not None
        request.status = "approved"
        db.commit()

    cancelled = client.post(
        f"/api/v1/employee/me/requests/{created.json()['id']}/cancel",
        headers=_auth(token),
    )
    assert cancelled.status_code == 409
    assert cancelled.json()["error"]["code"] == "REQUEST_NOT_PENDING"


def test_employee_cannot_see_or_cancel_another_employee_request(client: TestClient) -> None:
    _, store, _ = _create_site_with_employees(client, ["alex", "blair"])
    alex_token = _employee_login(client, site_id=store["id"], username="alex")
    blair_token = _employee_login(client, site_id=store["id"], username="blair")

    created = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "end_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "reason": "Private",
        },
        headers=_auth(alex_token),
    )
    assert created.status_code == 201

    listed = client.get("/api/v1/employee/me/requests", headers=_auth(blair_token))
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    cancelled = client.post(
        f"/api/v1/employee/me/requests/{created.json()['id']}/cancel",
        headers=_auth(blair_token),
    )
    assert cancelled.status_code == 404
    assert cancelled.json()["error"]["code"] == "REQUEST_NOT_FOUND"


def test_employee_cannot_request_another_employee_draft_or_cancelled_shift(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff = _create_site_with_employees(client, ["alex", "blair"])
    alex_token = _employee_login(client, site_id=store["id"], username="alex")
    blair_shift = _published_shift(client, admin, store, staff["blair"])

    another_employee_shift = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": blair_shift["id"], "reason": "Try request"},
        headers=_auth(alex_token),
    )
    assert another_employee_shift.status_code == 404

    draft_shift = _create_shift(client, admin, store["id"], staff["alex"]["user"]["id"])
    draft_request = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": draft_shift["id"], "reason": "Need cover"},
        headers=_auth(alex_token),
    )
    assert draft_request.status_code == 404

    cancelled_shift = _published_shift(client, admin, store, staff["alex"])
    with test_session_local() as db:
        shift = db.get(Shift, uuid.UUID(cancelled_shift["id"]))
        assert shift is not None
        shift.status = "cancelled"
        db.commit()

    cancelled_request = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": cancelled_shift["id"], "reason": "Need cover"},
        headers=_auth(alex_token),
    )
    assert cancelled_request.status_code == 404


def test_swap_target_must_be_active_same_site_and_same_tenant(client: TestClient) -> None:
    admin, store, staff = _create_site_with_employees(client, ["alex", "blair"])
    shift = _published_shift(client, admin, store, staff["alex"])
    token = _employee_login(client, site_id=store["id"], username="alex")
    other_store = _create_store(client, admin, f"M-OTHER-{uuid.uuid4()}")
    other_site_staff = _create_staff_with_employee_account(
        client,
        admin,
        store_id=other_store["id"],
        username="casey",
    )
    _, _, other_tenant_staff = _create_site_with_employees(client, ["devon"])

    other_site = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shift["id"],
            "target_employee_account_id": other_site_staff["profile"]["employee_account_id"],
            "reason": "Need swap",
        },
        headers=_auth(token),
    )
    assert other_site.status_code == 404

    other_tenant = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shift["id"],
            "target_employee_account_id": other_tenant_staff["devon"]["profile"]["employee_account_id"],
            "reason": "Need swap",
        },
        headers=_auth(token),
    )
    assert other_tenant.status_code == 404

    self_target = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shift["id"],
            "target_employee_account_id": staff["alex"]["profile"]["employee_account_id"],
            "reason": "Need swap",
        },
        headers=_auth(token),
    )
    assert self_target.status_code == 422


def test_employee_request_auth_and_site_isolation(client: TestClient) -> None:
    admin, store, _ = _create_site_with_employees(client, ["alex"])
    token = _employee_login(client, site_id=store["id"], username="alex")
    other_store = _create_store(client, admin, f"M-OTHER-{uuid.uuid4()}")

    admin_on_employee = client.get(
        "/api/v1/employee/me/requests",
        headers=_auth(admin["token"]),
    )
    assert admin_on_employee.status_code == 401

    employee_on_admin = client.get("/api/v1/stores", headers=_auth(token))
    assert employee_on_admin.status_code == 401

    wrong_site = client.get(
        "/api/v1/employee/me/requests",
        params={"store_id": other_store["id"]},
        headers=_auth(token),
    )
    assert wrong_site.status_code == 404
    assert wrong_site.json()["error"]["code"] == "STORE_NOT_FOUND"


def test_request_validation_and_public_lookup_regression(client: TestClient) -> None:
    _, store, _ = _create_site_with_employees(client, ["alex"])
    token = _employee_login(client, site_id=store["id"], username="alex")

    past = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
            "end_date": (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat(),
            "reason": "Past",
        },
        headers=_auth(token),
    )
    assert past.status_code == 422

    reversed_dates = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (_future_monday().date() + timedelta(days=3)).isoformat(),
            "end_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "reason": "Bad dates",
        },
        headers=_auth(token),
    )
    assert reversed_dates.status_code == 422

    missing_reason = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "end_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "reason": "",
        },
        headers=_auth(token),
    )
    assert missing_reason.status_code == 422

    lookup = client.get("/api/v1/public/sites/lookup", params={"code": store["code"]})
    assert lookup.status_code == 200
    assert lookup.json() == {
        "site_id": store["id"],
        "site_code": store["code"],
        "site_name": store["name"],
    }
