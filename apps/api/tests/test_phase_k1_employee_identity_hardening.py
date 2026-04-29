from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.staff_profile import StaffProfile


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"
WEEK_START = "2026-04-20"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_k1_employee_identity_hardening.db"
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


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _register_and_login(client: TestClient, email: str) -> dict:
    register_body = _register(client, email)
    token = _login(client, email)
    return {
        "id": register_body["id"],
        "email": email,
        "active_tenant_id": register_body["active_tenant_id"],
        "token": token,
    }


def _auth(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['token']}"}


def _token_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_store(client: TestClient, admin: dict, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": code,
            "name": f"Store {code}",
            "timezone": "Europe/London",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_tenant_member(client: TestClient, admin: dict, email: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Phase K1 Staff",
            "role": "member",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_staff_with_employee_account(
    client: TestClient,
    admin: dict,
    *,
    store_id: str,
    username: str,
    is_active: bool = True,
    assert_success: bool = True,
):
    user = _create_tenant_member(
        client,
        admin,
        f"phase-k1-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase K1 {username}",
            "job_title": "Cashier",
            "is_active": is_active,
        },
        headers=_auth(admin),
    )
    if not assert_success:
        return user, response

    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    assert "employee_password" not in profile
    assert "hashed_password" not in profile
    return user, profile


def _configure_opening_hours(client: TestClient, admin: dict, store_id: str) -> None:
    response = client.put(
        f"/api/v1/stores/{store_id}/opening-hours",
        json={
            "opening_hours": [
                {
                    "day_of_week": day,
                    "open_time": "06:00",
                    "close_time": "22:00",
                    "is_closed": False,
                }
                for day in range(7)
            ]
        },
        headers=_auth(admin),
    )
    assert response.status_code == 200


def _create_ready_store_with_employee(
    client: TestClient,
    *,
    username: str,
) -> tuple[dict, dict, dict, dict]:
    admin = _register_and_login(client, f"phase-k1-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"K1-{uuid.uuid4()}")
    user, profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username=username,
    )
    _configure_opening_hours(client, admin, store["id"])
    return admin, store, user, profile


def _employee_login(client: TestClient, *, site_id: str, username: str):
    return client.post(
        "/api/v1/auth/employee/login",
        json={
            "site_id": site_id,
            "username": username,
            "password": EMPLOYEE_PASSWORD,
        },
    )


def _create_site_shift(
    client: TestClient,
    admin: dict,
    *,
    site_id: str,
    assigned_user_id: str,
) -> dict:
    response = client.post(
        f"/api/v1/sites/{site_id}/shifts",
        json={
            "assigned_employee_account_id": assigned_user_id,
            "role_required": "Cashier",
            "start_time": "2026-04-20T09:00:00Z",
            "end_time": "2026-04-20T17:00:00Z",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _publish_rota(client: TestClient, admin: dict, site_id: str) -> None:
    response = client.post(
        f"/api/v1/sites/{site_id}/rota/publish",
        json={"week_start": WEEK_START},
        headers=_auth(admin),
    )
    assert response.status_code == 200


def test_auth_me_keeps_admin_shape_and_accepts_employee_shape(client: TestClient) -> None:
    admin, store, _, profile = _create_ready_store_with_employee(
        client,
        username="alex",
    )

    admin_response = client.get("/api/v1/auth/me", headers=_auth(admin))
    assert admin_response.status_code == 200
    admin_body = admin_response.json()
    assert admin_body["id"] == admin["id"]
    assert admin_body["email"] == admin["email"]
    assert admin_body["active_tenant_id"] == admin["active_tenant_id"]
    assert admin_body["active_tenant_role"] == "admin"

    login_response = _employee_login(client, site_id=store["id"], username="alex")
    assert login_response.status_code == 200
    employee_auth = _token_auth(login_response.json()["access_token"])

    employee_me = client.get("/api/v1/auth/me", headers=employee_auth)
    employee_specific_me = client.get("/api/v1/auth/employee/me", headers=employee_auth)

    assert employee_me.status_code == 200
    assert employee_me.json() == {
        "portal": "employee",
        "employee_account_id": profile["employee_account_id"],
        "tenant_id": admin["active_tenant_id"],
        "site_id": store["id"],
        "display_name": "Phase K1 alex",
    }
    assert employee_specific_me.status_code == 200
    assert employee_specific_me.json() == employee_me.json()


def test_admin_and_employee_tokens_are_not_interchangeable(client: TestClient) -> None:
    admin, store, _, _ = _create_ready_store_with_employee(client, username="jamie")
    employee_token = _employee_login(
        client,
        site_id=store["id"],
        username="jamie",
    ).json()["access_token"]

    admin_on_employee_endpoint = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_auth(admin),
    )
    employee_on_admin_endpoint = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": WEEK_START},
        headers=_token_auth(employee_token),
    )

    assert admin_on_employee_endpoint.status_code == 401
    assert employee_on_admin_endpoint.status_code == 401


def test_duplicate_username_same_site_rejected_without_partial_staff(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-k1-dupe-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"K1-DUPE-{uuid.uuid4()}")
    _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="sam",
    )

    _, duplicate_response = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="sam",
        assert_success=False,
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "EMPLOYEE_USERNAME_EXISTS"
    assert "hashed_password" not in duplicate_response.text
    with test_session_local() as db:
        employee_accounts = db.scalars(
            select(EmployeeAccount).where(
                EmployeeAccount.tenant_id == uuid.UUID(admin["active_tenant_id"]),
                EmployeeAccount.store_id == uuid.UUID(store["id"]),
                EmployeeAccount.username == "sam",
            )
        ).all()
        linked_profiles = db.scalars(
            select(StaffProfile).where(
                StaffProfile.tenant_id == uuid.UUID(admin["active_tenant_id"]),
                StaffProfile.store_id == uuid.UUID(store["id"]),
                StaffProfile.employee_account_id.is_not(None),
            )
        ).all()
    assert len(employee_accounts) == 1
    assert len(linked_profiles) == 1


