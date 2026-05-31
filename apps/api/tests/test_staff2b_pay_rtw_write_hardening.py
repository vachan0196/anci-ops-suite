import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.models.staff_profile import StaffProfile
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


def _create_admin(client: TestClient, owner: dict, label: str) -> dict:
    user = _create_tenant_user(client, owner, role="admin", label=f"staff2b-{label}")
    user["token"] = _login_admin(client, user["email"])
    return user


def _staff_profile_from_db(test_session_local, staff_id: str) -> StaffProfile:
    db = test_session_local()
    try:
        profile = db.scalar(select(StaffProfile).where(StaffProfile.id == uuid.UUID(staff_id)))
        assert profile is not None
        db.expunge(profile)
        return profile
    finally:
        db.close()


def _assert_owner_only_error(body: dict) -> None:
    assert body["error"]["code"] == "STAFF_SENSITIVE_FIELDS_OWNER_ONLY"
    assert body["error"]["message"] == "Only owners can set staff pay or right-to-work fields."


def test_owner_can_create_and_update_staff_pay_rtw_fields(client: TestClient) -> None:
    owner = _register_owner(client, "staff2b-owner-write")
    store = _create_store(client, owner, "staff2b-owner-write")
    member = _create_tenant_user(client, owner, role="member", label="staff2b-owner-write")

    create_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": member["id"],
            "store_id": store["id"],
            "display_name": "Staff.2b Owner Write",
            "job_title": "Cashier",
            "hourly_rate": "12.50",
            "pay_type": "hourly",
            "rtw_status": "pending",
            "is_active": True,
        },
        headers=_auth(owner["token"]),
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["hourly_rate"] == "12.50"
    assert create_response.json()["pay_type"] == "hourly"
    assert create_response.json()["rtw_status"] == "pending"

    update_response = client.patch(
        f"/api/v1/staff/{create_response.json()['id']}",
        json={"hourly_rate": "15.25", "pay_type": "salary", "rtw_status": "verified"},
        headers=_auth(owner["token"]),
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["hourly_rate"] == "15.25"
    assert update_response.json()["pay_type"] == "salary"
    assert update_response.json()["rtw_status"] == "verified"
    assert update_response.json()["rtw_checked_by_user_id"] == owner["id"]


def test_admin_can_create_and_update_staff_with_safe_or_null_fields(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "staff2b-admin-safe-owner")
    admin = _create_admin(client, owner, "admin-safe")
    store = _create_store(client, owner, "staff2b-admin-safe")
    member = _create_tenant_user(client, owner, role="member", label="staff2b-admin-safe")

    create_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": member["id"],
            "store_id": store["id"],
            "display_name": "Staff.2b Admin Safe",
            "job_title": "Cashier",
            "hourly_rate": None,
            "pay_type": None,
            "rtw_status": None,
            "phone": "07111111111",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert create_response.status_code == 201, create_response.text

    update_response = client.patch(
        f"/api/v1/staff/{create_response.json()['id']}",
        json={
            "display_name": "Staff.2b Admin Safe Updated",
            "job_title": "Supervisor",
            "hourly_rate": None,
            "pay_type": None,
            "rtw_status": None,
        },
        headers=_auth(admin["token"]),
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["display_name"] == "Staff.2b Admin Safe Updated"
    assert update_response.json()["job_title"] == "Supervisor"

    persisted = _staff_profile_from_db(test_session_local, create_response.json()["id"])
    assert persisted.display_name == "Staff.2b Admin Safe Updated"
    assert persisted.hourly_rate is None
    assert persisted.pay_type is None
    assert persisted.rtw_status is None


def test_admin_create_with_staff_pay_or_rtw_value_is_rejected(client: TestClient) -> None:
    owner = _register_owner(client, "staff2b-admin-create-owner")
    admin = _create_admin(client, owner, "admin-create")
    store = _create_store(client, owner, "staff2b-admin-create")

    sensitive_cases = [
        {"hourly_rate": "12.50"},
        {"pay_type": "hourly"},
        {"rtw_status": "pending"},
    ]
    for index, sensitive_payload in enumerate(sensitive_cases):
        member = _create_tenant_user(
            client,
            owner,
            role="member",
            label=f"staff2b-admin-create-{index}",
        )
        response = client.post(
            "/api/v1/staff",
            json={
                "user_id": member["id"],
                "store_id": store["id"],
                "display_name": f"Staff.2b Admin Rejected {index}",
                "job_title": "Cashier",
                **sensitive_payload,
            },
            headers=_auth(admin["token"]),
        )
        assert response.status_code == 403
        _assert_owner_only_error(response.json())


def test_admin_update_with_staff_pay_or_rtw_value_is_rejected_without_state_change(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "staff2b-admin-update-owner")
    admin = _create_admin(client, owner, "admin-update")
    store = _create_store(client, owner, "staff2b-admin-update")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2b-admin-update",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    sensitive_cases = [
        {"hourly_rate": "99.99"},
        {"pay_type": "salary"},
        {"rtw_status": "expired"},
    ]
    for sensitive_payload in sensitive_cases:
        response = client.patch(
            f"/api/v1/staff/{staff['profile']['id']}",
            json=sensitive_payload,
            headers=_auth(admin["token"]),
        )
        assert response.status_code == 403
        _assert_owner_only_error(response.json())

    persisted = _staff_profile_from_db(test_session_local, staff["profile"]["id"])
    assert str(persisted.hourly_rate) == "14.25"
    assert persisted.pay_type == "hourly"
    assert persisted.rtw_status == "verified"


def test_admin_null_staff_pay_rtw_update_does_not_clear_owner_values(client: TestClient) -> None:
    owner = _register_owner(client, "staff2b-admin-null-owner")
    admin = _create_admin(client, owner, "admin-null")
    store = _create_store(client, owner, "staff2b-admin-null")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2b-admin-null",
        hourly_rate="14.25",
        rtw_status="verified",
    )

    update_response = client.patch(
        f"/api/v1/staff/{staff['profile']['id']}",
        json={
            "hourly_rate": None,
            "pay_type": None,
            "rtw_status": None,
            "job_title": "Senior Cashier",
            "phone": "07111112222",
        },
        headers=_auth(admin["token"]),
    )
    assert update_response.status_code == 200, update_response.text

    reread_response = client.get(
        f"/api/v1/staff/{staff['profile']['id']}",
        headers=_auth(owner["token"]),
    )
    assert reread_response.status_code == 200, reread_response.text
    reread = reread_response.json()
    assert reread["hourly_rate"] == "14.25"
    assert reread["pay_type"] == "hourly"
    assert reread["rtw_status"] == "verified"
    assert reread["job_title"] == "Senior Cashier"
    assert reread["phone"] == "07111112222"


def test_member_staff_pay_rtw_write_remains_rejected_without_state_change(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "staff2b-member-owner")
    store = _create_store(client, owner, "staff2b-member")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staff2b-member",
        hourly_rate="14.25",
        rtw_status="verified",
    )
    member_token = _legacy_access_token(staff["user"]["id"])

    response = client.patch(
        f"/api/v1/staff/{staff['profile']['id']}",
        json={"hourly_rate": "99.99", "pay_type": "salary", "rtw_status": "expired"},
        headers=_auth(member_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    persisted = _staff_profile_from_db(test_session_local, staff["profile"]["id"])
    assert str(persisted.hourly_rate) == "14.25"
    assert persisted.pay_type == "hourly"
    assert persisted.rtw_status == "verified"
