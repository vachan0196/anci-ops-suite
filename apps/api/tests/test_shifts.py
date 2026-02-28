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


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_shifts.db"
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


def test_shift_admin_create_member_forbidden_and_assignment_validation(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"shift-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"shift-member-{uuid.uuid4()}@example.com")
    outsider = _register_and_login(client, f"shift-outsider-{uuid.uuid4()}@example.com")

    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "SHIFT-001")

    create_response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "assigned_user_id": str(member["id"]),
            "start_at": "2026-03-01T09:00:00Z",
            "end_at": "2026-03-01T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_response.status_code == 201

    member_create_response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": "2026-03-02T09:00:00Z",
            "end_at": "2026-03-02T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_create_response.status_code == 403

    assign_non_member_response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "assigned_user_id": str(outsider["id"]),
            "start_at": "2026-03-03T09:00:00Z",
            "end_at": "2026-03-03T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert assign_non_member_response.status_code == 400


def test_shift_tenant_isolation_and_member_visibility(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, f"shift-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"shift-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"shift-admin-b-{uuid.uuid4()}@example.com")

    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin_a["token"], "SHIFT-002")

    mine_response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "assigned_user_id": str(member_a["id"]),
            "start_at": "2026-03-04T09:00:00Z",
            "end_at": "2026-03-04T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert mine_response.status_code == 201
    my_shift_id = mine_response.json()["id"]

    open_response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": "2026-03-05T09:00:00Z",
            "end_at": "2026-03-05T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert open_response.status_code == 201

    member_list_default = client.get(
        "/api/v1/shifts",
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_list_default.status_code == 200
    assert len(member_list_default.json()) == 1
    assert member_list_default.json()[0]["id"] == my_shift_id

    member_list_with_open = client.get(
        "/api/v1/shifts",
        params={"include_open": "true"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_list_with_open.status_code == 200
    assert len(member_list_with_open.json()) == 2

    cross_tenant_get = client.get(
        f"/api/v1/shifts/{my_shift_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_get.status_code == 404

    cross_tenant_update = client.patch(
        f"/api/v1/shifts/{my_shift_id}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_update.status_code == 404


def test_shift_audit_logs_on_create_update_cancel(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"shift-audit-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"shift-audit-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], "SHIFT-003")

    create_response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "assigned_user_id": str(member["id"]),
            "start_at": "2026-03-06T09:00:00Z",
            "end_at": "2026-03-06T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_response.status_code == 201
    shift_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/shifts/{shift_id}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert update_response.status_code == 200

    cancel_response = client.post(
        f"/api/v1/shifts/{shift_id}/cancel",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == str(shift_id),
            )
        ).all()
        actions = sorted(log.action for log in logs)
        assert actions == ["cancel", "create", "update"]
    finally:
        db.close()
