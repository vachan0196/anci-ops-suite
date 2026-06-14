from collections.abc import Generator
from datetime import date, datetime, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.shift import Shift
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User


PASSWORD = "password123"
WEEK_START = "2026-04-06"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _register_and_login(client: TestClient, email: str) -> dict:
    register_body = _register(client, email)
    token = _login(client, email)
    return {
        "id": uuid.UUID(register_body["id"]),
        "active_tenant_id": uuid.UUID(register_body["active_tenant_id"]),
        "token": token,
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _set_membership(
    test_session_local,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    set_active_tenant: bool = True,
) -> None:
    db = test_session_local()
    try:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.user_id == user_id,
                TenantUser.tenant_id == tenant_id,
            )
        )
        if membership is None:
            db.add(TenantUser(user_id=user_id, tenant_id=tenant_id, role=role))
        else:
            membership.role = role

        user = db.get(User, user_id)
        assert user is not None
        if set_active_tenant:
            user.active_tenant_id = tenant_id
        db.commit()
    finally:
        db.close()


def _create_store(client: TestClient, token: str, code: str) -> str:
    response = client.post(
        "/api/v1/stores",
        json={"code": code, "name": f"Store {code}", "timezone": "UTC"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_staff_profile(
    client: TestClient,
    token: str,
    *,
    user_id: uuid.UUID,
    store_id: str,
    weekly_cap: str | None = None,
) -> str:
    payload = {
        "user_id": str(user_id),
        "store_id": store_id,
        "display_name": f"User {user_id}",
        "is_active": True,
    }
    if weekly_cap is not None:
        payload["weekly_working_hour_soft_cap"] = weekly_cap

    response = client.post(
        "/api/v1/staff",
        json=payload,
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_staff_role(client: TestClient, token: str, staff_id: str, role: str) -> None:
    response = client.post(
        f"/api/v1/staff/{staff_id}/roles",
        json={"role": role},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text


def _create_shift(
    client: TestClient,
    token: str,
    *,
    store_id: str,
    start_at: str,
    end_at: str,
    assigned_user_id: uuid.UUID | None = None,
    required_role: str | None = None,
) -> str:
    response = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "assigned_user_id": str(assigned_user_id) if assigned_user_id else None,
            "start_at": start_at,
            "end_at": end_at,
            "required_role": required_role,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _replace_staff_availability_week(
    client: TestClient,
    token: str,
    *,
    staff_user_id: uuid.UUID,
    entries: list[dict],
) -> dict:
    response = client.put(
        f"/api/v1/staff/{staff_user_id}/availability/week",
        json={"week_start": WEEK_START, "entries": entries},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _availability_entry(date_value: str, availability_type: str = "available") -> dict:
    return {
        "date": date_value,
        "start_time": None,
        "end_time": None,
        "type": availability_type,
    }


def _upsert_hour_target(
    client: TestClient,
    token: str,
    *,
    user_id: uuid.UUID,
    week_start: str,
    max_hours: int,
    store_id: str | None = None,
) -> None:
    response = client.put(
        "/api/v1/hour-targets",
        json={
            "user_id": str(user_id),
            "store_id": store_id,
            "week_start": week_start,
            "min_hours": 0,
            "max_hours": max_hours,
            "target_hours": 0,
        },
        headers=_auth(token),
    )
    assert response.status_code in [200, 201], response.text


def _create_recommendation_detail(
    client: TestClient,
    token: str,
    *,
    store_id: str,
    week_start: str = WEEK_START,
) -> dict:
    create_response = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": week_start},
        headers=_auth(token),
    )
    assert create_response.status_code == 201, create_response.text

    detail_response = client.get(
        f"/api/v1/rota-recommendations/{create_response.json()['draft_id']}",
        headers=_auth(token),
    )
    assert detail_response.status_code == 200, detail_response.text
    return detail_response.json()


def _proposed_user_ids(detail: dict) -> list[str | None]:
    return [item["proposed_user_id"] for item in detail["items"]]


def _single_proposed_user_id(detail: dict) -> str | None:
    assert detail["items_created"] == 1
    assert len(detail["items"]) == 1
    return detail["items"][0]["proposed_user_id"]


def _setup_admin_member_store(
    client: TestClient,
    test_session_local,
    *,
    code: str,
    weekly_cap: str | None = None,
) -> tuple[dict, dict, str, str]:
    admin = _register_and_login(client, f"{code}-admin-{uuid.uuid4()}@example.com")
    member = _register_and_login(client, f"{code}-member-{uuid.uuid4()}@example.com")
    _set_membership(
        test_session_local,
        user_id=member["id"],
        tenant_id=admin["active_tenant_id"],
        role="member",
    )
    store_id = _create_store(client, admin["token"], code)
    staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=member["id"],
        store_id=store_id,
        weekly_cap=weekly_cap,
    )
    return admin, member, store_id, staff_id


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_rota_recommendations_e2e_availability.db"
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


def test_no_availability_row_skips_candidate(client: TestClient, test_session_local) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-NONE",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) is None
    assert detail["items"][0]["reason"] == "no_eligible_candidate"
    assert str(member["id"]) not in _proposed_user_ids(detail)


def test_admin_set_available_row_makes_same_user_eligible(
    client: TestClient,
    test_session_local,
) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-ADMIN",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-07T09:00:00Z",
        end_at="2026-04-07T17:00:00Z",
    )

    availability = _replace_staff_availability_week(
        client,
        admin["token"],
        staff_user_id=member["id"],
        entries=[_availability_entry("2026-04-07")],
    )
    assert availability["items"][0]["user_id"] == str(member["id"])
    assert availability["items"][0]["source"] == "admin"

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(member["id"])


def test_admin_set_available_extra_row_is_eligible(
    client: TestClient,
    test_session_local,
) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-EXTRA",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-08T09:00:00Z",
        end_at="2026-04-08T17:00:00Z",
    )
    _replace_staff_availability_week(
        client,
        admin["token"],
        staff_user_id=member["id"],
        entries=[_availability_entry("2026-04-08", "available_extra")],
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(member["id"])


def test_required_role_filters_to_matching_available_staff(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"RR-E2E-ROLE-admin-{uuid.uuid4()}@example.com")
    matching = _register_and_login(client, f"RR-E2E-ROLE-match-{uuid.uuid4()}@example.com")
    non_matching = _register_and_login(client, f"RR-E2E-ROLE-other-{uuid.uuid4()}@example.com")
    for user in [matching, non_matching]:
        _set_membership(
            test_session_local,
            user_id=user["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )
    store_id = _create_store(client, admin["token"], "RR-E2E-ROLE")
    matching_staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=matching["id"],
        store_id=store_id,
    )
    _create_staff_profile(
        client,
        admin["token"],
        user_id=non_matching["id"],
        store_id=store_id,
    )
    _add_staff_role(client, admin["token"], matching_staff_id, "cashier")
    for user in [matching, non_matching]:
        _replace_staff_availability_week(
            client,
            admin["token"],
            staff_user_id=user["id"],
            entries=[_availability_entry("2026-04-09")],
        )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-09T09:00:00Z",
        end_at="2026-04-09T17:00:00Z",
        required_role="cashier",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(matching["id"])
    assert str(non_matching["id"]) not in _proposed_user_ids(detail)


def test_staff_profile_soft_cap_fallback_flags_but_does_not_exclude_in_real_generation(
    client: TestClient,
    test_session_local,
) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-SOFTCAP",
        weekly_cap="4.00",
    )
    _replace_staff_availability_week(
        client,
        admin["token"],
        staff_user_id=member["id"],
        entries=[_availability_entry("2026-04-10")],
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        assigned_user_id=member["id"],
        start_at="2026-04-06T08:00:00Z",
        end_at="2026-04-06T12:00:00Z",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-10T09:00:00Z",
        end_at="2026-04-10T13:00:00Z",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(member["id"])
    assert detail["unfilled"] == 0
    assert "over_weekly_soft_cap" in detail["items"][0]["reason"].split(",")


def test_under_soft_cap_staff_ranks_ahead_of_over_soft_cap_staff(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"RR-E2E-SOFTRANK-admin-{uuid.uuid4()}@example.com")
    under_cap = _register_and_login(client, f"RR-E2E-SOFTRANK-under-{uuid.uuid4()}@example.com")
    over_cap = _register_and_login(client, f"RR-E2E-SOFTRANK-over-{uuid.uuid4()}@example.com")
    for user in [under_cap, over_cap]:
        _set_membership(
            test_session_local,
            user_id=user["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )
    store_id = _create_store(client, admin["token"], "RR-E2E-SOFTRANK")
    under_staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=under_cap["id"],
        store_id=store_id,
        weekly_cap="40.00",
    )
    over_staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=over_cap["id"],
        store_id=store_id,
        weekly_cap="4.00",
    )
    for staff_id in [under_staff_id, over_staff_id]:
        _add_staff_role(client, admin["token"], staff_id, "cashier")
    for user in [under_cap, over_cap]:
        _replace_staff_availability_week(
            client,
            admin["token"],
            staff_user_id=user["id"],
            entries=[_availability_entry("2026-04-10")],
        )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        assigned_user_id=over_cap["id"],
        start_at="2026-04-06T08:00:00Z",
        end_at="2026-04-06T12:00:00Z",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-10T09:00:00Z",
        end_at="2026-04-10T13:00:00Z",
        required_role="cashier",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(under_cap["id"])
    assert "over_weekly_soft_cap" not in detail["items"][0]["reason"].split(",")


def test_hour_target_max_hours_overrides_staff_profile_soft_cap_in_real_generation(
    client: TestClient,
    test_session_local,
) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-HOURTARGET",
        weekly_cap="4.00",
    )
    _replace_staff_availability_week(
        client,
        admin["token"],
        staff_user_id=member["id"],
        entries=[_availability_entry("2026-04-10")],
    )
    _upsert_hour_target(
        client,
        admin["token"],
        user_id=member["id"],
        week_start=WEEK_START,
        max_hours=8,
        store_id=store_id,
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        assigned_user_id=member["id"],
        start_at="2026-04-06T08:00:00Z",
        end_at="2026-04-06T12:00:00Z",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-10T09:00:00Z",
        end_at="2026-04-10T13:00:00Z",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(member["id"])
    assert "over_weekly_soft_cap" not in detail["items"][0]["reason"].split(",")


def test_hour_target_over_cap_preserves_hard_exclusion(
    client: TestClient,
    test_session_local,
) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-HARDCAP",
        weekly_cap="40.00",
    )
    _replace_staff_availability_week(
        client,
        admin["token"],
        staff_user_id=member["id"],
        entries=[_availability_entry("2026-04-10")],
    )
    _upsert_hour_target(
        client,
        admin["token"],
        user_id=member["id"],
        week_start=WEEK_START,
        max_hours=4,
        store_id=store_id,
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        assigned_user_id=member["id"],
        start_at="2026-04-06T08:00:00Z",
        end_at="2026-04-06T12:00:00Z",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-10T09:00:00Z",
        end_at="2026-04-10T13:00:00Z",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) is None
    assert detail["unfilled"] == 1


def test_cross_tenant_staff_and_availability_never_appear(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a, member_a, store_a_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-ISO-A",
    )
    admin_b, member_b, store_b_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-ISO-B",
    )
    _replace_staff_availability_week(
        client,
        admin_a["token"],
        staff_user_id=member_a["id"],
        entries=[_availability_entry("2026-04-06")],
    )
    _replace_staff_availability_week(
        client,
        admin_b["token"],
        staff_user_id=member_b["id"],
        entries=[_availability_entry("2026-04-06")],
    )
    _create_shift(
        client,
        admin_a["token"],
        store_id=store_a_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )
    _create_shift(
        client,
        admin_b["token"],
        store_id=store_b_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )

    detail = _create_recommendation_detail(client, admin_a["token"], store_id=store_a_id)

    assert str(member_a["id"]) in _proposed_user_ids(detail)
    assert str(member_b["id"]) not in _proposed_user_ids(detail)


def test_useful_output_probe_with_availability_roles_and_caps(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"RR-E2E-USEFUL-admin-{uuid.uuid4()}@example.com")
    eligible = _register_and_login(client, f"RR-E2E-USEFUL-eligible-{uuid.uuid4()}@example.com")
    over_cap = _register_and_login(client, f"RR-E2E-USEFUL-overcap-{uuid.uuid4()}@example.com")
    unavailable = _register_and_login(client, f"RR-E2E-USEFUL-unavailable-{uuid.uuid4()}@example.com")
    for user in [eligible, over_cap, unavailable]:
        _set_membership(
            test_session_local,
            user_id=user["id"],
            tenant_id=admin["active_tenant_id"],
            role="member",
        )

    store_id = _create_store(client, admin["token"], "RR-E2E-USEFUL")
    eligible_staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=eligible["id"],
        store_id=store_id,
        weekly_cap="40.00",
    )
    over_cap_staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=over_cap["id"],
        store_id=store_id,
        weekly_cap="4.00",
    )
    unavailable_staff_id = _create_staff_profile(
        client,
        admin["token"],
        user_id=unavailable["id"],
        store_id=store_id,
        weekly_cap="40.00",
    )
    for staff_id in [eligible_staff_id, over_cap_staff_id, unavailable_staff_id]:
        _add_staff_role(client, admin["token"], staff_id, "cashier")
    for user in [eligible, over_cap]:
        _replace_staff_availability_week(
            client,
            admin["token"],
            staff_user_id=user["id"],
            entries=[_availability_entry("2026-04-11")],
        )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        assigned_user_id=over_cap["id"],
        start_at="2026-04-06T08:00:00Z",
        end_at="2026-04-06T12:00:00Z",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-11T09:00:00Z",
        end_at="2026-04-11T13:00:00Z",
        required_role="cashier",
    )

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert detail["items_created"] == 1
    assert detail["unfilled"] == 0
    assert _single_proposed_user_id(detail) == str(eligible["id"])
    assert str(over_cap["id"]) not in _proposed_user_ids(detail)
    assert str(unavailable["id"]) not in _proposed_user_ids(detail)


def test_admin_replace_week_persists_user_id_key_consumed_by_recommendations(
    client: TestClient,
    test_session_local,
) -> None:
    admin, member, store_id, _ = _setup_admin_member_store(
        client,
        test_session_local,
        code="RR-E2E-KEY",
    )
    _create_shift(
        client,
        admin["token"],
        store_id=store_id,
        start_at="2026-04-06T09:00:00Z",
        end_at="2026-04-06T17:00:00Z",
    )
    _replace_staff_availability_week(
        client,
        admin["token"],
        staff_user_id=member["id"],
        entries=[_availability_entry("2026-04-06")],
    )

    db = test_session_local()
    try:
        rows = db.scalars(
            select(AvailabilityEntry).where(
                AvailabilityEntry.tenant_id == admin["active_tenant_id"],
                AvailabilityEntry.user_id == member["id"],
                AvailabilityEntry.week_start == date(2026, 4, 6),
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].source == "admin"
    finally:
        db.close()

    detail = _create_recommendation_detail(client, admin["token"], store_id=store_id)

    assert _single_proposed_user_id(detail) == str(member["id"])
