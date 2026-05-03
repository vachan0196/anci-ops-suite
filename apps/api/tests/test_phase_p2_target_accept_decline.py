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
from apps.api.models.shift import Shift
from apps.api.models.shift_request import ShiftRequest


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_p2_target_accept_decline.db"
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
            "email": f"phase-p2-{username}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Phase P2 {username}",
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
            "display_name": f"Phase P2 {username}",
            "job_title": "Cashier",
            "phone": "01234 567890",
            "hourly_rate": "12.50",
            "pay_type": "hourly",
            "rtw_status": "verified",
            "notes": "private note",
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


def _setup_site(client: TestClient) -> tuple[dict, dict, dict[str, dict], datetime, dict]:
    admin = _register_and_login(client, f"phase-p2-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"P2-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    staff = {
        username: _create_staff_with_employee_account(
            client,
            admin,
            store_id=store["id"],
            username=username,
        )
        for username in ["alex", "blair", "casey"]
    }
    week = _future_monday()
    shift = _create_shift(
        client,
        admin,
        store["id"],
        staff["alex"]["user"]["id"],
        week=week,
    )
    _publish_rota(client, admin, store["id"], week)
    return admin, store, staff, week, shift


def _create_targeted_request(
    client: TestClient,
    *,
    store: dict,
    requester_username: str,
    shift_id: str,
    target_employee_account_id: str,
    request_type: str,
) -> dict:
    requester_token = _employee_login(client, site_id=store["id"], username=requester_username)
    response = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": request_type,
            "shift_id": shift_id,
            "target_employee_account_id": target_employee_account_id,
            "reason": f"Please {request_type} this shift",
        },
        headers=_auth(requester_token),
    )
    assert response.status_code == 201
    return response.json()


def test_target_employee_lists_only_own_inbound_cover_and_swap_requests(
    client: TestClient,
) -> None:
    _admin, store, staff, _week, shift = _setup_site(client)
    cover = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    swap = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="swap",
    )

    blair_token = _employee_login(client, site_id=store["id"], username="blair")
    response = client.get("/api/v1/employee/me/inbound-requests", headers=_auth(blair_token))

    assert response.status_code == 200
    body = response.json()
    assert body["selected_store"]["id"] == store["id"]
    assert {item["id"] for item in body["items"]} == {cover["id"], swap["id"]}
    assert {item["request_type"] for item in body["items"]} == {"cover", "swap"}
    first = body["items"][0]
    assert first["requester_display_name"] == "Phase P2 alex"
    assert first["reason"]
    assert first["shift"]["id"] == shift["id"]
    assert first["shift"]["role_required"] == "cashier"
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
    assert forbidden_fields.isdisjoint(first.keys())
    assert forbidden_fields.isdisjoint(first["shift"].keys())

    for username in ["alex", "casey"]:
        token = _employee_login(client, site_id=store["id"], username=username)
        other_response = client.get(
            "/api/v1/employee/me/inbound-requests",
            headers=_auth(token),
        )
        assert other_response.status_code == 200
        assert other_response.json()["items"] == []


def test_cross_site_cross_tenant_and_admin_tokens_cannot_see_inbound_requests(
    client: TestClient,
) -> None:
    admin, store, staff, _week, shift = _setup_site(client)
    _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    other_store = _create_store(client, admin, f"P2O-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, other_store["id"])
    _create_staff_with_employee_account(
        client,
        admin,
        store_id=other_store["id"],
        username="devon",
    )
    other_tenant_admin = _register_and_login(
        client,
        f"phase-p2-other-admin-{uuid.uuid4()}@example.com",
    )
    other_tenant_store = _create_store(client, other_tenant_admin, f"P2X-{uuid.uuid4()}")
    _configure_opening_hours(client, other_tenant_admin, other_tenant_store["id"])
    _create_staff_with_employee_account(
        client,
        other_tenant_admin,
        store_id=other_tenant_store["id"],
        username="ellis",
    )

    other_site_token = _employee_login(client, site_id=other_store["id"], username="devon")
    assert client.get(
        "/api/v1/employee/me/inbound-requests",
        headers=_auth(other_site_token),
    ).json()["items"] == []

    other_tenant_token = _employee_login(
        client,
        site_id=other_tenant_store["id"],
        username="ellis",
    )
    assert client.get(
        "/api/v1/employee/me/inbound-requests",
        headers=_auth(other_tenant_token),
    ).json()["items"] == []

    admin_response = client.get(
        "/api/v1/employee/me/inbound-requests",
        headers=_auth(admin["token"]),
    )
    assert admin_response.status_code in {401, 403}


@pytest.mark.parametrize("request_type", ["cover", "swap"])
@pytest.mark.parametrize("decision", ["accept", "decline"])
def test_target_employee_can_accept_or_decline_without_rota_mutation(
    client: TestClient,
    test_session_local,
    request_type: str,
    decision: str,
) -> None:
    _admin, store, staff, _week, shift = _setup_site(client)
    created = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type=request_type,
    )
    with test_session_local() as db:
        original_shift = db.get(Shift, uuid.UUID(shift["id"]))
        original_assignee = original_shift.assigned_user_id
        original_status = original_shift.status

    blair_token = _employee_login(client, site_id=store["id"], username="blair")
    response = client.post(
        f"/api/v1/employee/me/inbound-requests/{created['id']}/{decision}",
        json={"decline_reason": "No thanks"} if decision == "decline" else None,
        headers=_auth(blair_token),
    )

    assert response.status_code == 200
    expected_status = "target_accepted" if decision == "accept" else "target_declined"
    body = response.json()
    assert body["id"] == created["id"]
    assert body["status"] == expected_status
    assert body["rota_updated"] is False
    with test_session_local() as db:
        request = db.get(ShiftRequest, uuid.UUID(created["id"]))
        changed_shift = db.get(Shift, uuid.UUID(shift["id"]))
        assert request.status == expected_status
        assert request.updated_at is not None
        assert changed_shift.assigned_user_id == original_assignee
        assert changed_shift.status == original_status


@pytest.mark.parametrize("decision", ["accept", "decline"])
def test_non_target_and_non_pending_requests_cannot_be_decided(
    client: TestClient,
    test_session_local,
    decision: str,
) -> None:
    _admin, store, staff, _week, shift = _setup_site(client)
    created = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    casey_token = _employee_login(client, site_id=store["id"], username="casey")
    non_target = client.post(
        f"/api/v1/employee/me/inbound-requests/{created['id']}/{decision}",
        headers=_auth(casey_token),
    )
    assert non_target.status_code == 404
    assert non_target.json()["error"]["code"] == "REQUEST_NOT_FOUND"

    for status in ["cancelled", "rejected", "approved", "target_accepted", "target_declined"]:
        with test_session_local() as db:
            request = db.get(ShiftRequest, uuid.UUID(created["id"]))
            request.status = status
            db.commit()

        blair_token = _employee_login(client, site_id=store["id"], username="blair")
        response = client.post(
            f"/api/v1/employee/me/inbound-requests/{created['id']}/{decision}",
            headers=_auth(blair_token),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "REQUEST_NOT_PENDING"
