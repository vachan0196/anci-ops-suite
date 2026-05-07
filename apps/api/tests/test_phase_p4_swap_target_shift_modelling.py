from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.shift import Shift
from apps.api.models.shift_request import ShiftRequest
from apps.api.models.staff_profile import StaffProfile
from apps.api.tests.test_phase_p2_target_accept_decline import (
    _auth,
    _configure_opening_hours,
    _create_shift,
    _create_staff_with_employee_account,
    _create_store,
    _employee_login,
    _future_monday,
    _register_and_login,
)


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_p4_swap_target_shift_modelling.db"
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


def _publish(client: TestClient, admin: dict, store_id: str, week: datetime) -> None:
    response = client.post(
        f"/api/v1/sites/{store_id}/rota/publish",
        json={"week_start": week.date().isoformat()},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200


def _setup_swap_site(client: TestClient) -> tuple[dict, dict, dict[str, dict], dict[str, dict], dict[str, datetime]]:
    admin = _register_and_login(client, f"phase-p4-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"P4-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, store["id"])
    staff = {
        username: _create_staff_with_employee_account(
            client,
            admin,
            store_id=store["id"],
            username=username,
        )
        for username in ["alex", "blair", "casey"]
    }
    weeks = {
        "requester": _future_monday(),
        "target": _future_monday(35),
        "draft": _future_monday(49),
        "cancelled": _future_monday(63),
    }
    shifts = {
        "requester": _create_shift(client, admin, store["id"], staff["alex"]["user"]["id"], week=weeks["requester"]),
        "target": _create_shift(client, admin, store["id"], staff["blair"]["user"]["id"], week=weeks["target"]),
        "casey": _create_shift(client, admin, store["id"], staff["casey"]["user"]["id"], week=weeks["target"] + timedelta(days=7)),
        "draft_target": _create_shift(client, admin, store["id"], staff["blair"]["user"]["id"], week=weeks["draft"]),
        "cancelled_target": _create_shift(client, admin, store["id"], staff["blair"]["user"]["id"], week=weeks["cancelled"]),
    }
    _publish(client, admin, store["id"], weeks["requester"])
    _publish(client, admin, store["id"], weeks["target"])
    _publish(client, admin, store["id"], weeks["target"] + timedelta(days=7))
    _publish(client, admin, store["id"], weeks["cancelled"])
    return admin, store, staff, shifts, weeks


def _create_valid_swap(
    client: TestClient,
    *,
    store: dict,
    staff: dict[str, dict],
    shifts: dict[str, dict],
) -> dict:
    token = _employee_login(client, site_id=store["id"], username="alex")
    response = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shifts["requester"]["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
            "target_shift_id": shifts["target"]["id"],
            "reason": "Swap please",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def test_employee_can_list_target_employee_published_scheduled_shifts(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, shifts, weeks = _setup_swap_site(client)
    with test_session_local() as db:
        db.get(Shift, uuid.UUID(shifts["cancelled_target"]["id"])).status = "cancelled"
        db.commit()

    token = _employee_login(client, site_id=store["id"], username="alex")
    response = client.get(
        "/api/v1/employee/me/request-target-shifts",
        params={
            "shift_id": shifts["requester"]["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
        },
        headers=_auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_store"]["id"] == store["id"]
    assert [item["shift_id"] for item in body["items"]] == [shifts["target"]["id"]]
    assert body["items"][0]["role_required"] == "cashier"
    assert "tenant_id" not in body["items"][0]

    admin_response = client.get(
        "/api/v1/employee/me/request-target-shifts",
        params={
            "shift_id": shifts["requester"]["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
        },
        headers=_auth(admin["token"]),
    )
    assert admin_response.status_code in {401, 403}

    assert weeks


@pytest.mark.parametrize(
    "mutation",
    [
        "inactive_target_account",
        "inactive_target_profile",
        "other_site_target",
        "other_tenant_target",
        "draft_requester_shift",
        "cancelled_requester_shift",
        "other_employee_requester_shift",
    ],
)
def test_target_shift_list_validates_requester_shift_and_target_employee(
    client: TestClient,
    test_session_local,
    mutation: str,
) -> None:
    admin, store, staff, shifts, weeks = _setup_swap_site(client)
    target_employee_account_id = staff["blair"]["profile"]["employee_account_id"]
    shift_id = shifts["requester"]["id"]
    if mutation == "other_site_target":
        other_store = _create_store(client, admin, f"P4O-{uuid.uuid4()}")
        _configure_opening_hours(client, admin, other_store["id"])
        other_staff = _create_staff_with_employee_account(client, admin, store_id=other_store["id"], username="devon")
        target_employee_account_id = other_staff["profile"]["employee_account_id"]
    elif mutation == "other_tenant_target":
        other_admin = _register_and_login(client, f"phase-p4-other-{uuid.uuid4()}@example.com")
        other_store = _create_store(client, other_admin, f"P4X-{uuid.uuid4()}")
        other_staff = _create_staff_with_employee_account(client, other_admin, store_id=other_store["id"], username="ellis")
        target_employee_account_id = other_staff["profile"]["employee_account_id"]
    elif mutation == "draft_requester_shift":
        shift_id = shifts["draft_target"]["id"]
    elif mutation == "other_employee_requester_shift":
        shift_id = shifts["casey"]["id"]

    with test_session_local() as db:
        if mutation == "inactive_target_account":
            db.get(EmployeeAccount, uuid.UUID(target_employee_account_id)).is_active = False
        elif mutation == "inactive_target_profile":
            db.get(StaffProfile, uuid.UUID(staff["blair"]["profile"]["id"])).is_active = False
        elif mutation == "cancelled_requester_shift":
            db.get(Shift, uuid.UUID(shift_id)).status = "cancelled"
        db.commit()

    token = _employee_login(client, site_id=store["id"], username="alex")
    response = client.get(
        "/api/v1/employee/me/request-target-shifts",
        params={
            "shift_id": shift_id,
            "target_employee_account_id": target_employee_account_id,
        },
        headers=_auth(token),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] in {"SHIFT_NOT_FOUND", "TARGET_NOT_FOUND"}
    assert weeks


def test_swap_creation_requires_and_stores_target_shift_without_rota_mutation(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    token = _employee_login(client, site_id=store["id"], username="alex")

    missing = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shifts["requester"]["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
            "reason": "Swap please",
        },
        headers=_auth(token),
    )
    assert missing.status_code == 422

    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    duplicate = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shifts["requester"]["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
            "target_shift_id": shifts["target"]["id"],
            "reason": "Duplicate",
        },
        headers=_auth(token),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "REQUEST_DUPLICATE"

    with test_session_local() as db:
        row = db.get(ShiftRequest, uuid.UUID(created["id"]))
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        assert row.target_shift_id == uuid.UUID(shifts["target"]["id"])
        assert row.status == "pending"
        assert requester_shift.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert target_shift.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])


@pytest.mark.parametrize(
    "target_shift_name",
    ["casey", "requester", "draft_target", "cancelled_target"],
)
def test_swap_creation_rejects_invalid_target_shift(
    client: TestClient,
    test_session_local,
    target_shift_name: str,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    with test_session_local() as db:
        db.get(Shift, uuid.UUID(shifts["cancelled_target"]["id"])).status = "cancelled"
        db.commit()

    token = _employee_login(client, site_id=store["id"], username="alex")
    response = client.post(
        "/api/v1/employee/me/requests",
        json={
            "request_type": "swap",
            "shift_id": shifts["requester"]["id"],
            "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
            "target_shift_id": shifts[target_shift_name]["id"],
            "reason": "Swap please",
        },
        headers=_auth(token),
    )

    assert response.status_code in {404, 422}
    assert response.json()["error"]["code"] in {"SHIFT_NOT_FOUND", "VALIDATION_ERROR"}


def test_swap_creation_rejects_cross_site_and_cross_tenant_target_shift(
    client: TestClient,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    other_store = _create_store(client, admin, f"P4OS-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, other_store["id"])
    other_site_staff = _create_staff_with_employee_account(client, admin, store_id=other_store["id"], username="devon")
    other_site_week = _future_monday(77)
    other_site_shift = _create_shift(client, admin, other_store["id"], other_site_staff["user"]["id"], week=other_site_week)
    _publish(client, admin, other_store["id"], other_site_week)

    other_admin = _register_and_login(client, f"phase-p4-tenant-{uuid.uuid4()}@example.com")
    other_tenant_store = _create_store(client, other_admin, f"P4T-{uuid.uuid4()}")
    _configure_opening_hours(client, other_admin, other_tenant_store["id"])
    other_tenant_staff = _create_staff_with_employee_account(
        client,
        other_admin,
        store_id=other_tenant_store["id"],
        username="ellis",
    )
    other_tenant_shift = _create_shift(
        client,
        other_admin,
        other_tenant_store["id"],
        other_tenant_staff["user"]["id"],
        week=_future_monday(91),
    )
    _publish(client, other_admin, other_tenant_store["id"], _future_monday(91))

    token = _employee_login(client, site_id=store["id"], username="alex")
    for target_shift_id in [other_site_shift["id"], other_tenant_shift["id"]]:
        response = client.post(
            "/api/v1/employee/me/requests",
            json={
                "request_type": "swap",
                "shift_id": shifts["requester"]["id"],
                "target_employee_account_id": staff["blair"]["profile"]["employee_account_id"],
                "target_shift_id": target_shift_id,
                "reason": "Swap please",
            },
            headers=_auth(token),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SHIFT_NOT_FOUND"


def test_inbound_and_admin_detail_include_safe_target_shift_summary(
    client: TestClient,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)

    blair_token = _employee_login(client, site_id=store["id"], username="blair")
    inbound = client.get("/api/v1/employee/me/inbound-requests", headers=_auth(blair_token))
    assert inbound.status_code == 200
    item = inbound.json()["items"][0]
    assert item["shift"]["id"] == shifts["requester"]["id"]
    assert item["target_shift"]["id"] == shifts["target"]["id"]
    assert "tenant_id" not in item["target_shift"]

    detail = client.get(
        f"/api/v1/sites/{store['id']}/requests/{created['id']}",
        headers=_auth(admin["token"]),
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["target_shift_id"] == shifts["target"]["id"]
    assert body["shift"]["assigned_employee_display_name"] == "Phase P2 alex"
    assert body["target_shift"]["assigned_employee_display_name"] == "Phase P2 blair"


def test_target_acceptance_is_workflow_only_and_employee_token_cannot_access_admin_api(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    blair_token = _employee_login(client, site_id=store["id"], username="blair")
    accepted = client.post(
        f"/api/v1/employee/me/inbound-requests/{created['id']}/accept",
        headers=_auth(blair_token),
    )
    assert accepted.status_code == 200
    employee_admin = client.get(
        f"/api/v1/sites/{store['id']}/requests",
        headers=_auth(blair_token),
    )
    assert employee_admin.status_code in {401, 403}
    with test_session_local() as db:
        request = db.get(ShiftRequest, uuid.UUID(created["id"]))
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        assert request.status == "target_accepted"
        assert requester_shift.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert target_shift.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])
