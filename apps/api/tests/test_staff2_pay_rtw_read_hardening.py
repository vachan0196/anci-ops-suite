from fastapi.testclient import TestClient

from apps.api.tests.test_phase_t0_tenant_role_security_gate import (
    _auth,
    _create_staff_with_employee_account,
    _create_store,
    _create_tenant_user,
    _legacy_access_token,
    _login_admin,
    _register_owner,
    client,
    test_session_local,
)


SENSITIVE_STAFF_READ_FIELDS = {
    "hourly_rate",
    "pay_type",
    "rtw_status",
}


def _create_admin(client: TestClient, owner: dict, label: str) -> dict:
    user = _create_tenant_user(client, owner, role="admin", label=f"staff2-{label}")
    user["token"] = _login_admin(client, user["email"])
    return user


def _assert_sensitive_fields_present(body: dict) -> None:
    assert body["hourly_rate"] == "14.25"
    assert body["pay_type"] == "hourly"
    assert body["rtw_status"] == "verified"


def _assert_sensitive_fields_absent(body: dict) -> None:
    assert SENSITIVE_STAFF_READ_FIELDS.isdisjoint(body.keys())


def test_owner_staff_reads_include_pay_and_rtw_fields(client: TestClient) -> None:
    owner = _register_owner(client, "staff2-owner-read")
    store = _create_store(client, owner, "staff2-owner-read")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2-owner-read",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    list_response = client.get("/api/v1/staff", headers=_auth(owner["token"]))
    assert list_response.status_code == 200, list_response.text
    listed = next(item for item in list_response.json() if item["id"] == staff["profile"]["id"])
    _assert_sensitive_fields_present(listed)

    detail_response = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(owner["token"]),
    )
    assert detail_response.status_code == 200, detail_response.text
    _assert_sensitive_fields_present(detail_response.json())


def test_admin_staff_reads_omit_pay_and_rtw_fields(client: TestClient) -> None:
    owner = _register_owner(client, "staff2-admin-read")
    admin = _create_admin(client, owner, "admin-read")
    store = _create_store(client, owner, "staff2-admin-read")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2-admin-read",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    list_response = client.get("/api/v1/staff", headers=_auth(admin["token"]))
    assert list_response.status_code == 200, list_response.text
    listed = next(item for item in list_response.json() if item["id"] == staff["profile"]["id"])
    _assert_sensitive_fields_absent(listed)

    detail_response = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(admin["token"]),
    )
    assert detail_response.status_code == 200, detail_response.text
    _assert_sensitive_fields_absent(detail_response.json())


def test_member_staff_own_profile_read_omits_pay_and_rtw_fields(client: TestClient) -> None:
    owner = _register_owner(client, "staff2-member-read")
    store = _create_store(client, owner, "staff2-member-read")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2-member-read",
        hourly_rate="14.25",
        rtw_status="verified",
    )
    legacy_member_token = _legacy_access_token(staff["user"]["id"])

    list_response = client.get("/api/v1/staff", headers=_auth(legacy_member_token))
    assert list_response.status_code == 403

    detail_response = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(legacy_member_token),
    )
    assert detail_response.status_code == 200, detail_response.text
    _assert_sensitive_fields_absent(detail_response.json())

    me_response = client.get("/api/v1/staff/me", headers=_auth(legacy_member_token))
    assert me_response.status_code == 200, me_response.text
    _assert_sensitive_fields_absent(me_response.json())


def test_staff_directory_remains_trimmed(client: TestClient) -> None:
    owner = _register_owner(client, "staff2-directory")
    admin = _create_admin(client, owner, "directory")
    store = _create_store(client, owner, "staff2-directory")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2-directory",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    response = client.get("/api/v1/staff/directory", headers=_auth(admin["token"]))
    assert response.status_code == 200, response.text
    item = next(row for row in response.json() if row["id"] == staff["profile"]["id"])
    _assert_sensitive_fields_absent(item)


def test_staff_read_tenant_isolation_still_blocks_cross_tenant_access(client: TestClient) -> None:
    owner_a = _register_owner(client, "staff2-tenant-a")
    owner_b = _register_owner(client, "staff2-tenant-b")
    store_b = _create_store(client, owner_b, "staff2-tenant-b")
    staff_b = _create_staff_with_employee_account(
        client,
        owner_b,
        store_id=store_b["id"],
        username="staff2-tenant-b",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    list_response = client.get("/api/v1/staff", headers=_auth(owner_a["token"]))
    assert list_response.status_code == 200, list_response.text
    assert all(item["id"] != staff_b["profile"]["id"] for item in list_response.json())

    detail_response = client.get(
        f"/api/v1/staff/{staff_b['profile']['id']}",
        headers=_auth(owner_a["token"]),
    )
    assert detail_response.status_code == 404
    assert detail_response.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"


def test_employee_profile_projection_remains_unchanged(client: TestClient) -> None:
    owner = _register_owner(client, "staff2-employee-profile")
    store = _create_store(client, owner, "staff2-employee-profile")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2-employee-profile",
        hourly_rate="14.25",
        rtw_status="verified",
    )
    legacy_member_token = _legacy_access_token(staff["user"]["id"])

    response = client.get("/api/v1/employee/me/profile", headers=_auth(legacy_member_token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["staff_id"] == staff["profile"]["id"]
    assert body["hourly_rate"] == 14.25
    assert body["pay_type"] == "hourly"
    assert "rtw_status" not in body
