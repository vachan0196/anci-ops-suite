from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.shift import Shift
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


def _create_staff_profile(client: TestClient, token: str, user_id: uuid.UUID, store_id: str) -> str:
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": str(user_id),
            "store_id": store_id,
            "display_name": f"User {user_id}",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_staff_role(client: TestClient, token: str, staff_id: str, role: str) -> None:
    response = client.post(
        f"/api/v1/staff/{staff_id}/roles",
        json={"role": role},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def _create_shift(
    client: TestClient,
    token: str,
    *,
    store_id: str,
    start_at: str,
    end_at: str,
    required_role: str | None = None,
) -> str:
    payload = {
        "store_id": store_id,
        "start_at": start_at,
        "end_at": end_at,
    }
    if required_role is not None:
        payload["required_role"] = required_role
    response = client.post(
        "/api/v1/shifts",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_availability(
    client: TestClient,
    *,
    token: str,
    week_start: str,
    date: str,
    start_time: str,
    end_time: str,
) -> None:
    response = client.post(
        "/api/v1/availability",
        json={
            "week_start": week_start,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "type": "available_extra",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase16_role_constraints_and_overrides.db"
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


def test_staff_roles_admin_crud_and_normalization(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p16-staff-role-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p16-staff-role-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "P16-SR-001")
    staff_id = _create_staff_profile(client, admin["token"], member["id"], store_id)

    add_response = client.post(
        f"/api/v1/staff/{staff_id}/roles",
        json={"role": " Cashier "},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert add_response.status_code == 200
    assert add_response.json()["role"] == "cashier"

    list_response = client.get(
        f"/api/v1/staff/{staff_id}/roles",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert list_response.status_code == 200
    assert [item["role"] for item in list_response.json()] == ["cashier"]

    delete_response = client.delete(
        f"/api/v1/staff/{staff_id}/roles/cashier",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert delete_response.status_code == 204


def test_staff_roles_cross_tenant_returns_404(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"p16-staff-role-iso-admin-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p16-staff-role-iso-admin-b-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p16-staff-role-iso-member-a-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin_a["token"], "P16-SR-ISO")
    staff_id = _create_staff_profile(client, admin_a["token"], member_a["id"], store_id)
    _add_staff_role(client, admin_a["token"], staff_id, "cashier")

    list_response = client.get(
        f"/api/v1/staff/{staff_id}/roles",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert list_response.status_code == 404

    add_response = client.post(
        f"/api/v1/staff/{staff_id}/roles",
        json={"role": "supervisor"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert add_response.status_code == 404

    delete_response = client.delete(
        f"/api/v1/staff/{staff_id}/roles/cashier",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert delete_response.status_code == 404


def test_recommendation_filters_by_required_role(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p16-rec-role-admin-{uuid.uuid4()}@example.com")
    member_cashier = _register_and_login(client, f"p16-rec-role-cashier-{uuid.uuid4()}@example.com")
    member_supervisor = _register_and_login(client, f"p16-rec-role-supervisor-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_cashier["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    _set_membership(
        test_session_local,
        user_id=member_supervisor["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin["token"], "P16-REC-ROLE")
    staff_cashier = _create_staff_profile(client, admin["token"], member_cashier["id"], store_id)
    staff_supervisor = _create_staff_profile(client, admin["token"], member_supervisor["id"], store_id)
    _add_staff_role(client, admin["token"], staff_cashier, "cashier")
    _add_staff_role(client, admin["token"], staff_cashier, "supervisor")
    _add_staff_role(client, admin["token"], staff_supervisor, "supervisor")

    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        required_role="cashier",
    )
    _create_availability(
        client,
        token=member_cashier["token"],
        week_start="2026-04-06",
        date="2026-04-06",
        start_time="09:00:00",
        end_time="17:00:00",
    )
    _create_availability(
        client,
        token=member_supervisor["token"],
        week_start="2026-04-06",
        date="2026-04-06",
        start_time="09:00:00",
        end_time="17:00:00",
    )

    response = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert response.status_code == 201

    detail_response = client.get(
        f"/api/v1/rota-recommendations/{response.json()['draft_id']}",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["items"][0]["proposed_user_id"] == str(member_cashier["id"])


def test_manager_override_sets_flags_and_audit_fields(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p16-override-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p16-override-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "P16-OVR-001")
    staff_id = _create_staff_profile(client, admin["token"], member["id"], store_id)
    _add_staff_role(client, admin["token"], staff_id, "supervisor")

    shift_id = _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        required_role="cashier",
    )

    assign_response = client.patch(
        f"/api/v1/shifts/{shift_id}/assign",
        json={
            "assigned_user_id": str(member["id"]),
            "override_reason": "Urgent manager coverage",
            "mode": "single",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert assign_response.status_code == 200
    payload = assign_response.json()["shift"]
    assert payload["role_override"] is True
    assert payload["availability_override"] is True
    assert payload["overridden_by_user_id"] == str(admin["id"])
    assert payload["overridden_at"] is not None


def test_override_recalibrate_returns_recommendations_for_remaining_unassigned(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p16-recalibrate-admin-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p16-recalibrate-member-a-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"p16-recalibrate-member-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    _set_membership(
        test_session_local,
        user_id=member_b["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "P16-RECAL-001")
    staff_a = _create_staff_profile(client, admin["token"], member_a["id"], store_id)
    staff_b = _create_staff_profile(client, admin["token"], member_b["id"], store_id)
    _add_staff_role(client, admin["token"], staff_a, "cashier")
    _add_staff_role(client, admin["token"], staff_b, "cashier")
    _create_availability(
        client,
        token=member_a["token"],
        week_start="2026-04-06",
        date="2026-04-06",
        start_time="09:00:00",
        end_time="17:00:00",
    )
    _create_availability(
        client,
        token=member_b["token"],
        week_start="2026-04-06",
        date="2026-04-06",
        start_time="09:00:00",
        end_time="21:00:00",
    )

    shift_one = _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        required_role="cashier",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T17:00:00Z",
        end_at="2026-04-06T21:00:00Z",
        required_role="cashier",
    )

    response = client.patch(
        f"/api/v1/shifts/{shift_one}/assign",
        json={
            "assigned_user_id": str(member_a["id"]),
            "override_reason": "Manual coverage adjustment",
            "mode": "recalibrate",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert recommendations is not None
    assert "draft" in recommendations
    assert "items" in recommendations
    assert recommendations["shifts_considered"] >= 1


def test_override_cross_tenant_404(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"p16-override-iso-admin-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p16-override-iso-admin-b-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p16-override-iso-member-a-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin_a["token"], "P16-OVR-ISO")
    shift_id = _create_shift(
        client,
        admin_a["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )

    response = client.patch(
        f"/api/v1/shifts/{shift_id}/assign",
        json={
            "assigned_user_id": str(member_a["id"]),
            "mode": "single",
        },
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert response.status_code == 404


def test_override_marks_availability_mismatch_with_role_match(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p16-override-avail-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p16-override-avail-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "P16-OVR-AVL")
    staff_id = _create_staff_profile(client, admin["token"], member["id"], store_id)
    _add_staff_role(client, admin["token"], staff_id, "cashier")

    shift_id = _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
        required_role="cashier",
    )

    response = client.patch(
        f"/api/v1/shifts/{shift_id}/assign",
        json={
            "assigned_user_id": str(member["id"]),
            "mode": "single",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert response.status_code == 200
    shift_payload = response.json()["shift"]
    assert shift_payload["role_override"] is False
    assert shift_payload["availability_override"] is True

    db = test_session_local()
    try:
        shift = db.get(Shift, uuid.UUID(shift_id))
        assert shift is not None
        assert shift.overridden_by_user_id == admin["id"]
        assert shift.overridden_at is not None
    finally:
        db.close()
