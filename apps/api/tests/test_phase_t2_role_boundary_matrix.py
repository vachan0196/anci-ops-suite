from datetime import timedelta
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.models.shift_request import ShiftRequest
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
from apps.api.tests.test_phase_t0_tenant_role_security_gate import (
    PASSWORD,
    _auth,
    _create_staff_with_employee_account,
    _create_store,
    _create_tenant_user,
    _employee_login,
    _future_monday,
    _legacy_access_token,
    _login_admin,
    _register_owner,
    client,
    test_session_local,
)


def _create_admin(client: TestClient, owner: dict, label: str) -> dict:
    user = _create_tenant_user(client, owner, role="admin", label=f"t2-{label}")
    user["token"] = _login_admin(client, user["email"])
    return user


def _staff_profile_from_db(test_session_local, staff_id: str) -> StaffProfile:
    db = test_session_local()
    try:
        profile = db.get(StaffProfile, uuid.UUID(staff_id))
        assert profile is not None
        db.expunge(profile)
        return profile
    finally:
        db.close()


def _store_from_db(test_session_local, store_id: str) -> Store:
    db = test_session_local()
    try:
        store = db.get(Store, uuid.UUID(store_id))
        assert store is not None
        db.expunge(store)
        return store
    finally:
        db.close()


def _shift_request_from_db(test_session_local, request_id: str) -> ShiftRequest:
    db = test_session_local()
    try:
        request = db.get(ShiftRequest, uuid.UUID(request_id))
        assert request is not None
        db.expunge(request)
        return request
    finally:
        db.close()


def _create_employee_context(client: TestClient, owner: dict, label: str) -> tuple[dict, dict, str]:
    store = _create_store(client, owner, f"t2-{label}")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username=f"t2-{label}-{uuid.uuid4().hex[:8]}",
        hourly_rate="14.25",
        rtw_status="verified",
    )
    employee_token = _employee_login(
        client,
        site_id=store["id"],
        username=staff["profile"]["display_name"].lower().replace("phase t0 ", ""),
    )
    return store, staff, employee_token


def _create_leave_request(client: TestClient, employee_token: str) -> dict:
    week = _future_monday()
    response = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "leave",
            "start_date": (week + timedelta(days=2)).isoformat(),
            "end_date": (week + timedelta(days=2)).isoformat(),
            "reason": "Phase T2 matrix leave request",
        },
        headers=_auth(employee_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_ct_staff_pay_rtw_read_fields_are_owner_only(client: TestClient) -> None:
    owner = _register_owner(client, "t2-staff-read-owner")
    admin = _create_admin(client, owner, "staff-read")
    store = _create_store(client, owner, "staff-read")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="t2-staff-read",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    owner_list_response = client.get("/api/v1/staff", headers=_auth(owner["token"]))
    assert owner_list_response.status_code == 200, owner_list_response.text
    owner_listed = owner_list_response.json()
    assert owner_listed[0]["id"] == staff["profile"]["id"]
    assert owner_listed[0]["hourly_rate"] == "14.25"
    assert owner_listed[0]["pay_type"] == "hourly"
    assert owner_listed[0]["rtw_status"] == "verified"
    assert owner_listed[0]["rtw_checked_at"] is not None
    assert owner_listed[0]["rtw_checked_by_user_id"] == owner["id"]

    list_response = client.get("/api/v1/staff", headers=_auth(admin["token"]))
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert listed[0]["id"] == staff["profile"]["id"]
    assert "hourly_rate" not in listed[0]
    assert "pay_type" not in listed[0]
    assert "rtw_status" not in listed[0]

    owner_detail_response = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(owner["token"]),
    )
    assert owner_detail_response.status_code == 200, owner_detail_response.text
    owner_detail = owner_detail_response.json()
    assert owner_detail["hourly_rate"] == "14.25"
    assert owner_detail["pay_type"] == "hourly"
    assert owner_detail["rtw_status"] == "verified"

    detail_response = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(admin["token"]),
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert "hourly_rate" not in detail
    assert "pay_type" not in detail
    assert "rtw_status" not in detail


