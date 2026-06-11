import uuid

from fastapi.testclient import TestClient

from apps.api.models.shift import Shift
from apps.api.tests.test_phase_t0_tenant_role_security_gate import (
    _auth,
    _create_staff_with_employee_account,
    _create_store,
    _register_owner,
    client,
    test_session_local,
)


def test_staff_role_removal_does_not_change_existing_shift_assignment(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "staffsite-d2-no-cascade")
    store = _create_store(client, owner, "staffsite-d2-no-cascade")
    staff = _create_staff_with_employee_account(
        client,
        owner,
        store_id=store["id"],
        username="staffsite-d2-no-cascade",
    )

    add_role = client.post(
        f"/api/v1/staff/{staff['profile']['id']}/roles",
        json={"role": "cashier"},
        headers=_auth(owner["token"]),
    )
    assert add_role.status_code == 200, add_role.text

    create_shift = client.post(
        f"/api/v1/sites/{store['id']}/shifts",
        json={
            "assigned_employee_account_id": staff["profile"]["user_id"],
            "role_required": "cashier",
            "start_time": "2026-04-06T09:00:00Z",
            "end_time": "2026-04-06T17:00:00Z",
        },
        headers=_auth(owner["token"]),
    )
    assert create_shift.status_code == 201, create_shift.text
    shift_id = create_shift.json()["id"]

    delete_role = client.delete(
        f"/api/v1/staff/{staff['profile']['id']}/roles/cashier",
        headers=_auth(owner["token"]),
    )
    assert delete_role.status_code == 204

    db = test_session_local()
    try:
        shift = db.get(Shift, uuid.UUID(shift_id))
        assert shift is not None
        assert str(shift.assigned_user_id) == staff["profile"]["user_id"]
        assert str(shift.store_id) == store["id"]
        assert shift.required_role == "cashier"
        assert shift.status == "scheduled"
    finally:
        db.close()
