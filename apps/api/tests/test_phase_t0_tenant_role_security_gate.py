from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_t0_tenant_role_security_gate.db"
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


def _future_monday(days_ahead: int = 14) -> date:
    today = datetime.now(timezone.utc).date()
    target = today + timedelta(days=days_ahead)
    return target - timedelta(days=target.weekday())


def _register_owner(client: TestClient, email_prefix: str) -> dict:
    email = f"{email_prefix}-{uuid.uuid4()}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    body = register.json()
    body["email"] = email
    body["token"] = login.json()["access_token"]
    return body


def _login_admin(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_tenant_user(
    client: TestClient,
    owner: dict,
    *,
    role: str,
    label: str,
) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"t0-{label}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Phase T0 {label}",
            "role": role,
        },
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _legacy_access_token(user_id: str) -> str:
    return create_access_token(user_id)


def _create_store(client: TestClient, owner: dict, label: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"T0-{label}-{uuid.uuid4()}",
            "name": f"Phase T0 {label}",
            "timezone": "Europe/London",
        },
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_staff_with_employee_account(
    client: TestClient,
    owner: dict,
    *,
    store_id: str,
    username: str,
    hourly_rate: str = "13.50",
    rtw_status: str = "verified",
) -> dict:
    user = _create_tenant_user(client, owner, role="member", label=username)
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase T0 {username}",
            "job_title": "Cashier",
            "pay_type": "hourly",
            "hourly_rate": hourly_rate,
            "rtw_status": rtw_status,
            "is_active": True,
        },
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 201, response.text
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


