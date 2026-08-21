from collections.abc import Generator
from datetime import date, timedelta
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.shift import Shift


PASSWORD = "password123"


def _current_or_next_monday() -> date:
    today = date.today()
    return today + timedelta(days=(-today.weekday()) % 7)


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_i3_shift_create.db"
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
            "full_name": "Phase I3 Staff",
            "role": "member",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_staff_profile(
    client: TestClient,
    admin: dict,
    *,
    user_id: str,
    store_id: str,
    display_name: str = "Phase I3 Staff",
    weekly_soft_cap: str | None = None,
) -> dict:
    payload = {
        "user_id": user_id,
        "store_id": store_id,
        "display_name": display_name,
        "job_title": "Cashier",
        "is_active": True,
    }
    if weekly_soft_cap is not None:
        payload["weekly_working_hour_soft_cap"] = weekly_soft_cap

    response = client.post(
        "/api/v1/staff",
        json=payload,
        headers=_auth(admin),
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
                    "open_time": "00:00",
                    "close_time": "23:59",
                    "is_closed": False,
                }
                for day in range(7)
            ],
        },
        headers=_auth(admin),
    )
    assert response.status_code == 200


def _create_site_shift(
    client: TestClient,
    admin: dict,
    *,
    site_id: str,
    assigned_employee_account_id: str | None = None,
    role_required: str | None = "Cashier",
    start_time: str = "2026-04-20T09:00:00Z",
    end_time: str = "2026-04-20T17:00:00Z",
) -> dict:
    response = client.post(
        f"/api/v1/sites/{site_id}/shifts",
        json={
            "assigned_employee_account_id": assigned_employee_account_id,
            "role_required": role_required,
            "start_time": start_time,
            "end_time": end_time,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def test_unauthenticated_create_shift_rejected(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/sites/{uuid.uuid4()}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
    )

    assert response.status_code == 401


def test_member_create_shift_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i3-rbac-{uuid.uuid4()}@example.com")
    member_email = f"phase-i3-rbac-member-{uuid.uuid4()}@example.com"
    member_user = _create_tenant_member(client, admin, member_email)
    member = {"token": create_access_token(member_user["id"])}
    store = _create_store(client, admin, f"I3-RBAC-{uuid.uuid4()}")

    response = client.post(
        f"/api/v1/sites/{store['id']}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(member),
    )

    assert response.status_code == 403


def test_admin_creates_open_draft_shift_and_weekly_rota_includes_it(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-i3-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-A-{uuid.uuid4()}")

    body = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=None,
        role_required="Cashier",
    )

    assert body["assigned_employee_account_id"] is None
    assert body["role_required"] == "cashier"
    assert body["start_time"].startswith("2026-04-20T09:00:00")
    assert body["end_time"].startswith("2026-04-20T17:00:00")

    with test_session_local() as db:
        shift = db.get(Shift, uuid.UUID(body["id"]))
        assert shift is not None
        assert shift.tenant_id == uuid.UUID(admin["active_tenant_id"])
        assert shift.store_id == uuid.UUID(store["id"])
        assert shift.status == "scheduled"
        assert shift.published_at is None

        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.tenant_id == uuid.UUID(admin["active_tenant_id"]),
                AuditLog.user_id == uuid.UUID(admin["id"]),
                AuditLog.action == "shift_created",
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == body["id"],
            )
        )
        assert audit_log is not None

    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-04-20"},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200
    assert weekly_response.json()["shifts"] == [body]


def test_admin_creates_cross_midnight_shift_with_exact_dated_read_back(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-overnight-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-ON-{uuid.uuid4()}")
    week_start = _current_or_next_monday()
    end_date = week_start + timedelta(days=1)

    created = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        start_time=f"{week_start.isoformat()}T22:00:00Z",
        end_time=f"{end_date.isoformat()}T06:00:00Z",
    )

    assert created["start_time"].startswith(f"{week_start.isoformat()}T22:00:00")
    assert created["end_time"].startswith(f"{end_date.isoformat()}T06:00:00")
    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": week_start.isoformat()},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200, weekly_response.text
    assert weekly_response.json()["shifts"] == [created]


def test_admin_creates_sunday_shift_ending_in_following_rota_week(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-sunday-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-SUN-{uuid.uuid4()}")
    week_start = _current_or_next_monday()
    sunday = week_start + timedelta(days=6)
    following_monday = week_start + timedelta(days=7)

    created = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        start_time=f"{sunday.isoformat()}T22:00:00Z",
        end_time=f"{following_monday.isoformat()}T06:00:00Z",
    )

    assert created["start_time"].startswith(f"{sunday.isoformat()}T22:00:00")
    assert created["end_time"].startswith(
        f"{following_monday.isoformat()}T06:00:00"
    )
    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": week_start.isoformat()},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200, weekly_response.text
    assert weekly_response.json()["shifts"] == [created]


