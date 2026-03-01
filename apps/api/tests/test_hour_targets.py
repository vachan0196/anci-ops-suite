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
from apps.api.models.hour_target import HourTarget
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
    db_path = tmp_path / "test_hour_targets.db"
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


def test_admin_can_upsert_hour_target_and_audit(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"hour-target-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"hour-target-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    upsert_response = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member["id"]),
            "week_start": "2026-04-06",
            "min_hours": 12,
            "max_hours": 40,
            "target_hours": 30,
            "notes": "Planning baseline",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert upsert_response.status_code == 201
    target_id = upsert_response.json()["id"]

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "hour_target",
                AuditLog.entity_id == target_id,
            )
        ).all()
        assert [log.action for log in logs] == ["upsert"]
    finally:
        db.close()


def test_hour_target_upsert_updates_existing_not_duplicate(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"hour-target-upsert-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"hour-target-upsert-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    first = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member["id"]),
            "week_start": "2026-04-06",
            "target_hours": 24,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member["id"]),
            "week_start": "2026-04-06",
            "target_hours": 32,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first_id
    assert second.json()["target_hours"] == 32

    db = test_session_local()
    try:
        total = db.scalar(
            select(HourTarget).where(
                HourTarget.id == uuid.UUID(first_id),
                HourTarget.tenant_id == admin["active_tenant_id"],
            )
        )
        assert total is not None
        all_targets = db.scalars(
            select(HourTarget).where(HourTarget.tenant_id == admin["active_tenant_id"])
        ).all()
        assert len(all_targets) == 1
    finally:
        db.close()


def test_member_cannot_upsert_or_delete_hour_target(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"hour-target-member-block-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"hour-target-member-block-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    create = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member["id"]),
            "week_start": "2026-04-06",
            "target_hours": 20,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create.status_code == 201
    target_id = create.json()["id"]

    member_upsert = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member["id"]),
            "week_start": "2026-04-06",
            "target_hours": 25,
        },
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_upsert.status_code == 403

    member_delete = client.delete(
        f"/api/v1/hour-targets/{target_id}",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_delete.status_code == 403


def test_admin_hour_target_list_filters_and_week_start_required(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"hour-target-filter-admin-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"hour-target-filter-member-a-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"hour-target-filter-member-b-{uuid.uuid4()}@example.com")
    for member in [member_a, member_b]:
        _set_membership(
            test_session_local,
            user_id=member["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )

    store_id = _create_store(client, admin["token"], "HT-FLT")

    create_store_scoped = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member_a["id"]),
            "store_id": store_id,
            "week_start": "2026-04-06",
            "target_hours": 18,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_store_scoped.status_code == 201

    create_tenant_scoped = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member_b["id"]),
            "week_start": "2026-04-06",
            "target_hours": 28,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_tenant_scoped.status_code == 201

    missing_week_start = client.get(
        "/api/v1/hour-targets",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert missing_week_start.status_code == 422

    filtered_user = client.get(
        "/api/v1/hour-targets",
        params={"week_start": "2026-04-06", "user_id": str(member_a["id"])},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert filtered_user.status_code == 200
    assert len(filtered_user.json()) == 1
    assert filtered_user.json()[0]["user_id"] == str(member_a["id"])

    filtered_store = client.get(
        "/api/v1/hour-targets",
        params={"week_start": "2026-04-06", "store_id": store_id},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert filtered_store.status_code == 200
    assert len(filtered_store.json()) == 1
    assert filtered_store.json()[0]["store_id"] == store_id


def test_member_get_me_returns_only_own_targets(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"hour-target-me-admin-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"hour-target-me-member-a-{uuid.uuid4()}@example.com")
    member_b = _register_and_login(client, f"hour-target-me-member-b-{uuid.uuid4()}@example.com")
    for member in [member_a, member_b]:
        _set_membership(
            test_session_local,
            user_id=member["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )

    create_a = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member_a["id"]),
            "week_start": "2026-04-06",
            "target_hours": 26,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_a.status_code == 201

    create_b = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member_b["id"]),
            "week_start": "2026-04-06",
            "target_hours": 19,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_b.status_code == 201

    member_a_me = client.get(
        "/api/v1/hour-targets/me",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member_a['token']}"},
    )
    assert member_a_me.status_code == 200
    assert len(member_a_me.json()) == 1
    assert member_a_me.json()[0]["user_id"] == str(member_a["id"])


def test_hour_target_tenant_isolation_blocked(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"hour-target-iso-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"hour-target-iso-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"hour-target-iso-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    create = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(member_a["id"]),
            "week_start": "2026-04-06",
            "target_hours": 21,
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert create.status_code == 201
    target_id = create.json()["id"]

    cross_tenant_delete = client.delete(
        f"/api/v1/hour-targets/{target_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_delete.status_code == 404

    cross_tenant_list = client.get(
        "/api/v1/hour-targets",
        params={"week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_tenant_list.status_code == 200
    assert cross_tenant_list.json() == []