def _employee_login(client: TestClient, *, site_id: str, username: str) -> str:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_availability(client: TestClient, token: str, week: date, **overrides) -> dict:
    payload = {
        "week_start": week.isoformat(),
        "date": (week + timedelta(days=1)).isoformat(),
        "start_time": "09:00",
        "end_time": "17:00",
        "type": "available",
        "notes": "Phase T0 availability",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/employee/me/availability",
        json=payload,
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _leave_request_payload(week: date, **overrides) -> dict:
    payload = {
        "request_type": "leave",
        "start_date": (week + timedelta(days=2)).isoformat(),
        "end_date": (week + timedelta(days=2)).isoformat(),
        "reason": "Phase T0 leave request",
    }
    payload.update(overrides)
    return payload


def _complete_company_payload(label: str) -> dict:
    return {
        "company_name": f"Phase T0 {label} Ltd",
        "owner_name": f"Owner {label}",
        "business_email": f"owner-{label.lower()}@example.com",
        "phone_number": "07123456789",
        "registered_address": f"{label} Test Road",
    }


def test_company_profile_is_owner_only_and_scoped_to_active_tenant(client: TestClient) -> None:
    owner_a = _register_owner(client, "t0-company-owner-a")
    owner_b = _register_owner(client, "t0-company-owner-b")
    admin_a = _create_tenant_user(client, owner_a, role="admin", label="company-admin-a")
    admin_a_token = _login_admin(client, admin_a["email"])

    patch_a = client.patch(
        "/api/v1/company/profile",
        json=_complete_company_payload("Tenant A"),
        headers=_auth(owner_a["token"]),
    )
    assert patch_a.status_code == 200, patch_a.text

    patch_b = client.patch(
        "/api/v1/company/profile",
        json=_complete_company_payload("Tenant B"),
        headers=_auth(owner_b["token"]),
    )
    assert patch_b.status_code == 200, patch_b.text

    admin_read = client.get("/api/v1/company/profile", headers=_auth(admin_a_token))
    assert admin_read.status_code == 403
    assert admin_read.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    owner_a_read = client.get("/api/v1/company/profile", headers=_auth(owner_a["token"]))
    owner_b_read = client.get("/api/v1/company/profile", headers=_auth(owner_b["token"]))
    assert owner_a_read.status_code == 200, owner_a_read.text
    assert owner_b_read.status_code == 200, owner_b_read.text
    assert owner_a_read.json()["tenant_id"] == owner_a["active_tenant_id"]
    assert owner_b_read.json()["tenant_id"] == owner_b["active_tenant_id"]
    assert owner_a_read.json()["company_name"] == "Phase T0 Tenant A Ltd"
    assert owner_b_read.json()["company_name"] == "Phase T0 Tenant B Ltd"


def test_stores_reject_cross_tenant_read_readiness_and_mutation(client: TestClient) -> None:
    owner_a = _register_owner(client, "t0-store-owner-a")
    owner_b = _register_owner(client, "t0-store-owner-b")
    store_a = _create_store(client, owner_a, "store-a")
    store_b = _create_store(client, owner_b, "store-b")

    list_a = client.get("/api/v1/stores", headers=_auth(owner_a["token"]))
    assert list_a.status_code == 200, list_a.text
    assert [item["id"] for item in list_a.json()] == [store_a["id"]]
    assert store_b["id"] not in list_a.text

    cross_get = client.get(f"/api/v1/stores/{store_b['id']}", headers=_auth(owner_a["token"]))
    assert cross_get.status_code == 404
    assert cross_get.json()["error"]["code"] == "STORE_NOT_FOUND"

    cross_readiness = client.get(
        f"/api/v1/stores/{store_b['id']}/readiness",
        headers=_auth(owner_a["token"]),
    )
    assert cross_readiness.status_code == 404
    assert cross_readiness.json()["error"]["code"] == "STORE_NOT_FOUND"

    cross_patch = client.patch(
        f"/api/v1/stores/{store_b['id']}",
        json={"name": "Cross Tenant Write"},
        headers=_auth(owner_a["token"]),
    )
    assert cross_patch.status_code == 404
    assert cross_patch.json()["error"]["code"] == "STORE_NOT_FOUND"

    store_b_after = client.get(f"/api/v1/stores/{store_b['id']}", headers=_auth(owner_b["token"]))
    assert store_b_after.status_code == 200, store_b_after.text
    assert store_b_after.json()["name"] == store_b["name"]


def test_staff_rejects_cross_tenant_access_and_protects_sensitive_fields(client: TestClient) -> None:
    owner_a = _register_owner(client, "t0-staff-owner-a")
    owner_b = _register_owner(client, "t0-staff-owner-b")
    store_a = _create_store(client, owner_a, "staff-store-a")
    store_b = _create_store(client, owner_b, "staff-store-b")
    staff_a = _create_staff_with_employee_account(
        client,
        owner_a,
        store_id=store_a["id"],
        username="alex",
    )
    staff_b = _create_staff_with_employee_account(
        client,
        owner_b,
        store_id=store_b["id"],
        username="blair",
        hourly_rate="15.75",
    )

    list_a = client.get("/api/v1/staff", headers=_auth(owner_a["token"]))
    assert list_a.status_code == 200, list_a.text
    assert [item["id"] for item in list_a.json()] == [staff_a["profile"]["id"]]
    assert staff_b["profile"]["id"] not in list_a.text
    assert "15.75" not in list_a.text

    directory_a = client.get("/api/v1/staff/directory", headers=_auth(owner_a["token"]))
    assert directory_a.status_code == 200, directory_a.text
    assert [item["id"] for item in directory_a.json()] == [staff_a["profile"]["id"]]
    assert staff_b["profile"]["id"] not in directory_a.text

    cross_detail = client.get(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        headers=_auth(owner_a["token"]),
    )
    assert cross_detail.status_code == 404
    assert cross_detail.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"

    cross_update = client.patch(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        json={"hourly_rate": "99.99", "rtw_status": "expired"},
        headers=_auth(owner_a["token"]),
    )
    assert cross_update.status_code == 404
    assert cross_update.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"

    staff_b_after = client.get(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        headers=_auth(owner_b["token"]),
    )
    assert staff_b_after.status_code == 200, staff_b_after.text
    assert staff_b_after.json()["hourly_rate"] == "15.75"
    assert staff_b_after.json()["rtw_status"] == "verified"

    legacy_member_token = _legacy_access_token(staff_a["user"]["id"])
    coworker_detail = client.get(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        headers=_auth(legacy_member_token),
    )
    assert coworker_detail.status_code == 404
    assert coworker_detail.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"

    member_sensitive_update = client.patch(
        f"/api/v1/staff/{staff_a['profile']['id']}",
        json={"hourly_rate": "99.99", "rtw_status": "expired"},
        headers=_auth(legacy_member_token),
    )
    assert member_sensitive_update.status_code == 403
    assert member_sensitive_update.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"


def test_admin_member_and_employee_tokens_are_not_interchangeable(client: TestClient) -> None:
    owner = _register_owner(client, "t0-token-owner")
    store = _create_store(client, owner, "token-store")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="casey",
    )
    employee_token = _employee_login(client, site_id=store["id"], username="casey")

    employee_admin_api = client.get("/api/v1/stores", headers=_auth(employee_token))
    assert employee_admin_api.status_code == 401
    assert employee_admin_api.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    employee_staff_api = client.get("/api/v1/staff", headers=_auth(employee_token))
    assert employee_staff_api.status_code == 401
    assert employee_staff_api.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    admin_employee_api = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": _future_monday().isoformat()},
        headers=_auth(owner["token"]),
    )
    assert admin_employee_api.status_code == 401
    assert admin_employee_api.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    member_login = client.post(
        "/api/v1/auth/login",
        data={"username": staff["user"]["email"], "password": PASSWORD},
    )
    assert member_login.status_code == 403
    assert member_login.json()["error"]["code"] == "AUTH_ADMIN_PORTAL_ROLE_REQUIRED"


