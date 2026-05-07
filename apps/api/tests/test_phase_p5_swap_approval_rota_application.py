from collections.abc import Generator
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
    _employee_login,
    _future_monday,
    _register_and_login,
)
from apps.api.tests.test_phase_p4_swap_target_shift_modelling import (
    _create_valid_swap,
    _publish,
    _setup_swap_site,
)


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_p5_swap_approval_rota_application.db"
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


def _accept_swap(client: TestClient, *, store: dict, request_id: str) -> None:
    token = _employee_login(client, site_id=store["id"], username="blair")
    response = client.post(
        f"/api/v1/employee/me/inbound-requests/{request_id}/accept",
        headers=_auth(token),
    )
    assert response.status_code == 200


def _approve_swap(client: TestClient, *, admin: dict, store: dict, request_id: str):
    return client.post(
        f"/api/v1/sites/{store['id']}/requests/{request_id}/approve",
        json={"approval_reason": "Approved swap"},
        headers=_auth(admin["token"]),
    )


def test_approving_target_accepted_swap_exchanges_both_published_scheduled_shifts(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, shifts, weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    _accept_swap(client, store=store, request_id=created["id"])

    with test_session_local() as db:
        requester_before = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_before = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        requester_start = requester_before.start_at
        requester_end = requester_before.end_at
        requester_published_at = requester_before.published_at
        target_start = target_before.start_at
        target_end = target_before.end_at
        target_published_at = target_before.published_at

    response = _approve_swap(client, admin=admin, store=store, request_id=created["id"])

    assert response.status_code == 200
    assert response.json() == {
        "id": created["id"],
        "status": "approved",
        "rota_updated": True,
        "affected_shift_count": 2,
        "message": "Swap request approved and both shifts were exchanged.",
    }
    with test_session_local() as db:
        request = db.get(ShiftRequest, uuid.UUID(created["id"]))
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        assert request.status == "approved"
        assert request.approver_user_id == uuid.UUID(admin["id"])
        assert request.decided_at is not None
        assert requester_shift.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])
        assert target_shift.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert requester_shift.status == "scheduled"
        assert target_shift.status == "scheduled"
        assert requester_shift.published_at == requester_published_at
        assert target_shift.published_at == target_published_at
        assert requester_shift.start_at == requester_start
        assert requester_shift.end_at == requester_end
        assert target_shift.start_at == target_start
        assert target_shift.end_at == target_end
        actions = {
            action
            for (action,) in db.execute(
                select(AuditLog.action).where(
                    AuditLog.entity_id.in_(
                        [created["id"], shifts["requester"]["id"], shifts["target"]["id"]]
                    )
                )
            ).all()
        }
        assert "request_approved" in actions
        assert "approved_swap_reassigned_requester_shift" in actions
        assert "approved_swap_reassigned_target_shift" in actions

    alex_token = _employee_login(client, site_id=store["id"], username="alex")
    blair_token = _employee_login(client, site_id=store["id"], username="blair")
    alex_rota = client.get(
        f"/api/v1/employee/rota/my?week_start={weeks['target'].date().isoformat()}",
        headers=_auth(alex_token),
    )
    blair_rota = client.get(
        f"/api/v1/employee/rota/my?week_start={weeks['requester'].date().isoformat()}",
        headers=_auth(blair_token),
    )
    assert alex_rota.status_code == 200
    assert blair_rota.status_code == 200
    assert [shift["id"] for shift in alex_rota.json()["shifts"]] == [shifts["target"]["id"]]
    assert [shift["id"] for shift in blair_rota.json()["shifts"]] == [shifts["requester"]["id"]]


def test_pending_swap_cannot_be_approved_before_target_acceptance(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)

    response = _approve_swap(client, admin=admin, store=store, request_id=created["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_TARGET_NOT_ACCEPTED"
    with test_session_local() as db:
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        assert requester_shift.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert target_shift.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])


