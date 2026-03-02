from collections.abc import Generator
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
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


def _create_staff_profile(client: TestClient, token: str, user_id: uuid.UUID, store_id: str | None = None) -> str:
    payload = {
        "user_id": str(user_id),
        "display_name": f"User {user_id}",
        "job_title": "Crew",
        "is_active": True,
    }
    if store_id is not None:
        payload["store_id"] = store_id
    response = client.post(
        "/api/v1/staff",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase14_onboarding_directory.db"
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


def test_auth_me_includes_active_tenant_role_for_admin_and_member(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p14-role-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p14-role-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    admin_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert admin_me.status_code == 200
    assert admin_me.json()["active_tenant_role"] == "admin"

    member_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_me.status_code == 200
    assert member_me.json()["active_tenant_role"] == "member"


def test_admin_users_endpoint_create_forbidden_duplicate_and_membership(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p14-admin-users-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"p14-admin-users-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    create_response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"p14-new-user-{uuid.uuid4()}@example.com",
            "password": "password123",
            "role": "member",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_response.status_code == 201
    created_user_id = create_response.json()["id"]

    member_forbidden = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"p14-member-forbidden-{uuid.uuid4()}@example.com",
            "password": "password123",
            "role": "member",
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_forbidden.status_code == 403

    duplicate = client.post(
        "/api/v1/admin/users",
        json={
            "email": create_response.json()["email"],
            "password": "password123",
            "role": "member",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert duplicate.status_code == 409

    db = test_session_local()
    try:
        created_user = db.get(User, uuid.UUID(created_user_id))
        assert created_user is not None
        assert created_user.active_tenant_id == admin["active_tenant_id"]

        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == admin["active_tenant_id"],
                TenantUser.user_id == created_user.id,
            )
        )
        assert membership is not None
        assert membership.role == "member"
    finally:
        db.close()


def test_store_details_patch_permissions_tenant_isolation_and_manager_validation(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, f"p14-store-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p14-store-member-a-{uuid.uuid4()}@example.com")
    outsider = _register_and_login(client, f"p14-store-outsider-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p14-store-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin_a["token"], "P14-S-001")

    patch = client.patch(
        f"/api/v1/stores/{store_id}",
        json={
            "address_line1": "1 High Street",
            "city": "London",
            "postcode": "SW1A 1AA",
            "phone": "02000000000",
            "manager_user_id": str(member_a["id"]),
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert patch.status_code == 200
    assert patch.json()["city"] == "London"
    assert patch.json()["manager_user_id"] == str(member_a["id"])

    member_patch = client.patch(
        f"/api/v1/stores/{store_id}",
        json={"city": "Manchester"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_patch.status_code == 403

    cross_tenant_patch = client.patch(
        f"/api/v1/stores/{store_id}",
        json={"city": "Bristol"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_patch.status_code == 404

    invalid_manager = client.patch(
        f"/api/v1/stores/{store_id}",
        json={"manager_user_id": str(outsider["id"])},
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert invalid_manager.status_code == 400

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "store",
                AuditLog.entity_id == store_id,
                AuditLog.action == "update",
            )
        ).all()
        assert len(logs) >= 1
    finally:
        db.close()


def test_staff_profile_admin_and_member_update_flows(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"p14-staff-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"p14-staff-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p14-staff-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin_a["token"], "P14-ST-001")
    staff_profile_id = _create_staff_profile(client, admin_a["token"], member_a["id"], store_id)

    admin_patch = client.patch(
        f"/api/v1/staff/{staff_profile_id}",
        json={
            "display_name": "Member A",
            "job_title": "Shift Lead",
            "hourly_rate": "12.50",
            "pay_type": "hourly",
            "contract_type": "part_time",
            "rtw_status": "verified",
            "notes": "Checked",
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert admin_patch.status_code == 200
    assert admin_patch.json()["job_title"] == "Shift Lead"
    assert admin_patch.json()["rtw_status"] == "verified"
    assert admin_patch.json()["rtw_checked_at"] is not None
    assert admin_patch.json()["rtw_checked_by_user_id"] == str(admin_a["id"])

    member_cannot_patch_admin_endpoint = client.patch(
        f"/api/v1/staff/{staff_profile_id}",
        json={"job_title": "Not Allowed"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_cannot_patch_admin_endpoint.status_code == 403

    member_patch_me = client.patch(
        "/api/v1/staff/me",
        json={
            "phone": "07111111111",
            "emergency_contact_name": "Emergency Contact",
            "emergency_contact_phone": "07222222222",
        },
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_patch_me.status_code == 200
    assert member_patch_me.json()["phone"] == "07111111111"

    cross_tenant_patch = client.patch(
        f"/api/v1/staff/{staff_profile_id}",
        json={"job_title": "Wrong Tenant"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_patch.status_code == 404

    db = test_session_local()
    try:
        profile = db.get(StaffProfile, uuid.UUID(staff_profile_id))
        assert profile is not None
        assert profile.hourly_rate == Decimal("12.50")
        assert profile.rtw_checked_by_user_id == admin_a["id"]

        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "staff_profile",
                AuditLog.entity_id == staff_profile_id,
            )
        ).all()
        actions = sorted(log.action for log in logs)
        assert "update" in actions
        assert "update_self" in actions
    finally:
        db.close()
