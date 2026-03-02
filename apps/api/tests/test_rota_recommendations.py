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
from apps.api.models.rota_recommendation_draft import RotaRecommendationDraft
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


def _create_open_shift(client: TestClient, token: str, store_id: str, start_at: str, end_at: str) -> str:
    response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": start_at,
            "end_at": end_at,
        },
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


def _upsert_hour_target(
    client: TestClient,
    *,
    admin_token: str,
    user_id: uuid.UUID,
    week_start: str,
    min_hours: int,
    max_hours: int,
    target_hours: int,
) -> None:
    response = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(user_id),
            "week_start": week_start,
            "min_hours": min_hours,
            "max_hours": max_hours,
            "target_hours": target_hours,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code in [200, 201]


def _create_recommendation_draft(client: TestClient, admin_token: str, store_id: str, week_start: str) -> dict:
    response = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": week_start},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_rota_recommendations.db"
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


def test_admin_can_generate_recommendation_draft(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"rr-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"rr-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin["token"], "RR-001")
    _create_staff_profile(client, admin["token"], member["id"], store_id)
    _create_open_shift(
        client,
        admin["token"],
        store_id,
        "2026-04-06T09:00:00Z",
        "2026-04-06T17:00:00Z",
    )
    _create_availability(
        client,
        token=member["token"],
        week_start="2026-04-06",
        date="2026-04-06",
        start_time="08:00:00",
        end_time="18:00:00",
    )
    _upsert_hour_target(
        client,
        admin_token=admin["token"],
        user_id=member["id"],
        week_start="2026-04-06",
        min_hours=10,
        max_hours=40,
        target_hours=20,
    )

    create_draft_response = _create_recommendation_draft(client, admin["token"], store_id, "2026-04-06")
    assert create_draft_response["shifts_considered"] == 1
    assert create_draft_response["items_created"] == 1
    assert create_draft_response["unfilled"] == 0

    detail_response = client.get(
        f"/api/v1/rota-recommendations/{create_draft_response['draft_id']}",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert detail_response.status_code == 200
    assert len(detail_response.json()["items"]) == 1
    assert detail_response.json()["items"][0]["proposed_user_id"] == str(member["id"])

    db = test_session_local()
    try:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "rota_recommendation_draft",
                AuditLog.entity_id == create_draft_response["draft_id"],
                AuditLog.action == "create",
            )
        ).all()
        assert len(logs) == 1
    finally:
        db.close()


def test_apply_recommendation_draft_updates_shifts_and_audits(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"rr-apply-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"rr-apply-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin["token"], "RR-002")
    _create_staff_profile(client, admin["token"], member["id"], store_id)
    shift_id = _create_open_shift(
        client,
        admin["token"],
        store_id,
        "2026-04-07T09:00:00Z",
        "2026-04-07T17:00:00Z",
    )
    _create_availability(
        client,
        token=member["token"],
        week_start="2026-04-06",
        date="2026-04-07",
        start_time="09:00:00",
        end_time="17:00:00",
    )

    draft = _create_recommendation_draft(client, admin["token"], store_id, "2026-04-06")
    draft_id = draft["draft_id"]

    apply_response = client.post(
        f"/api/v1/rota-recommendations/{draft_id}/apply",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["count_applied"] == 1

    db = test_session_local()
    try:
        shift = db.get(Shift, uuid.UUID(shift_id))
        assert shift is not None
        assert shift.assigned_user_id == member["id"]

        draft_row = db.get(RotaRecommendationDraft, uuid.UUID(draft_id))
        assert draft_row is not None
        assert draft_row.status == "applied"
        assert draft_row.applied_at is not None

        draft_apply_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "rota_recommendation_draft",
                AuditLog.entity_id == draft_id,
                AuditLog.action == "apply",
            )
        ).all()
        assert len(draft_apply_logs) == 1

        shift_update_logs = db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == shift_id,
                AuditLog.action == "update",
            )
        ).all()
        assert len(shift_update_logs) >= 1
    finally:
        db.close()


def test_member_cannot_create_or_apply_recommendation_draft(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"rr-rbac-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"rr-rbac-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin["token"], "RR-003")
    _create_staff_profile(client, admin["token"], member["id"], store_id)
    _create_open_shift(
        client,
        admin["token"],
        store_id,
        "2026-04-08T09:00:00Z",
        "2026-04-08T17:00:00Z",
    )
    _create_availability(
        client,
        token=member["token"],
        week_start="2026-04-06",
        date="2026-04-08",
        start_time="09:00:00",
        end_time="17:00:00",
    )

    member_create = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_create.status_code == 403

    draft = _create_recommendation_draft(client, admin["token"], store_id, "2026-04-06")
    member_apply = client.post(
        f"/api/v1/rota-recommendations/{draft['draft_id']}/apply",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_apply.status_code == 403


def test_recommendation_draft_tenant_isolation(client: TestClient, test_session_local) -> None:
    admin_a = _register_and_login(client, f"rr-iso-admin-a-{uuid.uuid4()}@example.com")
    member_a = _register_and_login(client, f"rr-iso-member-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"rr-iso-admin-b-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member_a["id"],
        tenant_id=admin_a["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin_a["token"], "RR-004")
    _create_staff_profile(client, admin_a["token"], member_a["id"], store_id)
    _create_open_shift(
        client,
        admin_a["token"],
        store_id,
        "2026-04-09T09:00:00Z",
        "2026-04-09T17:00:00Z",
    )
    _create_availability(
        client,
        token=member_a["token"],
        week_start="2026-04-06",
        date="2026-04-09",
        start_time="09:00:00",
        end_time="17:00:00",
    )

    draft = _create_recommendation_draft(client, admin_a["token"], store_id, "2026-04-06")
    draft_id = draft["draft_id"]

    cross_get = client.get(
        f"/api/v1/rota-recommendations/{draft_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_get.status_code == 404

    cross_apply = client.post(
        f"/api/v1/rota-recommendations/{draft_id}/apply",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_apply.status_code == 404


def test_apply_is_not_idempotent_for_already_applied_draft(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"rr-idem-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"rr-idem-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )

    store_id = _create_store(client, admin["token"], "RR-005")
    _create_staff_profile(client, admin["token"], member["id"], store_id)
    _create_open_shift(
        client,
        admin["token"],
        store_id,
        "2026-04-10T09:00:00Z",
        "2026-04-10T17:00:00Z",
    )
    _create_availability(
        client,
        token=member["token"],
        week_start="2026-04-06",
        date="2026-04-10",
        start_time="09:00:00",
        end_time="17:00:00",
    )

    draft = _create_recommendation_draft(client, admin["token"], store_id, "2026-04-06")
    draft_id = draft["draft_id"]

    first_apply = client.post(
        f"/api/v1/rota-recommendations/{draft_id}/apply",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert first_apply.status_code == 200

    second_apply = client.post(
        f"/api/v1/rota-recommendations/{draft_id}/apply",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert second_apply.status_code == 409