def test_ct_owner_can_create_and_update_staff_pay_rtw_fields(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "t2-staff-write-owner")
    store = _create_store(client, owner, "staff-write")
    member = _create_tenant_user(client, owner, role="member", label="t2-staff-write-member")

    create_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": member["id"],
            "store_id": store["id"],
            "display_name": "Phase T2 Staff Write",
            "job_title": "Cashier",
            "pay_type": "hourly",
            "hourly_rate": "13.75",
            "rtw_status": "pending",
            "is_active": True,
        },
        headers=_auth(owner["token"]),
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["hourly_rate"] == "13.75"
    assert create_response.json()["rtw_status"] == "pending"

    update_response = client.patch(
        f"/api/v1/staff/{create_response.json()['id']}",
        json={"hourly_rate": "16.50", "rtw_status": "expired"},
        headers=_auth(owner["token"]),
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["hourly_rate"] == "16.50"
    assert update_response.json()["rtw_status"] == "expired"
    assert update_response.json()["rtw_checked_by_user_id"] == owner["id"]

    persisted = _staff_profile_from_db(test_session_local, create_response.json()["id"])
    assert str(persisted.hourly_rate) == "16.50"
    assert persisted.rtw_status == "expired"


def test_ct_member_and_employee_denied_staff_pay_rtw_mutation_without_state_change(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "t2-staff-denied-owner")
    store, staff, employee_token = _create_employee_context(client, owner, "staff-denied")
    legacy_member_token = _legacy_access_token(staff["user"]["id"])

    member_update = client.patch(
        f"/api/v1/staff/{staff['profile']['id']}",
        json={"hourly_rate": "99.99", "rtw_status": "expired"},
        headers=_auth(legacy_member_token),
    )
    assert member_update.status_code == 403
    assert member_update.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    employee_update = client.patch(
        f"/api/v1/staff/{staff['profile']['id']}",
        json={"hourly_rate": "88.88", "rtw_status": "expired"},
        headers=_auth(employee_token),
    )
    assert employee_update.status_code == 401
    assert employee_update.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    persisted = _staff_profile_from_db(test_session_local, staff["profile"]["id"])
    assert str(persisted.hourly_rate) == "14.25"
    assert persisted.rtw_status == "verified"
    assert str(persisted.store_id) == store["id"]


def test_ct_cross_tenant_staff_pay_rtw_access_blocked_without_state_change(
    client: TestClient,
    test_session_local,
) -> None:
    owner_a = _register_owner(client, "t2-staff-cross-owner-a")
    owner_b = _register_owner(client, "t2-staff-cross-owner-b")
    store_b = _create_store(client, owner_b, "staff-cross-b")
    staff_b = _create_staff_with_employee_account(
        client,
        owner_b,
        store_id=store_b["id"],
        username="t2-staff-cross-b",
        hourly_rate="15.75",
        rtw_status="verified",
    )

    cross_read = client.get(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        headers=_auth(owner_a["token"]),
    )
    assert cross_read.status_code == 404
    assert cross_read.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"

    cross_update = client.patch(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        json={"hourly_rate": "99.99", "rtw_status": "expired"},
        headers=_auth(owner_a["token"]),
    )
    assert cross_update.status_code == 404
    assert cross_update.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"

    persisted = _staff_profile_from_db(test_session_local, staff_b["profile"]["id"])
    assert str(persisted.hourly_rate) == "15.75"
    assert persisted.rtw_status == "verified"


def test_ct_admin_can_create_admin_and_member_users(client: TestClient) -> None:
    owner = _register_owner(client, "t2-admin-users-owner")
    admin = _create_admin(client, owner, "admin-users")

    owner_created_admin = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"t2-owner-created-admin-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": "Phase T2 Owner Created Admin",
            "role": "admin",
        },
        headers=_auth(owner["token"]),
    )
    assert owner_created_admin.status_code == 201, owner_created_admin.text
    assert owner_created_admin.json()["role"] == "admin"
    assert owner_created_admin.json()["active_tenant_id"] == owner["active_tenant_id"]

    created_admin = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"t2-created-admin-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": "Phase T2 Created Admin",
            "role": "admin",
        },
        headers=_auth(admin["token"]),
    )
    assert created_admin.status_code == 201, created_admin.text
    assert created_admin.json()["role"] == "admin"
    assert created_admin.json()["active_tenant_id"] == owner["active_tenant_id"]

    created_member = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"t2-created-member-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": "Phase T2 Created Member",
            "role": "member",
        },
        headers=_auth(admin["token"]),
    )
    assert created_member.status_code == 201, created_member.text
    assert created_member.json()["role"] == "member"
    assert created_member.json()["active_tenant_id"] == owner["active_tenant_id"]


