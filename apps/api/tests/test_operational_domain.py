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


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_operational.db"
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


def test_stores_permissions_tenant_isolation_and_audit(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, f"stores-admin-a-{uuid.uuid4()}@example.com")
    member_user = _register_and_login(client, f"stores-member-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"stores-admin-b-{uuid.uuid4()}@example.com")

    _set_membership(
        test_session_local,
        user_id=member_user["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    create_response = client.post(
        "/api/v1/stores",
        json={"code": "S-001", "name": "Store A", "timezone": "UTC"},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert create_response.status_code == 201
    store_id = create_response.json()["id"]

    member_create_response = client.post(
        "/api/v1/stores",
        json={"code": "S-002", "name": "Store B"},
        headers={"Authorization": f"Bearer {member_user['token']}"},
    )
    assert member_create_response.status_code == 403

    member_list_response = client.get(
        "/api/v1/stores",
        headers={"Authorization": f"Bearer {member_user['token']}"},
    )
    assert member_list_response.status_code == 200
    assert len(member_list_response.json()) == 1

    cross_tenant_get_response = client.get(
        f"/api/v1/stores/{store_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_get_response.status_code == 404

    update_response = client.patch(
        f"/api/v1/stores/{store_id}",
        json={"name": "Store A Updated"},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert update_response.status_code == 200

    deactivate_response = client.post(
        f"/api/v1/stores/{store_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "store",
                AuditLog.entity_id == str(store_id),
            )
        ).all()
        actions = sorted(log.action for log in logs)
        assert actions == ["create", "deactivate", "update"]
    finally:
        db.close()


def test_staff_permissions_tenant_isolation_and_audit(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, f"staff-admin-a-{uuid.uuid4()}@example.com")
    member_user = _register_and_login(client, f"staff-member-{uuid.uuid4()}@example.com")
    outsider_user = _register_and_login(client, f"staff-outsider-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"staff-admin-b-{uuid.uuid4()}@example.com")

    _set_membership(
        test_session_local,
        user_id=member_user["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    create_profile_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": str(member_user["id"]),
            "display_name": "Member User",
            "job_title": "Crew",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert create_profile_response.status_code == 201
    profile_id = create_profile_response.json()["id"]

    create_non_member_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": str(outsider_user["id"]),
            "display_name": "Outsider User",
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert create_non_member_response.status_code == 400

    member_me_response = client.get(
        "/api/v1/staff/me",
        headers={"Authorization": f"Bearer {member_user['token']}"},
    )
    assert member_me_response.status_code == 200
    assert member_me_response.json()["user_id"] == str(member_user["id"])

    member_list_response = client.get(
        "/api/v1/staff",
        headers={"Authorization": f"Bearer {member_user['token']}"},
    )
    assert member_list_response.status_code == 403

    admin_list_response = client.get(
        "/api/v1/staff",
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert admin_list_response.status_code == 200
    assert len(admin_list_response.json()) == 1

    update_response = client.patch(
        f"/api/v1/staff/{member_user['id']}",
        json={"job_title": "Shift Lead"},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["job_title"] == "Shift Lead"

    cross_tenant_update_response = client.patch(
        f"/api/v1/staff/{member_user['id']}",
        json={"job_title": "Wrong Tenant Update"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_update_response.status_code == 404

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "staff_profile",
                AuditLog.entity_id == str(profile_id),
            )
        ).all()
        actions = sorted(log.action for log in logs)
        assert actions == ["create", "update"]
    finally:
        db.close()
