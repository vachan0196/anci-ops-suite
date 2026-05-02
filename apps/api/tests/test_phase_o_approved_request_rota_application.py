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


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_o_approved_request_rota_application.db"
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


def _create_admin_user(client: TestClient, admin: dict) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"phase-o-user-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": "Phase O User",
            "role": "member",
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
            "display_name": f"Phase O {username}",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


def _create_site_with_employees(
    client: TestClient,
    usernames: list[str],
) -> tuple[dict, dict, dict[str, dict]]:
    admin = _register_and_login(client, f"phase-o-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"O-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    staff = {
        username: _create_staff_with_employee_account(
            client,
            admin,
            store_id=store["id"],
            username=username,
        )
        for username in usernames
    }
    return admin, store, staff


def _employee_login(client: TestClient, *, site_id: str, username: str) -> str:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_leave_request(client: TestClient, store: dict, username: str, start_date, end_date) -> dict:
    employee_token = _employee_login(client, site_id=store["id"], username=username)
    response = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "reason": "Family commitment",
        },
        headers=_auth(employee_token),
    )
    assert response.status_code == 201
    return response.json()


def _add_shift(
    db: Session,
    *,
    tenant_id: str,
    store_id: str,
    assigned_user_id: str,
    start_at: datetime,
    published: bool = True,
    status: str = "scheduled",
) -> Shift:
    shift = Shift(
        tenant_id=uuid.UUID(tenant_id),
        store_id=uuid.UUID(store_id),
        assigned_user_id=uuid.UUID(assigned_user_id),
        start_at=start_at,
        end_at=start_at + timedelta(hours=8),
        required_role="cashier",
        status=status,
        published_at=start_at - timedelta(days=1) if published else None,
    )
    db.add(shift)
    db.flush()
    return shift


def test_approving_leave_opens_only_matching_published_scheduled_shifts(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff = _create_site_with_employees(client, ["alex", "blair"])
    other_admin, other_store, other_staff = _create_site_with_employees(client, ["casey"])
    same_tenant_other_store = _create_store(client, admin, f"O-OTHER-{uuid.uuid4()}")
    week = _future_monday()
    leave_start = (week + timedelta(days=1)).date()
    leave_end = (week + timedelta(days=2)).date()
    request = _create_leave_request(client, store, "alex", leave_start, leave_end)

    with test_session_local() as db:
        affected = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=9),
        )
        same_requester_second_day = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=2, hours=9),
        )
        other_employee = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["blair"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=9),
        )
        other_site = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=same_tenant_other_store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=9),
        )
        other_tenant = _add_shift(
            db,
            tenant_id=other_admin["active_tenant_id"],
            store_id=other_store["id"],
            assigned_user_id=other_staff["casey"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=9),
        )
        outside_range = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=5, hours=9),
        )
        draft = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=10),
            published=False,
        )
        cancelled = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=2, hours=10),
            status="cancelled",
        )
        ids = {
            "affected": affected.id,
            "same_requester_second_day": same_requester_second_day.id,
            "other_employee": other_employee.id,
            "other_site": other_site.id,
            "other_tenant": other_tenant.id,
            "outside_range": outside_range.id,
            "draft": draft.id,
            "cancelled": cancelled.id,
        }
        db.commit()

    response = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/approve",
        json={"approval_reason": "Approved leave"},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["rota_updated"] is True
    assert response.json()["affected_shift_count"] == 2

    with test_session_local() as db:
        opened = db.get(Shift, ids["affected"])
        opened_second = db.get(Shift, ids["same_requester_second_day"])
        assert opened is not None
        assert opened_second is not None
        assert opened.assigned_user_id is None
        assert opened_second.assigned_user_id is None
        assert opened.status == "scheduled"
        assert opened.published_at is not None
        assert db.get(Shift, ids["other_employee"]).assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])
        assert db.get(Shift, ids["other_site"]).assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert db.get(Shift, ids["other_tenant"]).assigned_user_id == uuid.UUID(other_staff["casey"]["user"]["id"])
        assert db.get(Shift, ids["outside_range"]).assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert db.get(Shift, ids["draft"]).assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert db.get(Shift, ids["cancelled"]).assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert db.get(ShiftRequest, uuid.UUID(request["id"])).status == "approved"
        shift_count = db.scalar(select(Shift).where(Shift.id == ids["affected"])).id
        assert shift_count == ids["affected"]
        audit_actions = db.scalars(
            select(AuditLog.action).where(
                AuditLog.entity_type.in_(["shift_request", "shift"]),
                AuditLog.entity_id.in_([request["id"], str(ids["affected"]), str(ids["same_requester_second_day"])]),
            )
        ).all()
        assert "request_approved" in audit_actions
        assert audit_actions.count("approved_leave_opened_shift") == 2

    employee_token = _employee_login(client, site_id=store["id"], username="alex")
    rota = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": week.date().isoformat()},
        headers=_auth(employee_token),
    )
    assert rota.status_code == 200
    assert all(shift["id"] != str(ids["affected"]) for shift in rota.json()["shifts"])


