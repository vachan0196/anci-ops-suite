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
from apps.api.models.shift import Shift
from apps.api.models.shift_request import ShiftRequest
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


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_shift_requests.db"
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


def test_member_create_pickup_and_audit(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"sr-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"sr-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "SR-001")
    open_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-20T09:00:00Z",
        end_at="2026-03-20T17:00:00Z",
    )

    create_request_response = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": open_shift_id, "type": "pickup", "notes": "Can cover this shift"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert create_request_response.status_code == 201
    request_id = create_request_response.json()["id"]
    assert create_request_response.json()["status"] == "pending"

    member_list_response = client.get(
        "/api/v1/shift-requests",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_list_response.status_code == 200
    assert len(member_list_response.json()) == 1

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift_request",
                AuditLog.entity_id == str(request_id),
            )
        ).all()
        assert [log.action for log in logs] == ["create"]
    finally:
        db.close()


def test_member_create_validation_for_pickup_and_drop(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"sr-admin-v-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"sr-member-v-{uuid.uuid4()}@example.com")
    other_member = _register_and_login(client, f"sr-member-other-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    _set_membership(
        test_session_local,
        user_id=other_member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin["token"], "SR-002")
    assigned_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-21T09:00:00Z",
        end_at="2026-03-21T17:00:00Z",
        assigned_user_id=str(other_member["id"]),
    )
    member_own_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-22T09:00:00Z",
        end_at="2026-03-22T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )

    invalid_pickup = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": assigned_shift_id, "type": "pickup"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert invalid_pickup.status_code == 400

    invalid_drop = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": assigned_shift_id, "type": "drop"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert invalid_drop.status_code == 400

    valid_drop = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": member_own_shift_id, "type": "drop"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert valid_drop.status_code == 201


def test_admin_list_approve_pickup_and_drop_and_reject(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"sr-admin-a-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"sr-member-a-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "SR-003")

    open_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-23T09:00:00Z",
        end_at="2026-03-23T17:00:00Z",
    )
    assigned_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-24T09:00:00Z",
        end_at="2026-03-24T17:00:00Z",
        assigned_user_id=str(member["id"]),
    )
    reject_target_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-03-25T09:00:00Z",
        end_at="2026-03-25T17:00:00Z",
    )

    pickup_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": open_shift_id, "type": "pickup"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert pickup_request.status_code == 201
    pickup_request_id = pickup_request.json()["id"]

    drop_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": assigned_shift_id, "type": "drop"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert drop_request.status_code == 201
    drop_request_id = drop_request.json()["id"]

    reject_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": reject_target_shift_id, "type": "pickup"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert reject_request.status_code == 201
    reject_request_id = reject_request.json()["id"]

    admin_list = client.get(
        "/api/v1/shift-requests",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert admin_list.status_code == 200
    assert len(admin_list.json()) == 3

    approve_pickup = client.post(
        f"/api/v1/shift-requests/{pickup_request_id}/approve",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert approve_pickup.status_code == 200
    assert approve_pickup.json()["status"] == "approved"

    approve_drop = client.post(
        f"/api/v1/shift-requests/{drop_request_id}/approve",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert approve_drop.status_code == 200
    assert approve_drop.json()["status"] == "approved"

    reject_pending = client.post(
        f"/api/v1/shift-requests/{reject_request_id}/reject",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert reject_pending.status_code == 200
    assert reject_pending.json()["status"] == "rejected"

    cancel_after_approved = client.post(
        f"/api/v1/shift-requests/{pickup_request_id}/cancel",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert cancel_after_approved.status_code == 400

    cancel_after_rejected = client.post(
        f"/api/v1/shift-requests/{reject_request_id}/cancel",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert cancel_after_rejected.status_code == 400

    db = test_session_local()
    try:
        pickup_shift = db.get(Shift, uuid.UUID(open_shift_id))
        assert pickup_shift is not None
        assert pickup_shift.assigned_user_id == member["id"]

        drop_shift = db.get(Shift, uuid.UUID(assigned_shift_id))
        assert drop_shift is not None
        assert drop_shift.assigned_user_id is None

        reject_shift = db.get(Shift, uuid.UUID(reject_target_shift_id))
        assert reject_shift is not None
        assert reject_shift.assigned_user_id is None

        pickup_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift_request",
                AuditLog.entity_id == pickup_request_id,
            )
        ).all()
        assert sorted(log.action for log in pickup_logs) == ["approve", "create"]

        drop_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift_request",
                AuditLog.entity_id == drop_request_id,
            )
        ).all()
        assert sorted(log.action for log in drop_logs) == ["approve", "create"]

        shift_update_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift",
                AuditLog.entity_id.in_([open_shift_id, assigned_shift_id]),
                AuditLog.action == "update",
            )
        ).all()
        assert len(shift_update_logs) >= 2
    finally:
        db.close()


def test_member_cancel_rules_and_tenant_isolation(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, f"sr-admin-a2-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"sr-admin-b2-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"sr-member-a2-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"sr-member-b2-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )
    _set_membership(
        test_session_local,
        user_id=member_b["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin_a["token"], "SR-004")
    open_shift_id = _create_shift(
        client,
        token=admin_a["token"],
        store_id=store_id,
        start_at="2026-03-26T09:00:00Z",
        end_at="2026-03-26T17:00:00Z",
    )
    open_shift_id_2 = _create_shift(
        client,
        token=admin_a["token"],
        store_id=store_id,
        start_at="2026-03-27T09:00:00Z",
        end_at="2026-03-27T17:00:00Z",
    )

    pending_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": open_shift_id, "type": "pickup"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert pending_request.status_code == 201
    pending_request_id = pending_request.json()["id"]

    other_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": open_shift_id_2, "type": "pickup"},
        headers={"Authorization": f"Bearer {member_b['token']}"},
    )
    assert other_request.status_code == 201
    other_request_id = other_request.json()["id"]

    cancel_others = client.post(
        f"/api/v1/shift-requests/{other_request_id}/cancel",
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert cancel_others.status_code == 403

    cancel_own = client.post(
        f"/api/v1/shift-requests/{pending_request_id}/cancel",
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert cancel_own.status_code == 200
    assert cancel_own.json()["status"] == "cancelled"

    cancel_again = client.post(
        f"/api/v1/shift-requests/{pending_request_id}/cancel",
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert cancel_again.status_code == 400

    cross_tenant_approve = client.post(
        f"/api/v1/shift-requests/{other_request_id}/approve",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_approve.status_code == 404

    db = test_session_local()
    try:
        cancelled = db.get(ShiftRequest, uuid.UUID(pending_request_id))
        assert cancelled is not None
        assert cancelled.resolved_at is not None
    finally:
        db.close()
