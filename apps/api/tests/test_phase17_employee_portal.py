from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User


PASSWORD = "password123"


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
        "id": uuid.UUID(register_body["id"]),
        "active_tenant_id": uuid.UUID(register_body["active_tenant_id"]),
        "token": token,
    }


def _set_membership(
    test_session_local,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    set_active_tenant: bool = True,
) -> None:
    db = test_session_local()
    try:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.user_id == user_id,
                TenantUser.tenant_id == tenant_id,
            )
        )
        if membership is None:
            db.add(TenantUser(user_id=user_id, tenant_id=tenant_id, role=role))
        else:
            membership.role = role

        user = db.get(User, user_id)
        assert user is not None
        if set_active_tenant:
            user.active_tenant_id = tenant_id
        db.commit()
    finally:
        db.close()


def _create_store(client: TestClient, token: str, code: str) -> str:
    response = client.post(
        "/api/v1/stores",
        json={"code": code, "name": f"Store {code}", "timezone": "UTC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_staff_profile(
    client: TestClient,
    *,
    token: str,
    user_id: uuid.UUID,
    store_id: str,
    hourly_rate: str | None = None,
    pay_type: str | None = None,
) -> str:
    payload: dict[str, str | bool] = {
        "user_id": str(user_id),
        "store_id": store_id,
        "display_name": f"User {user_id}",
        "is_active": True,
    }
    if hourly_rate is not None:
        payload["hourly_rate"] = hourly_rate
    if pay_type is not None:
        payload["pay_type"] = pay_type
    response = client.post(
        "/api/v1/staff",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_shift(
    client: TestClient,
    *,
    token: str,
    store_id: str,
    start_at: str,
    end_at: str,
    assigned_user_id: str | None = None,
) -> str:
    payload: dict[str, str] = {
        "store_id": store_id,
        "start_at": start_at,
        "end_at": end_at,
    }
    if assigned_user_id is not None:
        payload["assigned_user_id"] = assigned_user_id
    response = client.post(
        "/api/v1/shifts",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _publish_range(client: TestClient, *, token: str, store_id: str, from_at: str, to_at: str) -> None:
    response = client.post(
        "/api/v1/shifts/publish",
        json={"store_id": store_id, "from": from_at, "to": to_at},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def _put_hour_target(
    client: TestClient,
    *,
    token: str,
    user_id: uuid.UUID,
    week_start: str,
    target_hours: int,
    store_id: str | None = None,
) -> None:
    payload: dict[str, str | int | None] = {
        "user_id": str(user_id),
        "week_start": week_start,
        "min_hours": 0,
        "max_hours": 60,
        "target_hours": target_hours,
        "store_id": store_id,
    }
    response = client.put(
        "/api/v1/hour-targets",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in [200, 201]


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase17_employee_portal.db"
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


def test_employee_home_context_and_store_resolution_path_a(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-home-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-home-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")

    store_primary = _create_store(client, admin["token"], "P17-HOME-001")
    store_other = _create_store(client, admin["token"], "P17-HOME-002")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_primary)

    response = client.get(
        "/api/v1/employee/home",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["available_stores"]) == 1
    assert body["selected_store"]["id"] == store_primary

    invalid_store = client.get(
        "/api/v1/employee/home",
        params={"week_start": "2026-04-06", "store_id": store_other},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert invalid_store.status_code == 404


def test_employee_my_rota_returns_only_own_published_shifts(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-rota-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-rota-member-{uuid.uuid4()}@example.com")
    other = _register_and_login(client, f"p17-rota-other-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    _set_membership(test_session_local, user_id=other["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-ROTA-001")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)
    _create_staff_profile(client, token=admin["token"], user_id=other["id"], store_id=store_id)

    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-04-06T17:00:00Z",
        end_at="2026-04-06T21:00:00Z",
        assigned_user_id=str(other["id"]),
    )
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-04-07T09:00:00Z",
        end_at="2026-04-07T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    _publish_range(
        client,
        token=admin["token"],
        store_id=store_id,
        from_at="2026-04-06T00:00:00Z",
        to_at="2026-04-07T00:00:00Z",
    )

    response = client.get(
        "/api/v1/employee/me/rota",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    shifts = response.json()["shifts"]
    assert len(shifts) == 1
    assert shifts[0]["assigned_user_id"] == str(member["id"])
    assert shifts[0]["start_at"].startswith("2026-04-06")


def test_employee_home_weekly_rota_store_scoped_and_published_only(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-weekly-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-weekly-member-{uuid.uuid4()}@example.com")
    colleague = _register_and_login(client, f"p17-weekly-colleague-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    _set_membership(test_session_local, user_id=colleague["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_a = _create_store(client, admin["token"], "P17-WEEK-A")
    store_b = _create_store(client, admin["token"], "P17-WEEK-B")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_a)
    _create_staff_profile(client, token=admin["token"], user_id=colleague["id"], store_id=store_a)

    _create_shift(
        client,
        token=admin["token"],
        store_id=store_a,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        assigned_user_id=str(colleague["id"]),
    )
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_a,
        start_at="2026-04-07T09:00:00Z",
        end_at="2026-04-07T17:00:00Z",
        assigned_user_id=str(colleague["id"]),
    )
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_b,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        assigned_user_id=str(colleague["id"]),
    )
    _publish_range(
        client,
        token=admin["token"],
        store_id=store_a,
        from_at="2026-04-06T00:00:00Z",
        to_at="2026-04-07T00:00:00Z",
    )
    _publish_range(
        client,
        token=admin["token"],
        store_id=store_b,
        from_at="2026-04-06T00:00:00Z",
        to_at="2026-04-07T00:00:00Z",
    )

    response = client.get(
        "/api/v1/employee/home",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    weekly_rota = response.json()["weekly_rota"]
    assert len(weekly_rota) == 1
    assert weekly_rota[0]["store_id"] == store_a
    assert weekly_rota[0]["start_at"].startswith("2026-04-06")


def test_employee_cross_tenant_data_hidden(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"p17-iso-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p17-iso-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p17-iso-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member_a["id"], tenant_id=admin_a["active_tenant_id"], role="member")
    store_a = _create_store(client, admin_a["token"], "P17-ISO-A")
    store_b = _create_store(client, admin_b["token"], "P17-ISO-B")
    _create_staff_profile(client, token=admin_a["token"], user_id=member_a["id"], store_id=store_a)

    response = client.get(
        "/api/v1/employee/me/rota",
        params={"week_start": "2026-04-06", "store_id": store_b},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert response.status_code == 404


def test_employee_labour_intelligence_truthful_calculation(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-li-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-li-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-LI-001")
    _create_staff_profile(
        client,
        token=admin["token"],
        user_id=member["id"],
        store_id=store_id,
        hourly_rate="10.00",
        pay_type="hourly",
    )

    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-09T09:00:00Z",
        end_at="2026-03-09T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-10T09:00:00Z",
        end_at="2026-03-10T13:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-15T09:00:00Z",
        end_at="2026-03-15T15:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    _publish_range(
        client,
        token=admin["token"],
        store_id=store_id,
        from_at="2026-03-01T00:00:00Z",
        to_at="2026-04-01T00:00:00Z",
    )
    _put_hour_target(
        client,
        token=admin["token"],
        user_id=member["id"],
        week_start="2026-03-09",
        target_hours=20,
        store_id=store_id,
    )
    _put_hour_target(
        client,
        token=admin["token"],
        user_id=member["id"],
        week_start="2026-03-16",
        target_hours=20,
        store_id=store_id,
    )

    response = client.get(
        "/api/v1/employee/me/labour-intelligence",
        params={"week_start": "2026-03-09"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scheduled_hours_this_week"] == 18.0
    assert body["scheduled_hours_this_month"] == 18.0
    assert body["estimated_pay_this_week"] == 180.0
    assert body["estimated_pay_this_month"] == 180.0
    assert body["monthly_progress_percent"] == 45.0


def test_employee_availability_crud_self_only(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-av-admin-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p17-av-member-a-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"p17-av-member-b-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member_a["id"], tenant_id=admin["active_tenant_id"], role="member")
    _set_membership(test_session_local, user_id=member_b["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-AV-001")
    _create_staff_profile(client, token=admin["token"], user_id=member_a["id"], store_id=store_id)
    _create_staff_profile(client, token=admin["token"], user_id=member_b["id"], store_id=store_id)

    create_response = client.post(
        "/api/v1/employee/me/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-06",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "type": "available",
            "notes": "Available",
        },
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert create_response.status_code == 201
    entry_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    delete_as_other = client.delete(
        f"/api/v1/employee/me/availability/{entry_id}",
        headers={"Authorization": f"Bearer {member_b['token']}"},
    )
    assert delete_as_other.status_code == 404

    delete_as_owner = client.delete(
        f"/api/v1/employee/me/availability/{entry_id}",
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert delete_as_owner.status_code == 200


def test_employee_swaps_create_and_list_follow_existing_rules(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-sw-admin-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p17-sw-member-a-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"p17-sw-member-b-{uuid.uuid4()}@example.com")
    outsider = _register_and_login(client, f"p17-sw-outsider-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member_a["id"], tenant_id=admin["active_tenant_id"], role="member")
    _set_membership(test_session_local, user_id=member_b["id"], tenant_id=admin["active_tenant_id"], role="member")
    _set_membership(test_session_local, user_id=outsider["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-SW-001")
    _create_staff_profile(client, token=admin["token"], user_id=member_a["id"], store_id=store_id)
    _create_staff_profile(client, token=admin["token"], user_id=member_b["id"], store_id=store_id)
    _create_staff_profile(client, token=admin["token"], user_id=outsider["id"], store_id=store_id)

    shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-06-20T09:00:00Z",
        end_at="2026-06-20T17:00:00Z",
        assigned_user_id=str(member_a["id"]),
    )
    _publish_range(
        client,
        token=admin["token"],
        store_id=store_id,
        from_at="2026-06-20T00:00:00Z",
        to_at="2026-06-21T00:00:00Z",
    )

    valid_create = client.post(
        "/api/v1/employee/me/swaps",
        json={
            "shift_id": shift_id,
            "target_user_id": str(member_b["id"]),
            "notes": "Please swap",
        },
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert valid_create.status_code == 201
    assert valid_create.json()["type"] == "swap"
    assert valid_create.json()["status"] == "pending_target"

    listed = client.get(
        "/api/v1/employee/me/swaps",
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    invalid_create = client.post(
        "/api/v1/employee/me/swaps",
        json={
            "shift_id": shift_id,
            "target_user_id": str(member_b["id"]),
        },
        headers={"Authorization": f"Bearer {outsider['token']}"},
    )
    assert invalid_create.status_code == 400


def test_employee_missing_staff_profile_returns_404(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-missing-staff-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-missing-staff-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")

    response = client.get(
        "/api/v1/employee/home",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 404


def test_employee_home_empty_state_contract_stable(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-empty-home-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-empty-home-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-EMPTY-HOME")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)

    response = client.get(
        "/api/v1/employee/home",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["available_stores"], list)
    assert isinstance(body["my_rota"], list)
    assert isinstance(body["weekly_rota"], list)
    assert isinstance(body["today_operators"], list)
    assert body["today_tasks"] is None
    assert "labour_intelligence" in body
    assert body["my_rota"] == []
    assert body["weekly_rota"] == []
    assert body["today_operators"] == []


def test_employee_labour_intelligence_missing_hourly_rate_and_target(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-li-null-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-li-null-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-LI-NULL")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)

    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-09T09:00:00Z",
        end_at="2026-03-09T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    _publish_range(
        client,
        token=admin["token"],
        store_id=store_id,
        from_at="2026-03-01T00:00:00Z",
        to_at="2026-04-01T00:00:00Z",
    )

    response = client.get(
        "/api/v1/employee/me/labour-intelligence",
        params={"week_start": "2026-03-09"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scheduled_hours_this_week"] == 8.0
    assert body["estimated_pay_this_week"] is None
    assert body["estimated_pay_this_month"] is None
    assert body["monthly_progress_percent"] is None


def test_employee_invalid_store_returns_404_across_endpoints(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-invalid-store-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-invalid-store-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-STORE-OK")
    store_other = _create_store(client, admin["token"], "P17-STORE-BAD")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)

    endpoints = [
        ("/api/v1/employee/home", {"week_start": "2026-04-06", "store_id": store_other}),
        ("/api/v1/employee/me/rota", {"week_start": "2026-04-06", "store_id": store_other}),
        ("/api/v1/employee/me/labour-intelligence", {"week_start": "2026-04-06", "store_id": store_other}),
        ("/api/v1/employee/me/availability", {"week_start": "2026-04-06", "store_id": store_other}),
        ("/api/v1/employee/me/swaps", {"store_id": store_other}),
    ]
    for path, params in endpoints:
        response = client.get(path, params=params, headers={"Authorization": f"Bearer {member['token']}"})
        assert response.status_code == 404


def test_employee_profile_without_roles_and_empty_lists(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-profile-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-profile-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-PROFILE")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)

    profile_response = client.get(
        "/api/v1/employee/me/profile",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["roles"] == []

    swaps_response = client.get(
        "/api/v1/employee/me/swaps",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert swaps_response.status_code == 200
    assert swaps_response.json()["items"] == []

    availability_response = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert availability_response.status_code == 200
    assert availability_response.json()["items"] == []


def test_employee_create_swap_blocks_unpublished_shift(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-swap-unpub-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-swap-unpub-member-{uuid.uuid4()}@example.com")
    target = _register_and_login(client, f"p17-swap-unpub-target-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    _set_membership(test_session_local, user_id=target["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-SWAP-UNPUB")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)
    _create_staff_profile(client, token=admin["token"], user_id=target["id"], store_id=store_id)

    shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-06-20T09:00:00Z",
        end_at="2026-06-20T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    response = client.post(
        "/api/v1/employee/me/swaps",
        json={"shift_id": shift_id, "target_user_id": str(target["id"])},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 404


def test_employee_my_rota_empty_when_no_published_shifts(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p17-rota-empty-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p17-rota-empty-member-{uuid.uuid4()}@example.com")
    _set_membership(test_session_local, user_id=member["id"], tenant_id=admin["active_tenant_id"], role="member")
    store_id = _create_store(client, admin["token"], "P17-ROTA-EMPTY")
    _create_staff_profile(client, token=admin["token"], user_id=member["id"], store_id=store_id)
    _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )

    response = client.get(
        "/api/v1/employee/me/rota",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 200
    assert response.json()["shifts"] == []
