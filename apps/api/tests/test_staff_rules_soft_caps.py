import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.models.staff_profile import StaffProfile
from apps.api.tests.test_phase_t0_tenant_role_security_gate import (
    _auth,
    _create_store,
    _create_tenant_user,
    _login_admin,
    _register_owner,
    client,
    test_session_local,
)


SOFT_CAP_FIELDS = {
    "weekly_working_hour_soft_cap",
    "monthly_working_hour_soft_cap",
}
OWNER_ONLY_FIELDS = {"hourly_rate", "pay_type", "rtw_status"}


def _create_admin(client: TestClient, owner: dict, label: str) -> dict:
    user = _create_tenant_user(client, owner, role="admin", label=f"staff-rules-{label}")
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


def _create_staff(
    client: TestClient,
    actor: dict,
    *,
    user_id: str,
    store_id: str,
    label: str,
    weekly: str | None = "37.50",
    monthly: str | None = "162.50",
    extra: dict | None = None,
) -> dict:
    payload = {
        "user_id": user_id,
        "store_id": store_id,
        "display_name": f"StaffRules {label}",
        "job_title": "Cashier",
        "weekly_working_hour_soft_cap": weekly,
        "monthly_working_hour_soft_cap": monthly,
        "is_active": True,
    }
    if extra:
        payload.update(extra)
    response = client.post("/api/v1/staff", json=payload, headers=_auth(actor["token"]))
    assert response.status_code == 201, response.text
    return response.json()


def _assert_soft_caps(body: dict, *, weekly: str | None, monthly: str | None) -> None:
    assert body["weekly_working_hour_soft_cap"] == weekly
    assert body["monthly_working_hour_soft_cap"] == monthly


def test_owner_and_admin_staff_reads_include_soft_caps_with_existing_sensitive_boundary(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "staff-rules-read-owner")
    admin = _create_admin(client, owner, "read-admin")
    store = _create_store(client, owner, "staff-rules-read")
    member = _create_tenant_user(client, owner, role="member", label="staff-rules-read-member")
    staff = _create_staff(
        client,
        owner,
        user_id=member["id"],
        store_id=store["id"],
        label="Read",
        weekly="37.50",
        monthly="162.50",
        extra={"hourly_rate": "14.25", "pay_type": "hourly", "rtw_status": "verified"},
    )

    owner_list = client.get("/api/v1/staff", headers=_auth(owner["token"]))
    assert owner_list.status_code == 200, owner_list.text
    owner_listed = next(item for item in owner_list.json() if item["id"] == staff["id"])
    _assert_soft_caps(owner_listed, weekly="37.50", monthly="162.50")
    assert owner_listed["hourly_rate"] == "14.25"
    assert owner_listed["pay_type"] == "hourly"
    assert owner_listed["rtw_status"] == "verified"

    admin_list = client.get("/api/v1/staff", headers=_auth(admin["token"]))
    assert admin_list.status_code == 200, admin_list.text
    admin_listed = next(item for item in admin_list.json() if item["id"] == staff["id"])
    _assert_soft_caps(admin_listed, weekly="37.50", monthly="162.50")
    assert OWNER_ONLY_FIELDS.isdisjoint(admin_listed.keys())

    owner_detail = client.get(f"/api/v1/staff/{staff['id']}", headers=_auth(owner["token"]))
    assert owner_detail.status_code == 200, owner_detail.text
    _assert_soft_caps(owner_detail.json(), weekly="37.50", monthly="162.50")
    assert owner_detail.json()["hourly_rate"] == "14.25"

    admin_detail = client.get(f"/api/v1/staff/{staff['id']}", headers=_auth(admin["token"]))
    assert admin_detail.status_code == 200, admin_detail.text
    _assert_soft_caps(admin_detail.json(), weekly="37.50", monthly="162.50")
    assert OWNER_ONLY_FIELDS.isdisjoint(admin_detail.json().keys())


def test_staff_directory_remains_trimmed_without_soft_caps(client: TestClient) -> None:
    owner = _register_owner(client, "staff-rules-directory-owner")
    admin = _create_admin(client, owner, "directory-admin")
    store = _create_store(client, owner, "staff-rules-directory")
    member = _create_tenant_user(client, owner, role="member", label="staff-rules-directory-member")
    staff = _create_staff(
        client,
        owner,
        user_id=member["id"],
        store_id=store["id"],
        label="Directory",
    )

    response = client.get("/api/v1/staff/directory", headers=_auth(admin["token"]))
    assert response.status_code == 200, response.text
    item = next(row for row in response.json() if row["id"] == staff["id"])
    assert SOFT_CAP_FIELDS.isdisjoint(item.keys())
    assert OWNER_ONLY_FIELDS.isdisjoint(item.keys())