def test_same_username_allowed_in_different_sites_and_links_one_account_each(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-k1-sites-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin, f"K1-A-{uuid.uuid4()}")
    store_b = _create_store(client, admin, f"K1-B-{uuid.uuid4()}")

    _, profile_a = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store_a["id"],
        username="casey",
    )
    _, profile_b = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store_b["id"],
        username="casey",
    )

    assert profile_a["employee_account_id"] != profile_b["employee_account_id"]
    with test_session_local() as db:
        accounts = db.scalars(
            select(EmployeeAccount).where(
                EmployeeAccount.tenant_id == uuid.UUID(admin["active_tenant_id"]),
                EmployeeAccount.username == "casey",
            )
        ).all()
    assert len(accounts) == 2
    assert all(account.hashed_password != EMPLOYEE_PASSWORD for account in accounts)


def test_inactive_employee_account_cannot_login_or_use_rota(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store, _, profile = _create_ready_store_with_employee(
        client,
        username="morgan",
    )
    active_login = _employee_login(client, site_id=store["id"], username="morgan")
    assert active_login.status_code == 200

    with test_session_local() as db:
        account = db.get(EmployeeAccount, uuid.UUID(profile["employee_account_id"]))
        assert account is not None
        account.is_active = False
        db.commit()

    inactive_login = _employee_login(client, site_id=store["id"], username="morgan")
    inactive_rota = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_token_auth(active_login.json()["access_token"]),
    )

    assert inactive_login.status_code == 403
    assert inactive_rota.status_code == 403


def test_inactive_linked_staff_profile_cannot_login(
    client: TestClient,
    test_session_local,
) -> None:
    _, store, _, profile = _create_ready_store_with_employee(client, username="riley")
    with test_session_local() as db:
        staff_profile = db.get(StaffProfile, uuid.UUID(profile["id"]))
        assert staff_profile is not None
        staff_profile.is_active = False
        db.commit()

    response = _employee_login(client, site_id=store["id"], username="riley")

    assert response.status_code == 403


def test_employee_rota_still_hides_draft_and_shows_published_assigned_shift(
    client: TestClient,
) -> None:
    admin, store, user, _ = _create_ready_store_with_employee(
        client,
        username="taylor",
    )
    shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_user_id=user["id"],
    )
    employee_token = _employee_login(
        client,
        site_id=store["id"],
        username="taylor",
    ).json()["access_token"]
    employee_auth = _token_auth(employee_token)

    draft_response = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=employee_auth,
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["shifts"] == []

    _publish_rota(client, admin, store["id"])
    published_response = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=employee_auth,
    )

    assert published_response.status_code == 200
    assert [item["id"] for item in published_response.json()["shifts"]] == [shift["id"]]
