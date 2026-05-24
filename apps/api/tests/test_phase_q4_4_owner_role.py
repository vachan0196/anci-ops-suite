from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import importlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token, get_password_hash
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User


OWNER_EMAIL = "q44-owner@example.com"
PASSWORD = "password123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q4_4_owner_role.db"
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_owner(client: TestClient, email: str = OWNER_EMAIL) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    body = response.json()
    body["access_token"] = login.json()["access_token"]
    return body


def _create_admin_side_user(
    client: TestClient,
    *,
    owner_token: str,
    email: str,
    role: str,
) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        headers=_auth(owner_token),
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": email,
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    if role == "member":
        body["access_token"] = create_access_token(str(body["id"]))
    else:
        login = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": PASSWORD},
        )
        assert login.status_code == 200, login.text
        body["access_token"] = login.json()["access_token"]
    return body


def _employee_token() -> str:
    return create_access_token(f"employee:{uuid.uuid4()}")


def test_new_registration_creates_owner_membership_and_auth_me_returns_owner(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client)

    assert owner["active_tenant_role"] == "owner"

    me = client.get("/api/v1/auth/me", headers=_auth(owner["access_token"]))
    assert me.status_code == 200
    assert me.json()["active_tenant_role"] == "owner"

    db = test_session_local()
    try:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == uuid.UUID(owner["active_tenant_id"]),
                TenantUser.user_id == uuid.UUID(owner["id"]),
            )
        )
        assert membership is not None
        assert membership.role == "owner"
    finally:
        db.close()


def test_owner_admin_member_and_employee_rbac_across_admin_endpoints(client: TestClient) -> None:
    owner = _register_owner(client)
    owner_token = owner["access_token"]
    admin = _create_admin_side_user(
        client,
        owner_token=owner_token,
        email="q44-admin@example.com",
        role="admin",
    )
    member = _create_admin_side_user(
        client,
        owner_token=owner_token,
        email="q44-member@example.com",
        role="member",
    )
    employee_headers = _auth(_employee_token())

    owner_store = client.post(
        "/api/v1/stores",
        headers=_auth(owner_token),
        json={"code": "Q44-OWNER", "name": "Q44 Owner Store", "timezone": "Europe/London"},
    )
    assert owner_store.status_code == 201, owner_store.text

    admin_store = client.post(
        "/api/v1/stores",
        headers=_auth(admin["access_token"]),
        json={"code": "Q44-ADMIN", "name": "Q44 Admin Store", "timezone": "Europe/London"},
    )
    assert admin_store.status_code == 201, admin_store.text

    member_store = client.post(
        "/api/v1/stores",
        headers=_auth(member["access_token"]),
        json={"code": "Q44-MEMBER", "name": "Q44 Member Store"},
    )
    assert member_store.status_code == 403

    employee_store = client.post(
        "/api/v1/stores",
        headers=employee_headers,
        json={"code": "Q44-EMPLOYEE", "name": "Q44 Employee Store"},
    )
    assert employee_store.status_code in {401, 403}

    owner_created = client.post(
        "/api/v1/admin/users",
        headers=_auth(owner_token),
        json={
            "email": "q44-owner-created@example.com",
            "password": PASSWORD,
            "full_name": "Owner Created",
            "role": "member",
        },
    )
    assert owner_created.status_code == 201, owner_created.text

    admin_created = client.post(
        "/api/v1/admin/users",
        headers=_auth(admin["access_token"]),
        json={
            "email": "q44-admin-created@example.com",
            "password": PASSWORD,
            "full_name": "Admin Created",
            "role": "member",
        },
    )
    assert admin_created.status_code == 201, admin_created.text

    member_created = client.post(
        "/api/v1/admin/users",
        headers=_auth(member["access_token"]),
        json={
            "email": "q44-member-created@example.com",
            "password": PASSWORD,
            "full_name": "Member Created",
            "role": "member",
        },
    )
    assert member_created.status_code == 403

    employee_created = client.post(
        "/api/v1/admin/users",
        headers=employee_headers,
        json={
            "email": "q44-employee-created@example.com",
            "password": PASSWORD,
            "full_name": "Employee Created",
            "role": "member",
        },
    )
    assert employee_created.status_code in {401, 403}

    store_id = owner_store.json()["id"]
    owner_settings = client.patch(
        f"/api/v1/stores/{store_id}/settings",
        headers=_auth(owner_token),
        json={"business_week_start_day": 1},
    )
    assert owner_settings.status_code == 200, owner_settings.text

    admin_settings = client.patch(
        f"/api/v1/stores/{store_id}/settings",
        headers=_auth(admin["access_token"]),
        json={"business_week_start_day": 2},
    )
    assert admin_settings.status_code == 200, admin_settings.text

    member_settings = client.patch(
        f"/api/v1/stores/{store_id}/settings",
        headers=_auth(member["access_token"]),
        json={"business_week_start_day": 3},
    )
    assert member_settings.status_code == 403

    employee_settings = client.patch(
        f"/api/v1/stores/{store_id}/settings",
        headers=employee_headers,
        json={"business_week_start_day": 4},
    )
    assert employee_settings.status_code in {401, 403}