def test_ct_admin_user_create_rejects_owner_member_and_employee_without_user_creation(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "t2-admin-users-denied-owner")
    store, staff, employee_token = _create_employee_context(client, owner, "admin-users-denied")
    legacy_member_token = _legacy_access_token(staff["user"]["id"])

    owner_role_email = f"t2-owner-role-{uuid.uuid4()}@example.com"
    owner_role = client.post(
        "/api/v1/admin/users",
        json={
            "email": owner_role_email,
            "password": PASSWORD,
            "full_name": "Phase T2 Owner Role",
            "role": "owner",
        },
        headers=_auth(owner["token"]),
    )
    assert owner_role.status_code == 400
    assert owner_role.json()["error"]["code"] == "TENANT_ROLE_INVALID"

    member_email = f"t2-member-denied-{uuid.uuid4()}@example.com"
    member_create = client.post(
        "/api/v1/admin/users",
        json={
            "email": member_email,
            "password": PASSWORD,
            "full_name": "Phase T2 Member Denied",
            "role": "admin",
        },
        headers=_auth(legacy_member_token),
    )
    assert member_create.status_code == 403
    assert member_create.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    employee_email = f"t2-employee-denied-{uuid.uuid4()}@example.com"
    employee_create = client.post(
        "/api/v1/admin/users",
        json={
            "email": employee_email,
            "password": PASSWORD,
            "full_name": "Phase T2 Employee Denied",
            "role": "admin",
        },
        headers=_auth(employee_token),
    )
    assert employee_create.status_code == 401
    assert employee_create.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    for email in [owner_role_email, member_email, employee_email]:
        login = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": PASSWORD},
        )
        assert login.status_code == 401
    assert store["id"]


def test_ct_employee_legacy_admin_style_routes_accept_member_bearer_token(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "t2-employee-legacy-owner")
    store, staff, _employee_token = _create_employee_context(client, owner, "employee-legacy")
    legacy_member_token = _legacy_access_token(staff["user"]["id"])
    week = _future_monday()

    profile = client.get("/api/v1/employee/me/profile", headers=_auth(legacy_member_token))
    assert profile.status_code == 200, profile.text
    assert profile.json()["staff_id"] == staff["profile"]["id"]
    assert profile.json()["hourly_rate"] == 14.25
    assert profile.json()["pay_type"] == "hourly"
    assert "rtw_status" not in profile.json()

    home = client.get(
        "/api/v1/employee/home",
        params={"week_start": week.isoformat()},
        headers=_auth(legacy_member_token),
    )
    assert home.status_code == 200, home.text
    assert home.json()["selected_store"]["id"] == store["id"]

    rota = client.get(
        "/api/v1/employee/me/rota",
        params={"week_start": week.isoformat()},
        headers=_auth(legacy_member_token),
    )
    assert rota.status_code == 200, rota.text
    assert rota.json()["selected_store"]["id"] == store["id"]

    labour = client.get(
        "/api/v1/employee/me/labour-intelligence",
        params={"week_start": week.isoformat()},
        headers=_auth(legacy_member_token),
    )
    assert labour.status_code == 200, labour.text
    assert labour.json()["estimated_pay_this_week"] == 0.0