def test_swap_and_cover_approval_do_not_mutate_rota(client: TestClient, test_session_local) -> None:
    admin, store, staff = _create_site_with_employees(client, ["alex", "blair"])
    week = _future_monday()
    with test_session_local() as db:
        shift = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=9),
        )
        shift_id = shift.id
        db.commit()

    employee_token = _employee_login(client, site_id=store["id"], username="alex")
    cover = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": str(shift_id), "reason": "Need cover"},
        headers=_auth(employee_token),
    )
    assert cover.status_code == 201
    swap = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": str(shift_id),
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
            "reason": "Need swap",
        },
        headers=_auth(employee_token),
    )
    assert swap.status_code == 201

    for request_id in [cover.json()["id"], swap.json()["id"]]:
        approved = client.post(
            f"/api/v1/sites/{store['id']}/requests/{request_id}/approve",
            json={},
            headers=_auth(admin["token"]),
        )
        assert approved.status_code == 200
        assert approved.json()["rota_updated"] is False
        assert approved.json()["affected_shift_count"] == 0

    with test_session_local() as db:
        unchanged = db.get(Shift, shift_id)
        assert unchanged is not None
        assert unchanged.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])


def test_reject_leave_and_non_pending_approval_do_not_mutate_rota(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff = _create_site_with_employees(client, ["alex"])
    week = _future_monday()
    request = _create_leave_request(
        client,
        store,
        "alex",
        (week + timedelta(days=1)).date(),
        (week + timedelta(days=1)).date(),
    )
    with test_session_local() as db:
        shift = _add_shift(
            db,
            tenant_id=admin["active_tenant_id"],
            store_id=store["id"],
            assigned_user_id=staff["alex"]["user"]["id"],
            start_at=week + timedelta(days=1, hours=9),
        )
        shift_id = shift.id
        db.commit()

    rejected = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/reject",
        json={},
        headers=_auth(admin["token"]),
    )
    assert rejected.status_code == 200
    approve_rejected = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/approve",
        json={},
        headers=_auth(admin["token"]),
    )
    assert approve_rejected.status_code == 409
    assert approve_rejected.json()["error"]["code"] == "REQUEST_NOT_PENDING"

    with test_session_local() as db:
        unchanged = db.get(Shift, shift_id)
        assert unchanged is not None
        assert unchanged.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])


def test_employee_token_and_cross_tenant_request_cannot_apply_rota(client: TestClient) -> None:
    admin, store, _ = _create_site_with_employees(client, ["alex"])
    other_admin, other_store, _ = _create_site_with_employees(client, ["casey"])
    request = _create_leave_request(
        client,
        store,
        "alex",
        (_future_monday() + timedelta(days=1)).date(),
        (_future_monday() + timedelta(days=1)).date(),
    )
    employee_token = _employee_login(client, site_id=store["id"], username="alex")

    employee_attempt = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/approve",
        json={},
        headers=_auth(employee_token),
    )
    cross_tenant = client.post(
        f"/api/v1/sites/{other_store['id']}/requests/{request['id']}/approve",
        json={},
        headers=_auth(other_admin["token"]),
    )
    assert employee_attempt.status_code == 401
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "REQUEST_NOT_FOUND"
