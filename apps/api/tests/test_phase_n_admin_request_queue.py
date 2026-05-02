from collections.abc import Generator
from datetime import datetime, timedelta, timezone
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
from apps.api.models.shift_request import ShiftRequest
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_n_admin_request_queue.db"
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _future_monday(days_ahead: int = 21) -> datetime:
    today = datetime.now(timezone.utc).date()
    target = today + timedelta(days=days_ahead)
    monday = target - timedelta(days=target.weekday())
    return datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)


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
    user = _register(client, email)
    return {
        "id": user["id"],
        "active_tenant_id": user["active_tenant_id"],
        "token": _login(client, email),
        "email": email,
    }


def _set_membership_role(test_session_local, *, user_id: str, tenant_id: str, role: str) -> None:
    with test_session_local() as db:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.user_id == uuid.UUID(user_id),
                TenantUser.tenant_id == uuid.UUID(tenant_id),
            )
        )
        assert membership is not None
        membership.role = role
        db.commit()


def _create_admin_user(client: TestClient, admin: dict, role: str = "member") -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"phase-n-user-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": "Phase N User",
            "role": role,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    body = response.json()
    body["token"] = _login(client, body["email"])
    return body


def _create_store(client: TestClient, admin: dict, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={"code": code, "name": f"Store {code}", "timezone": "Europe/London"},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _assign_store_manager(test_session_local, *, store_id: str, manager_user_id: str) -> None:
    with test_session_local() as db:
        store = db.get(Store, uuid.UUID(store_id))
        assert store is not None
        store.manager_user_id = uuid.UUID(manager_user_id)
        db.commit()


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
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200


def _create_staff_with_employee_account(
    client: TestClient,
    admin: dict,
    *,
    store_id: str,
    username: str,
) -> dict:
    user = _create_admin_user(client, admin)
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase N {username}",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


def _create_site_with_employee(client: TestClient, username: str = "alex") -> tuple[dict, dict, dict]:
    admin = _register_and_login(client, f"phase-n-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"N-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    staff = _create_staff_with_employee_account(client, admin, store_id=store["id"], username=username)
    return admin, store, staff


def _employee_login(client: TestClient, *, site_id: str, username: str) -> str:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_shift(client: TestClient, admin: dict, store_id: str, user_id: str) -> dict:
    start_at = _future_monday() + timedelta(days=1, hours=9)
    end_at = start_at + timedelta(hours=8)
    response = client.post(
        f"/api/v1/sites/{store_id}/shifts",
        json={
            "assigned_employee_account_id": user_id,
            "role_required": "Cashier",
            "start_time": start_at.isoformat().replace("+00:00", "Z"),
            "end_time": end_at.isoformat().replace("+00:00", "Z"),
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    publish = client.post(
        f"/api/v1/sites/{store_id}/rota/publish",
        json={"week_start": _future_monday().date().isoformat()},
        headers=_auth(admin["token"]),
    )
    assert publish.status_code == 200
    return response.json()


def _create_leave_request(client: TestClient, store: dict, username: str) -> dict:
    employee_token = _employee_login(client, site_id=store["id"], username=username)
    response = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (_future_monday().date() + timedelta(days=2)).isoformat(),
            "end_date": (_future_monday().date() + timedelta(days=3)).isoformat(),
            "reason": "Family commitment",
        },
        headers=_auth(employee_token),
    )
    assert response.status_code == 201
    return response.json()


def _create_cover_request(client: TestClient, admin: dict, store: dict, staff: dict, username: str) -> tuple[dict, dict]:
    shift = _create_shift(client, admin, store["id"], staff["user"]["id"])
    employee_token = _employee_login(client, site_id=store["id"], username=username)
    response = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": shift["id"], "reason": "Need cover"},
        headers=_auth(employee_token),
    )
    assert response.status_code == 201
    return response.json(), shift


def test_admin_request_queue_empty_list_detail_and_sensitive_response(client: TestClient) -> None:
    admin, store, _ = _create_site_with_employee(client)

    empty = client.get(f"/api/v1/sites/{store['id']}/requests", headers=_auth(admin["token"]))
    assert empty.status_code == 200
    assert empty.json() == {"site_id": store["id"], "items": []}

    request = _create_leave_request(client, store, "alex")
    listed = client.get(f"/api/v1/sites/{store['id']}/requests", headers=_auth(admin["token"]))
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["id"] == request["id"]
    assert item["requester_display_name"] == "Phase N alex"
    assert item["request_type"] == "leave"
    assert "password" not in str(item).lower()
    assert "hourly" not in str(item).lower()

    detail = client.get(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}",
        headers=_auth(admin["token"]),
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == request["id"]


def test_admin_can_approve_and_reject_pending_requests_without_rota_mutation(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff = _create_site_with_employee(client)
    approve_request, shift = _create_cover_request(client, admin, store, staff, "alex")
    reject_request = _create_leave_request(client, store, "alex")
    with test_session_local() as db:
        original_shift = db.get(Shift, uuid.UUID(shift["id"]))
        assert original_shift is not None
        original_status = original_shift.status
        original_assigned_user_id = original_shift.assigned_user_id
        original_published_at = original_shift.published_at

    approved = client.post(
        f"/api/v1/sites/{store['id']}/requests/{approve_request['id']}/approve",
        json={"approval_reason": "Approved for test"},
        headers=_auth(admin["token"]),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["rota_updated"] is False

    rejected = client.post(
        f"/api/v1/sites/{store['id']}/requests/{reject_request['id']}/reject",
        json={"rejection_reason": "No cover available"},
        headers=_auth(admin["token"]),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rota_updated"] is False

    with test_session_local() as db:
        approved_row = db.get(ShiftRequest, uuid.UUID(approve_request["id"]))
        rejected_row = db.get(ShiftRequest, uuid.UUID(reject_request["id"]))
        unchanged_shift = db.get(Shift, uuid.UUID(shift["id"]))
        assert approved_row is not None
        assert approved_row.status == "approved"
        assert str(approved_row.approver_user_id) == admin["id"]
        assert approved_row.approval_reason == "Approved for test"
        assert approved_row.decided_at is not None
        assert rejected_row is not None
        assert rejected_row.status == "rejected"
        assert str(rejected_row.approver_user_id) == admin["id"]
        assert rejected_row.rejection_reason == "No cover available"
        assert rejected_row.decided_at is not None
        assert unchanged_shift is not None
        assert unchanged_shift.status == original_status
        assert unchanged_shift.assigned_user_id == original_assigned_user_id
        assert unchanged_shift.published_at == original_published_at
        actions = db.scalars(
            select(AuditLog.action).where(
                AuditLog.entity_type == "shift_request",
                AuditLog.entity_id.in_([approve_request["id"], reject_request["id"]]),
            )
        ).all()
        assert "request_approved" in actions
        assert "request_rejected" in actions


def test_non_pending_request_cannot_be_approved_or_rejected(client: TestClient) -> None:
    admin, store, _ = _create_site_with_employee(client)
    request = _create_leave_request(client, store, "alex")
    approved = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/approve",
        json={},
        headers=_auth(admin["token"]),
    )
    assert approved.status_code == 200

    approve_again = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/approve",
        json={},
        headers=_auth(admin["token"]),
    )
    reject_after_approve = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/reject",
        json={},
        headers=_auth(admin["token"]),
    )
    assert approve_again.status_code == 409
    assert reject_after_approve.status_code == 409
    assert approve_again.json()["error"]["code"] == "REQUEST_NOT_PENDING"
    assert reject_after_approve.json()["error"]["code"] == "REQUEST_NOT_PENDING"


def test_employee_token_and_unassigned_manager_cannot_access_queue(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, _ = _create_site_with_employee(client)
    other_store = _create_store(client, admin, f"N-OTHER-{uuid.uuid4()}")
    manager = _create_admin_user(client, admin)
    _set_membership_role(
        test_session_local,
        user_id=manager["id"],
        tenant_id=admin["active_tenant_id"],
        role="manager",
    )
    _assign_store_manager(test_session_local, store_id=store["id"], manager_user_id=manager["id"])
    employee_token = _employee_login(client, site_id=store["id"], username="alex")

    employee_response = client.get(f"/api/v1/sites/{store['id']}/requests", headers=_auth(employee_token))
    assert employee_response.status_code == 401

    manager_ok = client.get(f"/api/v1/sites/{store['id']}/requests", headers=_auth(manager["token"]))
    manager_bad = client.get(f"/api/v1/sites/{other_store['id']}/requests", headers=_auth(manager["token"]))
    assert manager_ok.status_code == 200
    assert manager_bad.status_code == 404


def test_cross_site_and_cross_tenant_request_access_is_safe(client: TestClient) -> None:
    admin_a, store_a, _ = _create_site_with_employee(client, username="alex")
    request_a = _create_leave_request(client, store_a, "alex")
    store_b = _create_store(client, admin_a, f"N-SAME-TENANT-{uuid.uuid4()}")
    admin_c, store_c, _ = _create_site_with_employee(client, username="casey")

    cross_site = client.get(
        f"/api/v1/sites/{store_b['id']}/requests/{request_a['id']}",
        headers=_auth(admin_a["token"]),
    )
    cross_tenant = client.get(
        f"/api/v1/sites/{store_c['id']}/requests/{request_a['id']}",
        headers=_auth(admin_c["token"]),
    )
    assert cross_site.status_code == 404
    assert cross_site.json()["error"]["code"] == "REQUEST_NOT_FOUND"
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "REQUEST_NOT_FOUND"


def test_owner_role_can_access_all_tenant_sites(client: TestClient, test_session_local) -> None:
    admin, store, _ = _create_site_with_employee(client)
    _create_store(client, admin, f"N-OWNER-OTHER-{uuid.uuid4()}")
    _set_membership_role(
        test_session_local,
        user_id=admin["id"],
        tenant_id=admin["active_tenant_id"],
        role="owner",
    )

    response = client.get(f"/api/v1/sites/{store['id']}/requests", headers=_auth(admin["token"]))
    assert response.status_code == 200
