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
    db_path = tmp_path / "test_availability.db"
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


def test_member_create_availability_and_audit(client: TestClient, test_session_local) -> None:
    member = _register_and_login(client, f"availability-member-{uuid.uuid4()}@example.com")

    create_response = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-07",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "type": "unavailable",
            "notes": "Doctor appointment",
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert create_response.status_code == 201
    entry_id = create_response.json()["id"]
    assert create_response.json()["user_id"] == str(member["id"])

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "availability_entry",
                AuditLog.entity_id == entry_id,
            )
        ).all()
        assert [log.action for log in logs] == ["create"]
    finally:
        db.close()


def test_member_cannot_create_for_another_user(client: TestClient, test_session_local) -> None:
    member = _register_and_login(client, f"availability-member-payload-{uuid.uuid4()}@example.com")
    other = _register_and_login(client, f"availability-other-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/availability",
        json={
            "user_id": str(other["id"]),
            "week_start": "2026-04-06",
            "date": "2026-04-08",
            "type": "preferred_off",
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert response.status_code == 422


def test_admin_lists_all_and_member_only_own(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"availability-admin-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"availability-member-a-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"availability-member-b-{uuid.uuid4()}@example.com")
    for member in [member_a, member_b]:
        _set_membership(
            test_session_local,
            user_id=member["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )

    create_a = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-06",
            "type": "available_extra",
        },
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert create_a.status_code == 201

    create_b = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-07",
            "type": "unavailable",
        },
        headers={"Authorization": f"Bearer {member_b['token']}"},
    )
    assert create_b.status_code == 201

    admin_list = client.get(
        "/api/v1/availability",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert admin_list.status_code == 200
    assert len(admin_list.json()) == 2

    member_list = client.get(
        "/api/v1/availability",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_list.status_code == 200
    assert len(member_list.json()) == 1
    assert member_list.json()[0]["user_id"] == str(member_a["id"])


def test_availability_tenant_isolation_read_and_delete(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"availability-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"availability-member-iso-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"availability-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    create_response = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-09",
            "type": "preferred_off",
        },
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert create_response.status_code == 201
    entry_id = create_response.json()["id"]

    cross_tenant_list = client.get(
        "/api/v1/availability",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_list.status_code == 200
    assert cross_tenant_list.json() == []

    cross_tenant_delete = client.delete(
        f"/api/v1/availability/{entry_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_delete.status_code == 404


def test_availability_validation_for_times_and_week_window(client: TestClient) -> None:
    member = _register_and_login(client, f"availability-validation-{uuid.uuid4()}@example.com")

    bad_time = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-08",
            "start_time": "18:00:00",
            "end_time": "09:00:00",
            "type": "available",
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert bad_time.status_code == 422

    out_of_week = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-20",
            "type": "unavailable",
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert out_of_week.status_code == 422


def test_availability_store_must_belong_to_active_tenant(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"availability-store-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"availability-store-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"availability-store-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    foreign_store_id = _create_store(client, admin_b["token"], "AV-FOREIGN")

    response = client.post(
        "/api/v1/availability",
        json={
            "week_start": "2026-04-06",
            "date": "2026-04-10",
            "store_id": foreign_store_id,
            "type": "available_extra",
        },
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert response.status_code == 404