def test_ct_employee_account_token_rejected_by_legacy_admin_style_employee_routes(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "t2-employee-token-owner")
    _store, _staff, employee_token = _create_employee_context(client, owner, "employee-token")
    week = _future_monday()

    for path, params in [
        ("/api/v1/employee/me/profile", {}),
        ("/api/v1/employee/home", {"week_start": week.isoformat()}),
        ("/api/v1/employee/me/rota", {"week_start": week.isoformat()}),
        ("/api/v1/employee/me/labour-intelligence", {"week_start": week.isoformat()}),
    ]:
        response = client.get(path, params=params, headers=_auth(employee_token))
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


def test_ct_admin_can_approve_site_request_and_mutates_status(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "t2-site-approve-owner")
    admin = _create_admin(client, owner, "site-approve")
    store, _staff, employee_token = _create_employee_context(client, owner, "site-approve")
    leave_request = _create_leave_request(client, employee_token)

    approve = client.post(
        f"/api/v1/sites/{store['id']}/requests/{leave_request['id']}/approve",
        json={"approval_reason": "Phase T2 current truth"},
        headers=_auth(admin["token"]),
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    persisted = _shift_request_from_db(test_session_local, leave_request["id"])
    assert persisted.status == "approved"
    assert str(persisted.approver_user_id) == admin["id"]
    assert persisted.approval_reason == "Phase T2 current truth"


def test_ct_member_employee_and_cross_tenant_denied_site_request_approval_without_state_change(
    client: TestClient,
    test_session_local,
) -> None:
    owner_a = _register_owner(client, "t2-site-denied-owner-a")
    owner_b = _register_owner(client, "t2-site-denied-owner-b")
    store_a, staff_a, employee_token_a = _create_employee_context(client, owner_a, "site-denied-a")
    leave_request = _create_leave_request(client, employee_token_a)
    legacy_member_token = _legacy_access_token(staff_a["user"]["id"])

    member_approve = client.post(
        f"/api/v1/sites/{store_a['id']}/requests/{leave_request['id']}/approve",
        json={"approval_reason": "Should not persist"},
        headers=_auth(legacy_member_token),
    )
    assert member_approve.status_code == 404
    assert member_approve.json()["error"]["code"] == "SITE_NOT_FOUND"

    employee_approve = client.post(
        f"/api/v1/sites/{store_a['id']}/requests/{leave_request['id']}/approve",
        json={"approval_reason": "Should not persist"},
        headers=_auth(employee_token_a),
    )
    assert employee_approve.status_code == 401
    assert employee_approve.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    cross_approve = client.post(
        f"/api/v1/sites/{store_a['id']}/requests/{leave_request['id']}/approve",
        json={"approval_reason": "Should not persist"},
        headers=_auth(owner_b["token"]),
    )
    assert cross_approve.status_code == 404
    assert cross_approve.json()["error"]["code"] == "SITE_NOT_FOUND"

    persisted = _shift_request_from_db(test_session_local, leave_request["id"])
    assert persisted.status == "pending"
    assert persisted.approver_user_id is None
    assert persisted.approval_reason is None


def test_ct_admin_can_patch_store_profile_but_not_lifecycle_state(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "t2-store-patch-owner")
    admin = _create_admin(client, owner, "store-patch")
    store = _create_store(client, owner, "store-patch")

    normal_patch = client.patch(
        f"/api/v1/stores/{store['id']}",
        json={"name": "Phase T2 Patched Store", "city": "London"},
        headers=_auth(admin["token"]),
    )
    assert normal_patch.status_code == 200, normal_patch.text
    assert normal_patch.json()["name"] == "Phase T2 Patched Store"
    assert normal_patch.json()["is_active"] is True

    lifecycle_patch = client.patch(
        f"/api/v1/stores/{store['id']}",
        json={"is_active": False},
        headers=_auth(admin["token"]),
    )
    assert lifecycle_patch.status_code == 422

    persisted = _store_from_db(test_session_local, store["id"])
    assert persisted.name == "Phase T2 Patched Store"
    assert persisted.city == "London"
    assert persisted.is_active is True


def test_ct_member_employee_and_cross_tenant_denied_store_patch_without_state_change(
    client: TestClient,
    test_session_local,
) -> None:
    owner_a = _register_owner(client, "t2-store-denied-owner-a")
    owner_b = _register_owner(client, "t2-store-denied-owner-b")
    store_a, staff_a, employee_token_a = _create_employee_context(client, owner_a, "store-denied-a")
    legacy_member_token = _legacy_access_token(staff_a["user"]["id"])

    member_patch = client.patch(
        f"/api/v1/stores/{store_a['id']}",
        json={"name": "Member Should Not Persist"},
        headers=_auth(legacy_member_token),
    )
    assert member_patch.status_code == 403
    assert member_patch.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    employee_patch = client.patch(
        f"/api/v1/stores/{store_a['id']}",
        json={"name": "Employee Should Not Persist"},
        headers=_auth(employee_token_a),
    )
    assert employee_patch.status_code == 401
    assert employee_patch.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    cross_patch = client.patch(
        f"/api/v1/stores/{store_a['id']}",
        json={"name": "Cross Should Not Persist"},
        headers=_auth(owner_b["token"]),
    )
    assert cross_patch.status_code == 404
    assert cross_patch.json()["error"]["code"] == "STORE_NOT_FOUND"

    lifecycle_patch = client.patch(
        f"/api/v1/stores/{store_a['id']}",
        json={"is_active": False},
        headers=_auth(legacy_member_token),
    )
    assert lifecycle_patch.status_code == 403
    assert lifecycle_patch.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    persisted = _store_from_db(test_session_local, store_a["id"])
    assert persisted.name == store_a["name"]
    assert persisted.is_active is True


def test_ct_member_not_admin_portal_but_legacy_member_token_can_read_member_scoped_routes(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "t2-member-boundary-owner")
    store, staff, employee_token = _create_employee_context(client, owner, "member-boundary")
    legacy_member_token = _legacy_access_token(staff["user"]["id"])

    login = client.post(
        "/api/v1/auth/login",
        data={"username": staff["user"]["email"], "password": PASSWORD},
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "AUTH_ADMIN_PORTAL_ROLE_REQUIRED"

    stores = client.get("/api/v1/stores", headers=_auth(legacy_member_token))
    assert stores.status_code == 200, stores.text
    assert [item["id"] for item in stores.json()] == [store["id"]]

    own_staff = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(legacy_member_token),
    )
    assert own_staff.status_code == 200, own_staff.text
    assert own_staff.json()["id"] == staff["profile"]["id"]

    employee_admin_route = client.get("/api/v1/stores", headers=_auth(employee_token))
    assert employee_admin_route.status_code == 401
    assert employee_admin_route.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


def test_ct_cross_tenant_member_scoped_routes_do_not_leak_resources(
    client: TestClient,
) -> None:
    owner_a = _register_owner(client, "t2-member-cross-owner-a")
    owner_b = _register_owner(client, "t2-member-cross-owner-b")
    store_a, staff_a, _employee_token_a = _create_employee_context(client, owner_a, "member-cross-a")
    store_b, staff_b, _employee_token_b = _create_employee_context(client, owner_b, "member-cross-b")
    legacy_member_token_a = _legacy_access_token(staff_a["user"]["id"])

    stores = client.get("/api/v1/stores", headers=_auth(legacy_member_token_a))
    assert stores.status_code == 200, stores.text
    assert [item["id"] for item in stores.json()] == [store_a["id"]]
    assert store_b["id"] not in stores.text

    cross_store = client.get(f"/api/v1/stores/{store_b['id']}", headers=_auth(legacy_member_token_a))
    assert cross_store.status_code == 404
    assert cross_store.json()["error"]["code"] == "STORE_NOT_FOUND"

    cross_staff = client.get(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        headers=_auth(legacy_member_token_a),
    )
    assert cross_staff.status_code == 404
    assert cross_staff.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"
