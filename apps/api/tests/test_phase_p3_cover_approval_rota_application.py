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
    _create_targeted_request,
    _employee_login,
    _future_monday,
    _register_and_login,
)


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_p3_cover_approval_rota_application.db"
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


def _setup_cover_site(client: TestClient) -> tuple[dict, dict, dict[str, dict], datetime, dict]:
    admin = _register_and_login(client, f"phase-p3-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"P3-{uuid.uuid4()}")
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
    week = _future_monday()
    shift = _create_shift(
        client,
        admin,
        store["id"],
        staff["alex"]["user"]["id"],
        week=week,
    )
    response = client.post(
        f"/api/v1/sites/{store['id']}/rota/publish",
        json={"week_start": week.date().isoformat()},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 200
    return admin, store, staff, week, shift


def _accept_inbound(client: TestClient, store: dict, username: str, request_id: str) -> None:
    token = _employee_login(client, site_id=store["id"], username=username)
    response = client.post(
        f"/api/v1/employee/me/inbound-requests/{request_id}/accept",
        headers=_auth(token),
    )
    assert response.status_code == 200


def _approve_request(client: TestClient, admin: dict, store: dict, request_id: str):
    return client.post(
        f"/api/v1/sites/{store['id']}/requests/{request_id}/approve",
        json={"approval_reason": "Approved"},
        headers=_auth(admin["token"]),
    )


def test_approving_target_accepted_cover_reassigns_published_scheduled_shift(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, week, shift = _setup_cover_site(client)
    request = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    _accept_inbound(client, store, "blair", request["id"])

    with test_session_local() as db:
        before = db.get(Shift, uuid.UUID(shift["id"]))
        original_start = before.start_at
        original_end = before.end_at
        original_published_at = before.published_at

    response = _approve_request(client, admin, store, request["id"])

    assert response.status_code == 200
    assert response.json() == {
        "id": request["id"],
        "status": "approved",
        "rota_updated": True,
        "affected_shift_count": 1,
        "message": "Cover request approved and the shift was assigned to the target employee.",
    }
    with test_session_local() as db:
        changed = db.get(Shift, uuid.UUID(shift["id"]))
        request_row = db.get(ShiftRequest, uuid.UUID(request["id"]))
        assert request_row.status == "approved"
        assert request_row.approver_user_id == uuid.UUID(admin["id"])
        assert request_row.decided_at is not None
        assert changed.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])
        assert changed.status == "scheduled"
        assert changed.published_at == original_published_at
        assert changed.start_at == original_start
        assert changed.end_at == original_end
        actions = {
            action
            for (action,) in db.execute(
                select(AuditLog.action).where(
                    AuditLog.entity_id.in_([request["id"], shift["id"]])
                )
            ).all()
        }
        assert "request_approved" in actions
        assert "approved_cover_reassigned_shift" in actions

    requester_token = _employee_login(client, site_id=store["id"], username="alex")
    target_token = _employee_login(client, site_id=store["id"], username="blair")
    requester_rota = client.get(
        f"/api/v1/employee/rota/my?week_start={week.date().isoformat()}",
        headers=_auth(requester_token),
    )
    target_rota = client.get(
        f"/api/v1/employee/rota/my?week_start={week.date().isoformat()}",
        headers=_auth(target_token),
    )
    assert requester_rota.status_code == 200
    assert target_rota.status_code == 200
    assert requester_rota.json()["shifts"] == []
    assert [item["id"] for item in target_rota.json()["shifts"]] == [shift["id"]]


def test_targeted_cover_must_be_accepted_before_approval_and_does_not_mutate(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, _week, shift = _setup_cover_site(client)
    request = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )

    response = _approve_request(client, admin, store, request["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_TARGET_NOT_ACCEPTED"
    with test_session_local() as db:
        changed = db.get(Shift, uuid.UUID(shift["id"]))
        request_row = db.get(ShiftRequest, uuid.UUID(request["id"]))
        assert request_row.status == "pending"
        assert changed.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])


@pytest.mark.parametrize("status", ["target_declined", "cancelled", "rejected", "approved"])
def test_non_actionable_cover_statuses_do_not_mutate_rota(
    client: TestClient,
    test_session_local,
    status: str,
) -> None:
    admin, store, staff, _week, shift = _setup_cover_site(client)
    request = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    with test_session_local() as db:
        row = db.get(ShiftRequest, uuid.UUID(request["id"]))
        row.status = status
        db.commit()

    response = _approve_request(client, admin, store, request["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_NOT_PENDING"
    with test_session_local() as db:
        changed = db.get(Shift, uuid.UUID(shift["id"]))
        assert changed.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        ("target_other_site", "Target employee is not active in selected site"),
        ("target_other_tenant", "Target employee is not active in selected site"),
        ("target_inactive", "Target employee is not active in selected site"),
        ("shift_unowned", "Cover request shift is no longer assigned to requester"),
        ("shift_draft", "Cover request shift is not an active published shift"),
        ("shift_cancelled", "Cover request shift is not an active published shift"),
    ],
)
def test_invalid_cover_application_data_does_not_mutate_rota(
    client: TestClient,
    test_session_local,
    mutation: str,
    expected_message: str,
) -> None:
    admin, store, staff, _week, shift = _setup_cover_site(client)
    request = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    _accept_inbound(client, store, "blair", request["id"])
    other_store = _create_store(client, admin, f"P3O-{uuid.uuid4()}")
    _configure_opening_hours(client, admin, other_store["id"])
    other_site_staff = _create_staff_with_employee_account(
        client,
        admin,
        store_id=other_store["id"],
        username=f"other-{uuid.uuid4()}",
    )
    other_tenant_admin = _register_and_login(
        client,
        f"phase-p3-other-admin-{uuid.uuid4()}@example.com",
    )
    other_tenant_store = _create_store(client, other_tenant_admin, f"P3X-{uuid.uuid4()}")
    _configure_opening_hours(client, other_tenant_admin, other_tenant_store["id"])
    other_tenant_staff = _create_staff_with_employee_account(
        client,
        other_tenant_admin,
        store_id=other_tenant_store["id"],
        username=f"external-{uuid.uuid4()}",
    )

    with test_session_local() as db:
        request_row = db.get(ShiftRequest, uuid.UUID(request["id"]))
        shift_row = db.get(Shift, uuid.UUID(shift["id"]))
        if mutation == "target_other_site":
            request_row.target_employee_account_id = uuid.UUID(
                other_site_staff["profile"]["employee_account_id"]
            )
        elif mutation == "target_other_tenant":
            request_row.target_employee_account_id = uuid.UUID(
                other_tenant_staff["profile"]["employee_account_id"]
            )
        elif mutation == "target_inactive":
            db.get(
                EmployeeAccount,
                uuid.UUID(staff["blair"]["profile"]["employee_account_id"]),
            ).is_active = False
        elif mutation == "shift_unowned":
            shift_row.assigned_user_id = uuid.UUID(staff["casey"]["user"]["id"])
        elif mutation == "shift_draft":
            shift_row.published_at = None
        elif mutation == "shift_cancelled":
            shift_row.status = "cancelled"
        db.commit()

    response = _approve_request(client, admin, store, request["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_COVER_APPLICATION_INVALID"
    assert expected_message in response.json()["error"]["message"]
    with test_session_local() as db:
        changed = db.get(Shift, uuid.UUID(shift["id"]))
        assert changed.assigned_user_id != uuid.UUID(staff["blair"]["user"]["id"])


def test_untargeted_cover_approval_remains_decision_only(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, _week, shift = _setup_cover_site(client)
    alex_token = _employee_login(client, site_id=store["id"], username="alex")
    untargeted_cover = client.post(
        "/api/v1/employee/me/requests",
        json={"request_type": "cover", "shift_id": shift["id"], "reason": "Open cover"},
        headers=_auth(alex_token),
    )
    assert untargeted_cover.status_code == 201

    cover_response = _approve_request(client, admin, store, untargeted_cover.json()["id"])

    assert cover_response.status_code == 200
    assert cover_response.json()["rota_updated"] is False
    assert cover_response.json()["affected_shift_count"] == 0
    with test_session_local() as db:
        assert db.get(Shift, uuid.UUID(shift["id"])).assigned_user_id == uuid.UUID(
            staff["alex"]["user"]["id"]
        )


def test_employee_token_and_unauthorised_manager_cannot_apply_cover_rota(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, _week, shift = _setup_cover_site(client)
    request = _create_targeted_request(
        client,
        store=store,
        requester_username="alex",
        shift_id=shift["id"],
        target_employee_account_id=staff["blair"]["profile"]["employee_account_id"],
        request_type="cover",
    )
    _accept_inbound(client, store, "blair", request["id"])

    employee_token = _employee_login(client, site_id=store["id"], username="blair")
    employee_response = client.post(
        f"/api/v1/sites/{store['id']}/requests/{request['id']}/approve",
        headers=_auth(employee_token),
    )
    assert employee_response.status_code in {401, 403}

    manager_admin = _register_and_login(client, f"phase-p3-manager-{uuid.uuid4()}@example.com")
    other_store = _create_store(client, manager_admin, f"P3M-{uuid.uuid4()}")
    manager_response = client.post(
        f"/api/v1/sites/{other_store['id']}/requests/{request['id']}/approve",
        headers=_auth(manager_admin["token"]),
    )
    assert manager_response.status_code == 404
    with test_session_local() as db:
        assert db.get(Shift, uuid.UUID(shift["id"])).assigned_user_id == uuid.UUID(
            staff["alex"]["user"]["id"]
        )
