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


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_i3_shift_create.db"
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
            "full_name": "Phase I3 Staff",
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
    display_name: str = "Phase I3 Staff",
) -> dict:
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user_id,
            "store_id": store_id,
            "display_name": display_name,
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


def test_unauthenticated_create_shift_rejected(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/sites/{uuid.uuid4()}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
    )

    assert response.status_code == 401


def test_member_create_shift_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i3-rbac-{uuid.uuid4()}@example.com")
    member_email = f"phase-i3-rbac-member-{uuid.uuid4()}@example.com"
    _create_tenant_member(client, admin, member_email)
    member = {"token": _login(client, member_email)}
    store = _create_store(client, admin, f"I3-RBAC-{uuid.uuid4()}")

    response = client.post(
        f"/api/v1/sites/{store['id']}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(member),
    )

    assert response.status_code == 403


def test_admin_creates_open_draft_shift_and_weekly_rota_includes_it(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-i3-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-A-{uuid.uuid4()}")

    body = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=None,
        role_required="Cashier",
    )

    assert body["assigned_employee_account_id"] is None
    assert body["role_required"] == "cashier"
    assert body["start_time"].startswith("2026-04-20T09:00:00")
    assert body["end_time"].startswith("2026-04-20T17:00:00")

    with test_session_local() as db:
        shift = db.get(Shift, uuid.UUID(body["id"]))
        assert shift is not None
        assert shift.tenant_id == uuid.UUID(admin["active_tenant_id"])
        assert shift.store_id == uuid.UUID(store["id"])
        assert shift.status == "scheduled"
        assert shift.published_at is None

        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.tenant_id == uuid.UUID(admin["active_tenant_id"]),
                AuditLog.user_id == uuid.UUID(admin["id"]),
                AuditLog.action == "shift_created",
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == body["id"],
            )
        )
        assert audit_log is not None

    weekly_response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": "2026-04-20"},
        headers=_auth(admin),
    )
    assert weekly_response.status_code == 200
    assert weekly_response.json()["shifts"] == [body]


def test_admin_creates_assigned_shift_for_staff_at_same_site(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"phase-i3-assign-{uuid.uuid4()}@example.com")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-member-{uuid.uuid4()}@example.com",
    )
    store = _create_store(client, admin, f"I3-B-{uuid.uuid4()}")
    _create_staff_profile(client, admin, user_id=member["id"], store_id=store["id"])

    body = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_employee_account_id=member["id"],
    )

    assert body["assigned_employee_account_id"] == member["id"]


def test_invalid_time_range_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i3-time-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"I3-C-{uuid.uuid4()}")

    response = client.post(
        f"/api/v1/sites/{store['id']}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T17:00:00Z",
            "end_time": "2026-04-20T09:00:00Z",
        },
        headers=_auth(admin),
    )

    assert response.status_code == 422


def test_cross_tenant_site_create_rejected(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"phase-i3-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"phase-i3-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a, f"I3-D-{uuid.uuid4()}")

    response = client.post(
        f"/api/v1/sites/{store_a['id']}/shifts",
        json={
            "assigned_employee_account_id": None,
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(admin_b),
    )

    assert response.status_code == 404


def test_assigned_staff_from_wrong_site_rejected(client: TestClient) -> None:
    admin = _register_and_login(client, f"phase-i3-wrong-site-{uuid.uuid4()}@example.com")
    member = _create_tenant_member(
        client,
        admin,
        f"phase-i3-wrong-site-member-{uuid.uuid4()}@example.com",
    )
    store_a = _create_store(client, admin, f"I3-E-{uuid.uuid4()}")
    store_b = _create_store(client, admin, f"I3-F-{uuid.uuid4()}")
    _create_staff_profile(client, admin, user_id=member["id"], store_id=store_b["id"])

    response = client.post(
        f"/api/v1/sites/{store_a['id']}/shifts",
        json={
            "assigned_employee_account_id": member["id"],
            "role_required": "cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(admin),
    )

    assert response.status_code == 400
