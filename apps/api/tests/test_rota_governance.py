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
    db_path = tmp_path / "test_rota_governance.db"
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


def test_publish_unpublish_permissions_and_tenant_isolation(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, f"p11-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p11-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p11-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    store_a = _create_store(client, admin_a["token"], "P11-A")
    store_b = _create_store(client, admin_b["token"], "P11-B")
    _create_shift(
        client,
        token=admin_a["token"],
        store_id=store_a,
        start_at="2026-04-01T09:00:00Z",
        end_at="2026-04-01T17:00:00Z",
    )
    _create_shift(
        client,
        token=admin_a["token"],
        store_id=store_a,
        start_at="2026-04-02T09:00:00Z",
        end_at="2026-04-02T17:00:00Z",
    )
    _create_shift(
        client,
        token=admin_b["token"],
        store_id=store_b,
        start_at="2026-04-01T09:00:00Z",
        end_at="2026-04-01T17:00:00Z",
    )

    member_publish = client.post(
        "/api/v1/shifts/publish",
        json={"store_id": store_a, "from": "2026-04-01T00:00:00Z", "to": "2026-04-08T00:00:00Z"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_publish.status_code == 403

    publish = client.post(
        "/api/v1/shifts/publish",
        json={"store_id": store_a, "from": "2026-04-01T00:00:00Z", "to": "2026-04-08T00:00:00Z"},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert publish.status_code == 200
    assert publish.json()["updated_count"] == 2

    cross_tenant_publish = client.post(
        "/api/v1/shifts/publish",
        json={"store_id": store_a, "from": "2026-04-01T00:00:00Z", "to": "2026-04-08T00:00:00Z"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_publish.status_code == 404

    status_response = client.get(
        "/api/v1/shifts/publish-status",
        params={"store_id": store_a, "from": "2026-04-01T00:00:00Z", "to": "2026-04-08T00:00:00Z"},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["published"] == 2
    assert status_response.json()["unpublished"] == 0

    unpublish = client.post(
        "/api/v1/shifts/unpublish",
        json={"store_id": store_a, "from": "2026-04-01T00:00:00Z", "to": "2026-04-08T00:00:00Z"},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert unpublish.status_code == 200
    assert unpublish.json()["updated_count"] == 2

    db = test_session_local()
    try:
        published_a = db.scalars(select(Shift).where(Shift.store_id == uuid.UUID(store_a))).all()
        assert len(published_a) == 2
        assert all(shift.published_at is None for shift in published_a)

        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == store_a,
                AuditLog.action.in_(["publish_range", "unpublish_range"]),
            )
        ).all()
        assert len(logs) == 2
    finally:
        db.close()


def test_swap_workflow_accept_approve_and_listing(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"p11-admin-{uuid.uuid4()}@example.com")
    requester = _register_and_login(client, f"p11-requester-{uuid.uuid4()}@example.com")
    target = _register_and_login(client, f"p11-target-{uuid.uuid4()}@example.com")
    outsider = _register_and_login(client, f"p11-outsider-{uuid.uuid4()}@example.com")
    for user in [requester, target, outsider]:
        _set_membership(
            test_session_local,
            user_id=user["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )

    store_id = _create_store(client, admin["token"], "P11-SWAP")
    shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-04-10T09:00:00Z",
        end_at="2026-04-10T17:00:00Z",
        assigned_user_id=str(requester["id"]),
    )

    create_swap = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": shift_id, "type": "swap", "target_user_id": str(target["id"])},
        headers={"Authorization": f"Bearer {requester['token']}"},
    )
    assert create_swap.status_code == 201
    assert create_swap.json()["status"] == "pending_target"
    request_id = create_swap.json()["id"]

    target_default_list = client.get(
        "/api/v1/shift-requests",
        headers={"Authorization": f"Bearer {target['token']}"},
    )
    assert target_default_list.status_code == 200
    assert len(target_default_list.json()) == 0

    target_incoming_list = client.get(
        "/api/v1/shift-requests",
        params={"include_incoming": "true"},
        headers={"Authorization": f"Bearer {target['token']}"},
    )
    assert target_incoming_list.status_code == 200
    assert len(target_incoming_list.json()) == 1

    outsider_accept = client.post(
        f"/api/v1/shift-requests/{request_id}/accept",
        headers={"Authorization": f"Bearer {outsider['token']}"},
    )
    assert outsider_accept.status_code == 403

    approve_too_early = client.post(
        f"/api/v1/shift-requests/{request_id}/approve",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert approve_too_early.status_code == 400

    accept = client.post(
        f"/api/v1/shift-requests/{request_id}/accept",
        headers={"Authorization": f"Bearer {target['token']}"},
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "target_accepted"

    cancel_after_accept = client.post(
        f"/api/v1/shift-requests/{request_id}/cancel",
        headers={"Authorization": f"Bearer {requester['token']}"},
    )
    assert cancel_after_accept.status_code == 400

    approve = client.post(
        f"/api/v1/shift-requests/{request_id}/approve",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    db = test_session_local()
    try:
        shift = db.get(Shift, uuid.UUID(shift_id))
        assert shift is not None
        assert shift.assigned_user_id == target["id"]

        req_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift_request",
                AuditLog.entity_id == request_id,
            )
        ).all()
        assert sorted(log.action for log in req_logs) == ["accept", "approve", "create"]

        shift_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == shift_id,
                AuditLog.action == "update",
            )
        ).all()
        assert len(shift_logs) >= 1
    finally:
        db.close()


def test_swap_decline_reject_and_shift_change_window_policy(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"p11-admin-r-{uuid.uuid4()}@example.com")
    requester = _register_and_login(client, f"p11-requester-r-{uuid.uuid4()}@example.com")
    target = _register_and_login(client, f"p11-target-r-{uuid.uuid4()}@example.com")
    for user in [requester, target]:
        _set_membership(
            test_session_local,
            user_id=user["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )

    store_id = _create_store(client, admin["token"], "P11-RULES")
    far_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at="2026-04-15T09:00:00Z",
        end_at="2026-04-15T17:00:00Z",
        assigned_user_id=str(requester["id"]),
    )

    decline_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": far_shift_id, "type": "swap", "target_user_id": str(target["id"])},
        headers={"Authorization": f"Bearer {requester['token']}"},
    )
    assert decline_request.status_code == 201
    decline_request_id = decline_request.json()["id"]

    decline = client.post(
        f"/api/v1/shift-requests/{decline_request_id}/decline",
        headers={"Authorization": f"Bearer {target['token']}"},
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "target_declined"

    approve_declined = client.post(
        f"/api/v1/shift-requests/{decline_request_id}/approve",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert approve_declined.status_code == 400

    reject_accepted_path_request = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": far_shift_id, "type": "swap", "target_user_id": str(target["id"])},
        headers={"Authorization": f"Bearer {requester['token']}"},
    )
    assert reject_accepted_path_request.status_code == 201
    reject_accepted_id = reject_accepted_path_request.json()["id"]
    reject_from_pending_target = client.post(
        f"/api/v1/shift-requests/{reject_accepted_id}/reject",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert reject_from_pending_target.status_code == 200
    assert reject_from_pending_target.json()["status"] == "rejected"

    near_start = datetime.now(timezone.utc) + timedelta(hours=24)
    near_end = near_start + timedelta(hours=8)
    near_shift_id = _create_shift(
        client,
        token=admin["token"],
        store_id=store_id,
        start_at=near_start.isoformat(),
        end_at=near_end.isoformat(),
        assigned_user_id=str(requester["id"]),
    )

    too_close_drop = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": near_shift_id, "type": "drop"},
        headers={"Authorization": f"Bearer {requester['token']}"},
    )
    assert too_close_drop.status_code == 400

    too_close_swap = client.post(
        "/api/v1/shift-requests",
        json={"shift_id": near_shift_id, "type": "swap", "target_user_id": str(target["id"])},
        headers={"Authorization": f"Bearer {requester['token']}"},
    )
    assert too_close_swap.status_code == 400