def test_owner_and_admin_can_write_soft_caps_while_admin_pay_rtw_block_remains(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "staff-rules-write-owner")
    admin = _create_admin(client, owner, "write-admin")
    store = _create_store(client, owner, "staff-rules-write")
    owner_member = _create_tenant_user(client, owner, role="member", label="staff-rules-owner-member")
    admin_member = _create_tenant_user(client, owner, role="member", label="staff-rules-admin-member")

    owner_created = _create_staff(
        client,
        owner,
        user_id=owner_member["id"],
        store_id=store["id"],
        label="Owner Write",
        weekly="37.50",
        monthly="162.50",
    )
    _assert_soft_caps(owner_created, weekly="37.50", monthly="162.50")

    owner_update = client.patch(
        f"/api/v1/staff/{owner_created['id']}",
        json={
            "weekly_working_hour_soft_cap": "40.25",
            "monthly_working_hour_soft_cap": "170.75",
        },
        headers=_auth(owner["token"]),
    )
    assert owner_update.status_code == 200, owner_update.text
    _assert_soft_caps(owner_update.json(), weekly="40.25", monthly="170.75")

    admin_created = _create_staff(
        client,
        admin,
        user_id=admin_member["id"],
        store_id=store["id"],
        label="Admin Write",
        weekly="30.50",
        monthly="130.25",
        extra={"hourly_rate": None, "pay_type": None, "rtw_status": None},
    )
    _assert_soft_caps(admin_created, weekly="30.50", monthly="130.25")
    assert OWNER_ONLY_FIELDS.isdisjoint(admin_created.keys())

    admin_update = client.patch(
        f"/api/v1/staff/{admin_created['id']}",
        json={
            "weekly_working_hour_soft_cap": "32.75",
            "monthly_working_hour_soft_cap": "141.50",
        },
        headers=_auth(admin["token"]),
    )
    assert admin_update.status_code == 200, admin_update.text
    _assert_soft_caps(admin_update.json(), weekly="32.75", monthly="141.50")
    assert OWNER_ONLY_FIELDS.isdisjoint(admin_update.json().keys())

    admin_sensitive = client.patch(
        f"/api/v1/staff/{owner_created['id']}",
        json={"hourly_rate": "99.99", "pay_type": "salary", "rtw_status": "expired"},
        headers=_auth(admin["token"]),
    )
    assert admin_sensitive.status_code == 403
    assert admin_sensitive.json()["error"]["code"] == "STAFF_SENSITIVE_FIELDS_OWNER_ONLY"

    persisted = _staff_profile_from_db(test_session_local, admin_created["id"])
    assert persisted.weekly_working_hour_soft_cap == Decimal("32.75")
    assert persisted.monthly_working_hour_soft_cap == Decimal("141.50")


def test_soft_cap_validation_accepts_null_and_fractional_values_and_rejects_negative(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "staff-rules-validation-owner")
    store = _create_store(client, owner, "staff-rules-validation")
    member = _create_tenant_user(client, owner, role="member", label="staff-rules-validation-member")

    negative_weekly = client.post(
        "/api/v1/staff",
        json={
            "user_id": member["id"],
            "store_id": store["id"],
            "display_name": "StaffRules Negative Weekly",
            "weekly_working_hour_soft_cap": "-1",
        },
        headers=_auth(owner["token"]),
    )
    assert negative_weekly.status_code == 422
    assert negative_weekly.json()["error"]["code"] == "VALIDATION_ERROR"

    created = _create_staff(
        client,
        owner,
        user_id=member["id"],
        store_id=store["id"],
        label="Validation",
        weekly="37.5",
        monthly=None,
    )
    _assert_soft_caps(created, weekly="37.50", monthly=None)

    negative_monthly = client.patch(
        f"/api/v1/staff/{created['id']}",
        json={"monthly_working_hour_soft_cap": "-0.01"},
        headers=_auth(owner["token"]),
    )
    assert negative_monthly.status_code == 422
    assert negative_monthly.json()["error"]["code"] == "VALIDATION_ERROR"

    null_update = client.patch(
        f"/api/v1/staff/{created['id']}",
        json={
            "weekly_working_hour_soft_cap": None,
            "monthly_working_hour_soft_cap": None,
        },
        headers=_auth(owner["token"]),
    )
    assert null_update.status_code == 200, null_update.text
    _assert_soft_caps(null_update.json(), weekly=None, monthly=None)


def test_soft_cap_cross_tenant_and_site_safety_remains_enforced(
    client: TestClient,
    test_session_local,
) -> None:
    owner_a = _register_owner(client, "staff-rules-cross-owner-a")
    owner_b = _register_owner(client, "staff-rules-cross-owner-b")
    store_a = _create_store(client, owner_a, "staff-rules-cross-a")
    store_b = _create_store(client, owner_b, "staff-rules-cross-b")
    member_b = _create_tenant_user(client, owner_b, role="member", label="staff-rules-cross-member-b")
    staff_b = _create_staff(
        client,
        owner_b,
        user_id=member_b["id"],
        store_id=store_b["id"],
        label="Cross Tenant",
        weekly="37.50",
        monthly="162.50",
    )

    cross_store_create = client.post(
        "/api/v1/staff",
        json={
            "user_id": member_b["id"],
            "store_id": store_a["id"],
            "display_name": "StaffRules Cross Store",
            "weekly_working_hour_soft_cap": "20.00",
        },
        headers=_auth(owner_b["token"]),
    )
    assert cross_store_create.status_code in {400, 404}

    cross_update = client.patch(
        f"/api/v1/staff/{staff_b['id']}",
        json={"weekly_working_hour_soft_cap": "99.00"},
        headers=_auth(owner_a["token"]),
    )
    assert cross_update.status_code == 404
    assert cross_update.json()["error"]["code"] == "STAFF_PROFILE_NOT_FOUND"

    persisted = _staff_profile_from_db(test_session_local, staff_b["id"])
    assert persisted.weekly_working_hour_soft_cap == Decimal("37.50")
