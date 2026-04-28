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
from apps.api.models.shift import Shift


PASSWORD = "password123"
WEEK_START = "2026-04-20"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_j_rota_publish.db"
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
            "full_name": "Phase J Staff",
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
            "display_name": "Phase J Staff",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _configure_opening_hours(client: TestClient, admin: dict, store_id: str) -> None:
    response = client.put(
        f"/api/v1/stores/{store_id}/opening-hours",
        json={
            "opening_hours": [
                {
                    "day_of_week": day,
                    "open_time": "06:00",
                    "close_time": "22:00",
                    "is_closed": False,
                }
                for day in range(7)
            ]
        },
        headers=_auth(admin),
    )
    assert response.status_code == 200


def _make_store_ready(client: TestClient, admin: dict, store_id: str) -> dict:
    staff_user = _create_tenant_member(
        client,
        admin,
        f"phase-j-staff-{uuid.uuid4()}@example.com",
    )
    _create_staff_profile(client, admin, user_id=staff_user["id"], store_id=store_id)
    _configure_opening_hours(client, admin, store_id)
    return staff_user


def _create_site_shift(
    client: TestClient,
    admin: dict,
    *,
    site_id: str,
    start_time: str = "2026-04-20T09:00:00Z",
    end_time: str = "2026-04-20T17:00:00Z",
) -> dict:
    response = client.post(
        f"/api/v1/sites/{site_id}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "Cashier",
            "start_time": start_time,
            "end_time": end_time,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _publish_rota(client: TestClient, admin: dict, site_id: str):
    return client.post(
        f"/api/v1/sites/{site_id}/rota/publish",
        json={"week_start": WEEK_START},
        headers=_auth(admin),
    )


def _unpublish_rota(client: TestClient, admin: dict, site_id: str):
    return client.post(
        f"/api/v1/sites/{site_id}/rota/unpublish",
        json={"week_start": WEEK_START},
        headers=_auth(admin),
    )


def test_unauthenticated_publish_and_unpublish_rejected(client: TestClient) -> None:
    site_id = uuid.uuid4()
    publish_response = client.post(
        f"/api/v1/sites/{site_id}/rota/publish",
        json={"week_start": WEEK_START},
    )
    unpublish_response = client.post(
        f"/api/v1/sites/{site_id}/rota/unpublish",
        json={"week_start": WEEK_START},
    )

    assert publish_response.status_code == 401
    assert unpublish_response.status_code == 401


def test_cannot_publish_when_site_not_ready(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-j-not-ready-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"J-NR-{uuid.uuid4()}")
    _create_site_shift(client, admin, site_id=store["id"])

    response = _publish_rota(client, admin, store["id"])

    assert response.status_code == 409


def test_cannot_publish_empty_week(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-j-empty-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"J-EMPTY-{uuid.uuid4()}")
    _make_store_ready(client, admin, store["id"])

    response = _publish_rota(client, admin, store["id"])

    assert response.status_code == 409


def test_admin_publishes_active_draft_shifts_and_weekly_state_updates(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-j-publish-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"J-PUB-{uuid.uuid4()}")
    _make_store_ready(client, admin, store["id"])
    shift = _create_site_shift(client, admin, site_id=store["id"])

    response = _publish_rota(client, admin, store["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["is_published"] is True
    assert body["published_shift_count"] == 1
    assert body["draft_shift_count"] == 0
    assert [item["id"] for item in body["shifts"]] == [shift["id"]]

    with test_session_local() as db:
        persisted = db.get(Shift, uuid.UUID(shift["id"]))
        assert persisted is not None
        assert persisted.published_at is not None
        assert persisted.published_by_user_id == uuid.UUID(admin["id"])
        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "rota_published",
                AuditLog.entity_type == "rota",
                AuditLog.entity_id == f"{store['id']}:{WEEK_START}",
            )
        )
        assert audit_log is not None


def test_cancelled_shifts_are_not_published(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-j-cancel-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"J-CAN-{uuid.uuid4()}")
    _make_store_ready(client, admin, store["id"])
    active_shift = _create_site_shift(client, admin, site_id=store["id"])
    cancelled_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        start_time="2026-04-21T09:00:00Z",
        end_time="2026-04-21T17:00:00Z",
    )
    cancel_response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{cancelled_shift['id']}/cancel",
        headers=_auth(admin),
    )
    assert cancel_response.status_code == 200

    response = _publish_rota(client, admin, store["id"])

    assert response.status_code == 200
    assert response.json()["published_shift_count"] == 1
    with test_session_local() as db:
        active = db.get(Shift, uuid.UUID(active_shift["id"]))
        cancelled = db.get(Shift, uuid.UUID(cancelled_shift["id"]))
        assert active is not None
        assert cancelled is not None
        assert active.published_at is not None
        assert cancelled.published_at is None


def test_admin_unpublishes_published_rota_and_audit_is_written(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-j-unpublish-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"J-UNPUB-{uuid.uuid4()}")
    _make_store_ready(client, admin, store["id"])
    shift = _create_site_shift(client, admin, site_id=store["id"])
    publish_response = _publish_rota(client, admin, store["id"])
    assert publish_response.status_code == 200

    response = _unpublish_rota(client, admin, store["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["is_published"] is False
    assert body["published_shift_count"] == 0
    assert body["draft_shift_count"] == 1
    with test_session_local() as db:
        persisted = db.get(Shift, uuid.UUID(shift["id"]))
        assert persisted is not None
        assert persisted.published_at is None
        assert persisted.published_by_user_id is None
        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "rota_unpublished",
                AuditLog.entity_type == "rota",
                AuditLog.entity_id == f"{store['id']}:{WEEK_START}",
            )
        )
        assert audit_log is not None


def test_cannot_unpublish_when_no_published_rota_exists(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-j-no-pub-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"J-NOPUB-{uuid.uuid4()}")
    _make_store_ready(client, admin, store["id"])
    _create_site_shift(client, admin, site_id=store["id"])

    response = _unpublish_rota(client, admin, store["id"])

    assert response.status_code == 409


def test_cross_tenant_and_wrong_site_publish_rejected(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-j-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-j-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a, f"J-A-{uuid.uuid4()}")
    store_other = _create_store(client, admin_a, f"J-OTHER-{uuid.uuid4()}")
    _make_store_ready(client, admin_a, store_a["id"])
    _create_site_shift(client, admin_a, site_id=store_a["id"])

    cross_tenant = client.post(
        f"/api/v1/sites/{store_a['id']}/rota/publish",
        json={"week_start": WEEK_START},
        headers=_auth(admin_b),
    )
    wrong_site = client.post(
        f"/api/v1/sites/{store_other['id']}/rota/publish",
        json={"week_start": WEEK_START},
        headers=_auth(admin_a),
    )

    assert cross_tenant.status_code == 404
    assert wrong_site.status_code == 409