def test_employee_portal_is_self_only_and_site_scoped(client: TestClient) -> None:
    owner_a = _register_owner(client, "t0-employee-owner-a")
    owner_b = _register_owner(client, "t0-employee-owner-b")
    store_a = _create_store(client, owner_a, "employee-store-a")
    other_store_a = _create_store(client, owner_a, "employee-other-store-a")
    store_b = _create_store(client, owner_b, "employee-store-b")
    _create_staff_with_employee_account(client, owner_a, store_id=store_a["id"], username="alex")
    _create_staff_with_employee_account(client, owner_a, store_id=store_a["id"], username="blair")
    _create_staff_with_employee_account(client, owner_b, store_id=store_b["id"], username="devon")

    alex_token = _employee_login(client, site_id=store_a["id"], username="alex")
    blair_token = _employee_login(client, site_id=store_a["id"], username="blair")
    devon_token = _employee_login(client, site_id=store_b["id"], username="devon")
    week = _future_monday()

    alex_availability = _create_availability(client, alex_token, week)
    blair_availability = _create_availability(
        client,
        blair_token,
        week,
        date=(week + timedelta(days=2)).isoformat(),
    )

    alex_list = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat()},
        headers=_auth(alex_token),
    )
    assert alex_list.status_code == 200, alex_list.text
    assert [item["id"] for item in alex_list.json()["items"]] == [alex_availability["id"]]
    assert blair_availability["id"] not in alex_list.text

    delete_blair = client.delete(
        f"/api/v1/employee/me/availability/{blair_availability['id']}",
        headers=_auth(alex_token),
    )
    assert delete_blair.status_code == 404
    assert delete_blair.json()["error"]["code"] == "AVAILABILITY_NOT_FOUND"

    wrong_site = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat(), "store_id": other_store_a["id"]},
        headers=_auth(alex_token),
    )
    assert wrong_site.status_code == 404
    assert wrong_site.json()["error"]["code"] == "STORE_NOT_FOUND"

    other_tenant_site = client.get(
        "/api/v1/employee/me/availability",
        params={"week_start": week.isoformat(), "store_id": store_b["id"]},
        headers=_auth(alex_token),
    )
    assert other_tenant_site.status_code == 404
    assert other_tenant_site.json()["error"]["code"] == "STORE_NOT_FOUND"

    alex_leave = client.post(
        "/api/v1/employee/me/requests",
        json=_leave_request_payload(week),
        headers=_auth(alex_token),
    )
    assert alex_leave.status_code == 201, alex_leave.text

    blair_requests = client.get("/api/v1/employee/me/requests", headers=_auth(blair_token))
    assert blair_requests.status_code == 200, blair_requests.text
    assert blair_requests.json()["items"] == []
    assert alex_leave.json()["id"] not in blair_requests.text

    devon_requests = client.get("/api/v1/employee/me/requests", headers=_auth(devon_token))
    assert devon_requests.status_code == 200, devon_requests.text
    assert devon_requests.json()["items"] == []
    assert alex_leave.json()["id"] not in devon_requests.text
