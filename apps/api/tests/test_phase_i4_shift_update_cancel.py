from collections.abc import Generator
from datetime import datetime, timezone
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


PASSWORD = "password123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_i4_shift_update_cancel.db"
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
        "id": register_body["id"],
        "active_tenant_id": register_body["active_tenant_id"],
        "token": token,
    }


def _auth(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['token']}"}


def _create_store(client: TestClient, admin: dict, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": code,
            "name": f"Store {code}",
            "timezone": "Europe/London",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_tenant_member(client: TestClient, admin: dict, email: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Phase I4 Staff",
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
    store_id: str,
) -> dict:
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user_id,
            "store_id": store_id,
            "display_name": "Phase I4 Staff",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_site_shift(
    client: TestClient,
    admin: dict,
    *,
    site_id: str,
    assigned_employee_account_id: str | None = None,
    role_required: str | None = "Cashier",
    start_time: str = "2026-04-20T09:00:00Z",
    end_time: str = "2026-04-20T17:00:00Z",
) -> dict:
    response = client.post(
        f"/api/v1/sites/{site_id}/shifts",
        json={
            "assigned_employee_account_id": assigned_employee_account_id,
            "role_required": role_required,
            "start_time": start_time,
            "end_time": end_time,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _update_payload(**overrides) -> dict:
    payload = {
        "assigned_employee_account_id": None,
        "role_required": "Supervisor",
        "start_time": "2026-04-21T10:00:00Z",
        "end_time": "2026-04-21T18:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_unauthenticated_update_and_cancel_rejected(client: TestClient) -> None:
    site_id = uuid.uuid4()
    shift_id = uuid.uuid4()

    update_response = client.patch(
        f"/api/v1/sites/{site_id}/shifts/{shift_id}",
        json=_update_payload(),
    )
    cancel_response = client.post(
        f"/api/v1/sites/{site_id}/shifts/{shift_id}/cancel",
    )

    assert update_response.status_code == 401
    assert cancel_response.status_code == 401


def test_admin_updates_draft_shift_and_weekly_rota_reflects_change(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-i4-update-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I4-A-{uuid.uuid4()}")
    shift = _create_site_shift(client, admin, site_id=store["id"])

    response = client.patch(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}",
        json=_update_payload(role_required="Supervisor"),
        headers=_auth(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == shift["id"]
    assert body["assigned_employee_account_id"] is None
    assert body["role_required"] == "supervisor"
    assert body["start_time"].startswith("2026-04-21T10:00:00")
    assert body["end_time"].startswith("2026-04-21T18:00:00")

    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-04-20"},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200
    assert weekly_response.json()["shifts"] == [body]

    with test_session_local() as db:
        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "shift_updated",
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == shift["id"],
            )
        )
        assert audit_log is not None


def test_update_rejects_invalid_time_range(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i4-time-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I4-B-{uuid.uuid4()}")
    shift = _create_site_shift(client, admin, site_id=store["id"])

    response = client.patch(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}",
        json=_update_payload(
            start_time="2026-04-21T18:00:00Z",
            end_time="2026-04-21T10:00:00Z",
        ),
        headers=_auth(admin),
    )

    assert response.status_code == 422


def test_cross_tenant_and_wrong_site_update_rejected(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-i4-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-i4-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a, f"I4-C-{uuid.uuid4()}")
    store_other = _create_store(client, admin_a, f"I4-D-{uuid.uuid4()}")
    shift = _create_site_shift(client, admin_a, site_id=store_a["id"])

    cross_tenant = client.patch(
        f"/api/v1/sites/{store_a['id']}/shifts/{shift['id']}",
        json=_update_payload(),
        headers=_auth(admin_b),
    )
    wrong_site = client.patch(
        f"/api/v1/sites/{store_other['id']}/shifts/{shift['id']}",
        json=_update_payload(),
        headers=_auth(admin_a),
    )

    assert cross_tenant.status_code == 404
    assert wrong_site.status_code == 404


def test_update_rejects_assigned_staff_from_wrong_site(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i4-staff-{uuid.uuid4()}@example.com")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i4-member-{uuid.uuid4()}@example.com",
    )
    store_a = _create_store(client, admin, f"I4-E-{uuid.uuid4()}")
    store_b = _create_store(client, admin, f"I4-F-{uuid.uuid4()}")
    _create_staff_profile(client, admin, user_id=member["id"], store_id=store_b["id"])
    shift = _create_site_shift(client, admin, site_id=store_a["id"])

    response = client.patch(
        f"/api/v1/sites/{store_a['id']}/shifts/{shift['id']}",
        json=_update_payload(assigned_employee_account_id=member["id"]),
        headers=_auth(admin),
    )

    assert response.status_code == 400


def test_admin_cancels_draft_shift_and_weekly_rota_excludes_it(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-i4-cancel-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I4-G-{uuid.uuid4()}")
    shift = _create_site_shift(client, admin, site_id=store["id"])

    response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}/cancel",
        headers=_auth(admin),
    )

    assert response.status_code == 200
    assert response.json()["id"] == shift["id"]

    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-04-20"},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200
    assert weekly_response.json()["shifts"] == []

    with test_session_local() as db:
        persisted = db.get(Shift, uuid.UUID(shift["id"]))
        assert persisted is not None
        assert persisted.status == "cancelled"
        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "shift_cancelled",
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == shift["id"],
            )
        )
        assert audit_log is not None


def test_cancelled_shift_cannot_be_edited_or_cancelled_again(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i4-done-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I4-H-{uuid.uuid4()}")
    shift = _create_site_shift(client, admin, site_id=store["id"])
    cancel_response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}/cancel",
        headers=_auth(admin),
    )
    assert cancel_response.status_code == 200

    edit_response = client.patch(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}",
        json=_update_payload(),
        headers=_auth(admin),
    )
    second_cancel_response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}/cancel",
        headers=_auth(admin),
    )

    assert edit_response.status_code == 409
    assert second_cancel_response.status_code == 409


def test_published_shift_cannot_be_edited_or_cancelled(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-i4-published-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I4-P-{uuid.uuid4()}")
    shift = _create_site_shift(client, admin, site_id=store["id"])

    with test_session_local() as db:
        persisted = db.get(Shift, uuid.UUID(shift["id"]))
        assert persisted is not None
        persisted.published_at = datetime.now(timezone.utc)
        db.commit()

    edit_response = client.patch(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}",
        json=_update_payload(),
        headers=_auth(admin),
    )
    cancel_response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{shift['id']}/cancel",
        headers=_auth(admin),
    )

    assert edit_response.status_code == 409
    assert cancel_response.status_code == 409