@pytest.mark.parametrize("status", ["target_declined", "cancelled", "rejected", "approved"])
def test_non_actionable_swap_statuses_do_not_mutate_rota(
    client: TestClient,
    test_session_local,
    status: str,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    with test_session_local() as db:
        row = db.get(ShiftRequest, uuid.UUID(created["id"]))
        row.status = status
        db.commit()

    response = _approve_swap(client, admin=admin, store=store, request_id=created["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_NOT_PENDING"
    with test_session_local() as db:
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        assert requester_shift.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert target_shift.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_target_shift",
        "requester_unassigned",
        "target_unassigned",
        "requester_draft",
        "target_draft",
        "requester_cancelled",
        "target_cancelled",
        "requester_inactive",
        "target_inactive",
        "requester_profile_inactive",
        "target_profile_inactive",
        "target_other_site",
        "target_other_tenant",
    ],
)
def test_invalid_swap_application_data_does_not_mutate_rota(
    client: TestClient,
    test_session_local,
    mutation: str,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    _accept_swap(client, store=store, request_id=created["id"])

    other_site_shift = None
    other_tenant_shift = None
    if mutation == "target_other_site":
        other_store = _create_store(client, admin, f"P5O-{uuid.uuid4()}")
        _configure_opening_hours(client, admin, other_store["id"])
        other_site_staff = _create_staff_with_employee_account(
            client,
            admin,
            store_id=other_store["id"],
            username=f"other-{uuid.uuid4()}",
        )
        other_site_week = _future_monday(77)
        other_site_shift = _create_shift(
            client,
            admin,
            other_store["id"],
            other_site_staff["user"]["id"],
            week=other_site_week,
        )
        _publish(client, admin, other_store["id"], other_site_week)
    elif mutation == "target_other_tenant":
        other_admin = _register_and_login(client, f"phase-p5-other-{uuid.uuid4()}@example.com")
        other_tenant_store = _create_store(client, other_admin, f"P5X-{uuid.uuid4()}")
        _configure_opening_hours(client, other_admin, other_tenant_store["id"])
        other_tenant_staff = _create_staff_with_employee_account(
            client,
            other_admin,
            store_id=other_tenant_store["id"],
            username=f"external-{uuid.uuid4()}",
        )
        other_tenant_week = _future_monday(91)
        other_tenant_shift = _create_shift(
            client,
            other_admin,
            other_tenant_store["id"],
            other_tenant_staff["user"]["id"],
            week=other_tenant_week,
        )
        _publish(client, other_admin, other_tenant_store["id"], other_tenant_week)

    with test_session_local() as db:
        request = db.get(ShiftRequest, uuid.UUID(created["id"]))
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        if mutation == "missing_target_shift":
            request.target_shift_id = None
        elif mutation == "requester_unassigned":
            requester_shift.assigned_user_id = None
        elif mutation == "target_unassigned":
            target_shift.assigned_user_id = None
        elif mutation == "requester_draft":
            requester_shift.published_at = None
        elif mutation == "target_draft":
            target_shift.published_at = None
        elif mutation == "requester_cancelled":
            requester_shift.status = "cancelled"
        elif mutation == "target_cancelled":
            target_shift.status = "cancelled"
        elif mutation == "requester_inactive":
            db.get(
                EmployeeAccount,
                uuid.UUID(staff["alex"]["profile"]["employee_account_id"]),
            ).is_active = False
        elif mutation == "target_inactive":
            db.get(
                EmployeeAccount,
                uuid.UUID(staff["blair"]["profile"]["employee_account_id"]),
            ).is_active = False
        elif mutation == "requester_profile_inactive":
            db.get(StaffProfile, uuid.UUID(staff["alex"]["profile"]["id"])).is_active = False
        elif mutation == "target_profile_inactive":
            db.get(StaffProfile, uuid.UUID(staff["blair"]["profile"]["id"])).is_active = False
        elif mutation == "target_other_site":
            assert other_site_shift is not None
            request.target_shift_id = uuid.UUID(other_site_shift["id"])
        elif mutation == "target_other_tenant":
            assert other_tenant_shift is not None
            request.target_shift_id = uuid.UUID(other_tenant_shift["id"])
        db.commit()

    response = _approve_swap(client, admin=admin, store=store, request_id=created["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] in {
        "REQUEST_SWAP_APPLICATION_INVALID",
        "REQUEST_TARGET_SHIFT_INVALID",
    }
    with test_session_local() as db:
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        if requester_shift is not None and target_shift is not None:
            assert requester_shift.assigned_user_id != uuid.UUID(staff["blair"]["user"]["id"])
            assert target_shift.assigned_user_id != uuid.UUID(staff["alex"]["user"]["id"])


def test_employee_token_and_unauthorised_site_cannot_apply_swap_rota(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    _accept_swap(client, store=store, request_id=created["id"])

    employee_token = _employee_login(client, site_id=store["id"], username="blair")
    employee_response = client.post(
        f"/api/v1/sites/{store['id']}/requests/{created['id']}/approve",
        headers=_auth(employee_token),
    )
    assert employee_response.status_code in {401, 403}

    other_store = _create_store(client, admin, f"P5M-{uuid.uuid4()}")
    manager_response = client.post(
        f"/api/v1/sites/{other_store['id']}/requests/{created['id']}/approve",
        headers=_auth(admin["token"]),
    )
    assert manager_response.status_code == 404
    with test_session_local() as db:
        requester_shift = db.get(Shift, uuid.UUID(shifts["requester"]["id"]))
        target_shift = db.get(Shift, uuid.UUID(shifts["target"]["id"]))
        assert requester_shift.assigned_user_id == uuid.UUID(staff["alex"]["user"]["id"])
        assert target_shift.assigned_user_id == uuid.UUID(staff["blair"]["user"]["id"])


def test_already_approved_swap_cannot_be_approved_again(
    client: TestClient,
) -> None:
    admin, store, staff, shifts, _weeks = _setup_swap_site(client)
    created = _create_valid_swap(client, store=store, staff=staff, shifts=shifts)
    _accept_swap(client, store=store, request_id=created["id"])
    first = _approve_swap(client, admin=admin, store=store, request_id=created["id"])
    second = _approve_swap(client, admin=admin, store=store, request_id=created["id"])

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "REQUEST_NOT_PENDING"