def test_shift_wall_clock_times_round_trip_for_bst_and_gmt(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-wall-clock-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-WALL-{uuid.uuid4()}")

    summer_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        start_time="2026-06-12T13:00:00Z",
        end_time="2026-06-12T14:00:00Z",
    )
    assert summer_shift["start_time"].startswith("2026-06-12T13:00:00")
    assert summer_shift["end_time"].startswith("2026-06-12T14:00:00")

    update_response = client.patch(
        f"/api/v1/sites/{store['id']}/shifts/{summer_shift['id']}",
        json={
            "assigned_employee_account_id": None,
            "role_required": "Cashier",
            "start_time": "2026-06-12T15:00:00Z",
            "end_time": "2026-06-12T17:00:00Z",
        },
        headers=_auth(admin),
    )
    assert update_response.status_code == 200, update_response.text
    updated_summer_shift = update_response.json()
    assert updated_summer_shift["start_time"].startswith("2026-06-12T15:00:00")
    assert updated_summer_shift["end_time"].startswith("2026-06-12T17:00:00")

    summer_week_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-06-08"},
        headers=_auth(admin),
    )
    assert summer_week_response.status_code == 200, summer_week_response.text
    assert summer_week_response.json()["shifts"] == [updated_summer_shift]

    winter_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        start_time="2026-01-13T13:00:00Z",
        end_time="2026-01-13T14:00:00Z",
    )
    assert winter_shift["start_time"].startswith("2026-01-13T13:00:00")
    assert winter_shift["end_time"].startswith("2026-01-13T14:00:00")

    winter_week_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-01-12"},
        headers=_auth(admin),
    )
    assert winter_week_response.status_code == 200, winter_week_response.text
    assert winter_week_response.json()["shifts"] == [winter_shift]


def test_admin_creates_assigned_shift_for_staff_at_same_site(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-assign-{uuid.uuid4()}@example.com")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-member-{uuid.uuid4()}@example.com",
    )
    store = _create_store(client, admin, f"I3-B-{uuid.uuid4()}")
    _create_staff_profile(client, admin, user_id=member["id"], store_id=store["id"])

    body = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=member["id"],
    )

    assert body["assigned_employee_account_id"] == member["id"]


