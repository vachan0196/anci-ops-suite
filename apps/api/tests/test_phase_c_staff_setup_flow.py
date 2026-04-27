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
SENSITIVE_RESPONSE_FIELDS = {
    "password",
    "hashed_password",
    "temporaryPassword",
    "confirmTemporaryPassword",
}


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_c_staff_setup_flow.db"
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


def _auth(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['token']}"}


def _create_store(client: TestClient, admin: dict, code: str = "PH-C-STORE") -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"{code}-{uuid.uuid4()}",
            "name": "Phase C Store",
            "timezone": "Europe/London",
            "address_line1": "1 Test Street",
            "city": None,
            "postcode": None,
            "phone": "07111111111",
            "manager_user_id": None,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_admin_user(
    client: TestClient,
    admin: dict,
    *,
    email: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email or f"phase-c-staff-{uuid.uuid4()}@example.com",
            "password": "staff-password-123",
            "full_name": "Phase C Staff",
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
    store_id: str | None = None,
    display_name: str = "Phase C Staff",
    extra: dict | None = None,
) -> dict:
    payload = {
        "user_id": user_id,
        "store_id": store_id,
        "display_name": display_name,
        "job_title": "Cashier",
        "hourly_rate": "12.50",
        "pay_type": "hourly",
        "phone": "07111111111",
        "is_active": True,
    }
    if extra:
        payload.update(extra)

    response = client.post(
        "/api/v1/staff",
        json=payload,
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _assert_no_sensitive_fields(body: dict) -> None:
    assert SENSITIVE_RESPONSE_FIELDS.isdisjoint(body.keys())


def test_full_three_call_staff_setup_flow_lists_staff_by_store_and_audits(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-c-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)
    tenant_user = _create_admin_user(client, admin)

    staff = _create_staff_profile(
        client,
        admin,
        user_id=tenant_user["id"],
        store_id=store["id"],
    )

    role_response = client.post(
        f"/api/v1/staff/{staff['id']}/roles",
        json={"role": "Cashier"},
        headers=_auth(admin),
    )
    assert role_response.status_code == 200
    role_body = role_response.json()

    list_response = client.get(
        f"/api/v1/staff?store_id={store['id']}",
        headers=_auth(admin),
    )
    assert list_response.status_code == 200
    listed_staff = list_response.json()

    assert staff["store_id"] == store["id"]
    assert staff["user_id"] == tenant_user["id"]
    assert staff["display_name"] == "Phase C Staff"
    assert role_body["staff_id"] == staff["id"]
    assert role_body["role"] == "cashier"
    assert any(item["id"] == staff["id"] for item in listed_staff)

    db = test_session_local()
    try:
        user_log = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == tenant_user["id"],
                AuditLog.action == "create_in_tenant",
            )
        )
        staff_log = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_type == "staff_profile",
                AuditLog.entity_id == staff["id"],
                AuditLog.action == "create",
            )
        )
        role_log = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_type == "staff_role",
                AuditLog.entity_id == role_body["id"],
                AuditLog.action == "add_role",
            )
        )
        assert user_log is not None
        assert staff_log is not None
        assert role_log is not None
    finally:
        db.close()


def test_staff_setup_responses_do_not_return_password_fields(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-c-sensitive-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)
    tenant_user = _create_admin_user(client, admin)
    staff = _create_staff_profile(
        client,
        admin,
        user_id=tenant_user["id"],
        store_id=store["id"],
    )

    _assert_no_sensitive_fields(tenant_user)
    _assert_no_sensitive_fields(staff)


def test_staff_setup_protected_endpoints_reject_unauthenticated_requests(
    client: TestClient,
) -> None:
    create_user = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"phase-c-unauth-{uuid.uuid4()}@example.com",
            "password": "staff-password-123",
            "full_name": "Unauthenticated User",
            "role": "member",
        },
    )
    create_staff = client.post(
        "/api/v1/staff",
        json={
            "user_id": str(uuid.uuid4()),
            "display_name": "Unauthenticated Staff",
        },
    )
    create_role = client.post(
        f"/api/v1/staff/{uuid.uuid4()}/roles",
        json={"role": "Cashier"},
    )

    assert create_user.status_code == 401
    assert create_staff.status_code == 401
    assert create_role.status_code == 401