def _add_user(
    db: Session,
    *,
    email: str,
    tenant_id: uuid.UUID,
    role: str,
    created_at: datetime,
) -> TenantUser:
    user = User(
        email=email,
        hashed_password=get_password_hash(PASSWORD),
        is_active=True,
        active_tenant_id=tenant_id,
        created_at=created_at,
    )
    db.add(user)
    db.flush()
    membership = TenantUser(tenant_id=tenant_id, user_id=user.id, role=role)
    db.add(membership)
    db.flush()
    return membership


def _run_owner_backfill(db: Session) -> None:
    migration = importlib.import_module(
        "apps.api.alembic.versions.0027_phase_q4_4_owner_role"
    )
    migration._backfill_one_owner_per_tenant(db.connection())
    db.commit()


def test_owner_backfill_promotes_one_admin_per_tenant(test_session_local) -> None:
    db = test_session_local()
    try:
        tenant = Tenant(name="Q44 Backfill Tenant")
        db.add(tenant)
        db.flush()
        now = datetime.now(UTC)
        first_admin = _add_user(
            db,
            email="q44-first-admin@example.com",
            tenant_id=tenant.id,
            role="admin",
            created_at=now - timedelta(days=2),
        )
        second_admin = _add_user(
            db,
            email="q44-second-admin@example.com",
            tenant_id=tenant.id,
            role="admin",
            created_at=now - timedelta(days=1),
        )
        _add_user(
            db,
            email="q44-member-backfill@example.com",
            tenant_id=tenant.id,
            role="member",
            created_at=now - timedelta(days=3),
        )
        db.commit()

        _run_owner_backfill(db)

        db.refresh(first_admin)
        db.refresh(second_admin)
        assert first_admin.role == "owner"
        assert second_admin.role == "admin"
        owner_count = db.scalar(
            select(func.count()).select_from(TenantUser).where(
                TenantUser.tenant_id == tenant.id,
                TenantUser.role == "owner",
            )
        )
        assert owner_count == 1
    finally:
        db.close()


def test_owner_backfill_keeps_existing_owner_and_skips_zero_user_tenant(
    test_session_local,
) -> None:
    db = test_session_local()
    try:
        tenant_with_owner = Tenant(name="Q44 Existing Owner Tenant")
        orphan_tenant = Tenant(name="Q44 Orphan Tenant")
        db.add_all([tenant_with_owner, orphan_tenant])
        db.flush()
        now = datetime.now(UTC)
        existing_owner = _add_user(
            db,
            email="q44-existing-owner@example.com",
            tenant_id=tenant_with_owner.id,
            role="owner",
            created_at=now - timedelta(days=2),
        )
        existing_admin = _add_user(
            db,
            email="q44-existing-admin@example.com",
            tenant_id=tenant_with_owner.id,
            role="admin",
            created_at=now - timedelta(days=3),
        )
        db.commit()

        _run_owner_backfill(db)

        db.refresh(existing_owner)
        db.refresh(existing_admin)
        assert existing_owner.role == "owner"
        assert existing_admin.role == "admin"
        owner_count = db.scalar(
            select(func.count()).select_from(TenantUser).where(
                TenantUser.tenant_id == tenant_with_owner.id,
                TenantUser.role == "owner",
            )
        )
        orphan_membership_count = db.scalar(
            select(func.count()).select_from(TenantUser).where(
                TenantUser.tenant_id == orphan_tenant.id,
            )
        )
        assert owner_count == 1
        assert orphan_membership_count == 0
    finally:
        db.close()