def test_weekly_rota_includes_non_blocking_weekly_soft_cap_status(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-soft-cap-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-CAPS-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])

    over_member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-over-cap-{uuid.uuid4()}@example.com",
    )
    under_member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-under-cap-{uuid.uuid4()}@example.com",
    )
    null_cap_member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-null-cap-{uuid.uuid4()}@example.com",
    )
    _create_staff_profile(
        client,
        admin,
        user_id=over_member["id"],
        store_id=store["id"],
        display_name="Over Cap",
        weekly_soft_cap="10.00",
    )
    _create_staff_profile(
        client,
        admin,
        user_id=under_member["id"],
        store_id=store["id"],
        display_name="Under Cap",
        weekly_soft_cap="8.00",
    )
    _create_staff_profile(
        client,
        admin,
        user_id=null_cap_member["id"],
        store_id=store["id"],
        display_name="Null Cap",
    )

    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=over_member["id"],
        start_time="2026-04-20T09:00:00Z",
        end_time="2026-04-20T14:00:00Z",
    )
    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=over_member["id"],
        start_time="2026-04-20T14:00:00Z",
        end_time="2026-04-20T18:00:00Z",
    )
    over_cap_create = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=over_member["id"],
        start_time="2026-04-20T18:00:00Z",
        end_time="2026-04-20T21:00:00Z",
    )
    update_response = client.patch(
        f"/api/v1/sites/{store['id']}/shifts/{over_cap_create['id']}",
        json={
            "assigned_employee_account_id": over_member["id"],
            "role_required": "Cashier",
            "start_time": "2026-04-20T18:00:00Z",
            "end_time": "2026-04-20T22:00:00Z",
        },
        headers=_auth(admin),
    )
    assert update_response.status_code == 200, update_response.text

    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=under_member["id"],
        start_time="2026-04-21T09:00:00Z",
        end_time="2026-04-21T15:00:00Z",
    )
    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=null_cap_member["id"],
        start_time="2026-04-22T09:00:00Z",
        end_time="2026-04-22T21:00:00Z",
    )
    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=None,
        start_time="2026-04-23T09:00:00Z",
        end_time="2026-04-23T21:00:00Z",
    )
    cancelled_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=over_member["id"],
        start_time="2026-04-24T09:00:00Z",
        end_time="2026-04-24T19:00:00Z",
    )
    cancel_response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{cancelled_shift['id']}/cancel",
        headers=_auth(admin),
    )
    assert cancel_response.status_code == 200, cancel_response.text
    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=over_member["id"],
        start_time="2026-04-27T09:00:00Z",
        end_time="2026-04-27T19:00:00Z",
    )

    other_store = _create_store(client, admin, f"I3-CAPS-OTHER-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, other_store["id"])
    other_site_member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-other-site-{uuid.uuid4()}@example.com",
    )
    _create_staff_profile(
        client,
        admin,
        user_id=other_site_member["id"],
        store_id=other_store["id"],
        display_name="Other Site",
        weekly_soft_cap="1.00",
    )
    _create_site_shift(
        client,
        admin,
        site_id=other_store["id"],
        assigned_employee_account_id=other_site_member["id"],
        start_time="2026-04-20T09:00:00Z",
        end_time="2026-04-20T17:00:00Z",
    )

    other_admin = _register_and_login(
        client,
        f"phase-i3-other-tenant-{uuid.uuid4()}@example.com",
    )
    other_tenant_store = _create_store(
        client,
        other_admin,
        f"I3-CAPS-TENANT-{uuid.uuid4()}",
    )
    other_tenant_member = _create_tenant_member(
        client,
        other_admin,
        f"phase-i3-other-tenant-member-{uuid.uuid4()}@example.com",
    )
    _create_staff_profile(
        client,
        other_admin,
        user_id=other_tenant_member["id"],
        store_id=other_tenant_store["id"],
        display_name="Other Tenant",
        weekly_soft_cap="1.00",
    )
    _create_site_shift(
        client,
        other_admin,
        site_id=other_tenant_store["id"],
        assigned_employee_account_id=other_tenant_member["id"],
        start_time="2026-04-20T09:00:00Z",
        end_time="2026-04-20T17:00:00Z",
    )

    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-04-20"},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200, weekly_response.text
    weekly_body = weekly_response.json()
    status_by_user = {
        item["user_id"]: item for item in weekly_body["weekly_hour_status"]
    }

    assert set(status_by_user) == {
        over_member["id"],
        under_member["id"],
        null_cap_member["id"],
    }
    assert status_by_user[over_member["id"]] == {
        "user_id": over_member["id"],
        "scheduled_hours": 13.0,
        "weekly_soft_cap": 10.0,
        "exceeded": True,
    }
    assert status_by_user[under_member["id"]] == {
        "user_id": under_member["id"],
        "scheduled_hours": 6.0,
        "weekly_soft_cap": 8.0,
        "exceeded": False,
    }
    assert status_by_user[null_cap_member["id"]] == {
        "user_id": null_cap_member["id"],
        "scheduled_hours": 12.0,
        "weekly_soft_cap": None,
        "exceeded": False,
    }

    publish_response = client.post(
        f"/api/v1/sites/{store['id']}/rota/publish",
        json={"week_start": "2026-04-20"},
        headers=_auth(admin),
    )
    assert publish_response.status_code == 200, publish_response.text
    publish_status_by_user = {
        item["user_id"]: item for item in publish_response.json()["weekly_hour_status"]
    }
    assert publish_status_by_user[over_member["id"]]["exceeded"] is True


def test_weekly_soft_cap_duration_uses_wall_clock_hour_during_bst(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-bst-cap-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-BST-CAP-{uuid.uuid4()}")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-bst-cap-member-{uuid.uuid4()}@example.com",
    )
    _create_staff_profile(
        client,
        admin,
        user_id=member["id"],
        store_id=store["id"],
        display_name="BST Cap",
        weekly_soft_cap="0.50",
    )
    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=member["id"],
        start_time="2026-06-12T13:00:00Z",
        end_time="2026-06-12T14:00:00Z",
    )

    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-06-08"},
        headers=_auth(admin),
    )

    assert weekly_response.status_code == 200, weekly_response.text
    assert weekly_response.json()["weekly_hour_status"] == [
        {
            "user_id": member["id"],
            "scheduled_hours": 1.0,
            "weekly_soft_cap": 0.5,
            "exceeded": True,
        }
    ]


def test_invalid_time_range_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i3-time-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-C-{uuid.uuid4()}")

    response = client.post(
        f"/api/v1/sites/{store['id']}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T17:00:00Z",
            "end_time": "2026-04-20T09:00:00Z",
        },
        headers=_auth(admin),
    )

    assert response.status_code == 422


def test_cross_tenant_site_create_rejected(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-i3-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-i3-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a, f"I3-D-{uuid.uuid4()}")

    response = client.post(
        f"/api/v1/sites/{store_a['id']}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(admin_b),
    )

    assert response.status_code == 404


def test_assigned_staff_from_wrong_site_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i3-wrong-site-{uuid.uuid4()}@example.com")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-wrong-site-member-{uuid.uuid4()}@example.com",
    )
    store_a = _create_store(client, admin, f"I3-E-{uuid.uuid4()}")
    store_b = _create_store(client, admin, f"I3-F-{uuid.uuid4()}")
    _create_staff_profile(client, admin, user_id=member["id"], store_id=store_b["id"])

    response = client.post(
        f"/api/v1/sites/{store_a['id']}/shifts",
        json={
            "assigned_employee_account_id": member["id"],
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(admin),
    )

    assert response.status_code == 400