def test_member_cannot_create_admin_user(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-c-admin-owner-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"phase-c-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"phase-c-forbidden-{uuid.uuid4()}@example.com",
            "password": "staff-password-123",
            "full_name": "Forbidden User",
            "role": "member",
        },
        headers=_auth(member),
    )

    assert response.status_code == 403


def test_store_from_another_tenant_rejected_for_staff_profile(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-c-tenant-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-c-tenant-b-{uuid.uuid4()}@example.com")
    tenant_b_store = _create_store(client, admin_b, code="PH-C-TENANT-B")
    tenant_a_user = _create_admin_user(client, admin_a)

    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": tenant_a_user["id"],
            "store_id": tenant_b_store["id"],
            "display_name": "Wrong Store Staff",
        },
        headers=_auth(admin_a),
    )
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "STORE_NOT_FOUND"


def test_duplicate_email_blocked(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-c-duplicate-admin-{uuid.uuid4()}@example.com")
    email = f"phase-c-duplicate-{uuid.uuid4()}@example.com"
    _create_admin_user(client, admin, email=email)

    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": "staff-password-123",
            "full_name": "Duplicate User",
            "role": "member",
        },
        headers=_auth(admin),
    )
    body = response.json()

    assert response.status_code == 409
    assert body["error"]["code"] == "AUTH_EMAIL_EXISTS"


def test_duplicate_staff_profile_blocked(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-c-profile-admin-{uuid.uuid4()}@example.com")
    tenant_user = _create_admin_user(client, admin)
    _create_staff_profile(client, admin, user_id=tenant_user["id"])

    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": tenant_user["id"],
            "display_name": "Duplicate Staff Profile",
        },
        headers=_auth(admin),
    )
    body = response.json()

    assert response.status_code == 409
    assert body["error"]["code"] == "STAFF_PROFILE_EXISTS"


def test_duplicate_staff_role_blocked(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-c-role-admin-{uuid.uuid4()}@example.com")
    tenant_user = _create_admin_user(client, admin)
    staff = _create_staff_profile(client, admin, user_id=tenant_user["id"])

    first_response = client.post(
        f"/api/v1/staff/{staff['id']}/roles",
        json={"role": "Cashier"},
        headers=_auth(admin),
    )
    assert first_response.status_code == 200

    duplicate_response = client.post(
        f"/api/v1/staff/{staff['id']}/roles",
        json={"role": "Cashier"},
        headers=_auth(admin),
    )
    body = duplicate_response.json()

    assert duplicate_response.status_code == 409
    assert body["error"]["code"] == "STAFF_ROLE_EXISTS"


def test_empty_staff_role_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-c-empty-role-admin-{uuid.uuid4()}@example.com")
    tenant_user = _create_admin_user(client, admin)
    staff = _create_staff_profile(client, admin, user_id=tenant_user["id"])

    response = client.post(
        f"/api/v1/staff/{staff['id']}/roles",
        json={"role": "   "},
        headers=_auth(admin),
    )
    body = response.json()

    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_sensitive_unsupported_staff_fields_are_ignored_not_returned(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-c-extra-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin)
    tenant_user = _create_admin_user(client, admin)

    staff = _create_staff_profile(
        client,
        admin,
        user_id=tenant_user["id"],
        store_id=store["id"],
        extra={
            "nationalInsuranceNumber": "AB123456C",
            "weeklyHourCap": "40",
            "overtimeHourlyRate": "15.00",
        },
    )

    assert staff["store_id"] == store["id"]
    assert "nationalInsuranceNumber" not in staff
    assert "weeklyHourCap" not in staff
    assert "overtimeHourlyRate" not in staff
    _assert_no_sensitive_fields(staff)
