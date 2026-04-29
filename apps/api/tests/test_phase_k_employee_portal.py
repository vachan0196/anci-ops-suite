from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"
WEEK_START = "2026-04-20"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_k_employee_portal.db"
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
        "active_tenant_id": register_body["active_tenant_id"],
        "token": token,
    }


def _auth(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['token']}"}


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
            "full_name": "Phase K Staff",
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
) -> dict:
    user = _create_tenant_member(
        client,
        admin,
        f"phase-k-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase K {username}",
            "job_title": "Cashier",
            "is_active": is_active,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["employee_account_id"]
    return {"user": user, "profile": profile}


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
) -> tuple[dict, dict, dict]:
    admin = _register_and_login(client, f"phase-k-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"K-{uuid.uuid4()}")
    staff = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username=username,
    )
    _configure_opening_hours(client, admin, store["id"])
    return admin, store, staff


def _employee_login(
    client: TestClient,
    *,
    site_id: str,
    username: str,
    password: str = EMPLOYEE_PASSWORD,
):
    return client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": password},
    )


def _employee_auth(login_response) -> dict:
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def _create_site_shift(
    client: TestClient,
    admin: dict,
    *,
    site_id: str,
    assigned_user_id: str,
    start_time: str = "2026-04-20T09:00:00Z",
    end_time: str = "2026-04-20T17:00:00Z",
) -> dict:
    response = client.post(
        f"/api/v1/sites/{site_id}/shifts",
        json={
            "assigned_employee_account_id": assigned_user_id,
            "role_required": "Cashier",
            "start_time": start_time,
            "end_time": end_time,
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


def test_employee_login_succeeds_with_site_username_password(client: TestClient) -> None:
    _, store, staff = _create_ready_store_with_employee(client, username="alex")

    response = _employee_login(client, site_id=store["id"], username="alex")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["employee_account"]["id"] == staff["profile"]["employee_account_id"]
    assert body["employee_account"]["site_id"] == store["id"]


def test_employee_login_rejects_wrong_password_wrong_site_and_inactive(
    client: TestClient,
) -> None:
    admin, store, _ = _create_ready_store_with_employee(client, username="jamie")
    other_store = _create_store(client, admin, f"K-OTHER-{uuid.uuid4()}")
    inactive_store = _create_store(client, admin, f"K-INACTIVE-{uuid.uuid4()}")
    _create_staff_with_employee_account(
        client,
        admin,
        store_id=inactive_store["id"],
        username="inactive",
        is_active=False,
    )

    wrong_password = _employee_login(
        client,
        site_id=store["id"],
        username="jamie",
        password="wrong-password",
    )
    wrong_site = _employee_login(client, site_id=other_store["id"], username="jamie")
    inactive = _employee_login(client, site_id=inactive_store["id"], username="inactive")

    assert wrong_password.status_code == 401
    assert wrong_site.status_code == 401
    assert inactive.status_code == 403


def test_employee_my_rota_returns_only_published_assigned_shifts(
    client: TestClient,
) -> None:
    admin, store, staff = _create_ready_store_with_employee(client, username="sam")
    shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_user_id=staff["user"]["id"],
    )
    login_response = _employee_login(client, site_id=store["id"], username="sam")
    assert login_response.status_code == 200

    draft_response = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_employee_auth(login_response),
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["shifts"] == []

    _publish_rota(client, admin, store["id"])
    published_response = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_employee_auth(login_response),
    )

    assert published_response.status_code == 200
    body = published_response.json()
    assert body["site_id"] == store["id"]
    assert body["employee_account_id"] == staff["profile"]["employee_account_id"]
    assert body["shifts"] == [
        {
            "id": shift["id"],
            "start_time": shift["start_time"],
            "end_time": shift["end_time"],
            "role_required": "cashier",
            "status": "scheduled",
        }
    ]


def test_employee_my_rota_excludes_cancelled_and_coworker_shifts(
    client: TestClient,
) -> None:
    admin, store, staff = _create_ready_store_with_employee(client, username="taylor")
    coworker = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="casey",
    )
    own_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_user_id=staff["user"]["id"],
    )
    cancelled_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_user_id=staff["user"]["id"],
        start_time="2026-04-21T09:00:00Z",
        end_time="2026-04-21T17:00:00Z",
    )
    coworker_shift = _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_user_id=coworker["user"]["id"],
        start_time="2026-04-22T09:00:00Z",
        end_time="2026-04-22T17:00:00Z",
    )
    cancel_response = client.post(
        f"/api/v1/sites/{store['id']}/shifts/{cancelled_shift['id']}/cancel",
        headers=_auth(admin),
    )
    assert cancel_response.status_code == 200
    _publish_rota(client, admin, store["id"])

    login_response = _employee_login(client, site_id=store["id"], username="taylor")
    response = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_employee_auth(login_response),
    )

    assert response.status_code == 200
    assert [shift["id"] for shift in response.json()["shifts"]] == [own_shift["id"]]
    assert cancelled_shift["id"] not in [shift["id"] for shift in response.json()["shifts"]]
    assert coworker_shift["id"] not in [shift["id"] for shift in response.json()["shifts"]]


def test_employee_cannot_access_admin_weekly_rota_endpoint(client: TestClient) -> None:
    _, store, _ = _create_ready_store_with_employee(client, username="morgan")
    login_response = _employee_login(client, site_id=store["id"], username="morgan")

    response = client.get(
        f"/api/v1/sites/{store['id']}/rota/week",
        params={"week_start": WEEK_START},
        headers=_employee_auth(login_response),
    )

    assert response.status_code == 401


def test_unpublish_immediately_removes_employee_visibility(client: TestClient) -> None:
    admin, store, staff = _create_ready_store_with_employee(client, username="riley")
    _create_site_shift(
        client,
        admin,
        site_id=store["id"],
        assigned_user_id=staff["user"]["id"],
    )
    _publish_rota(client, admin, store["id"])
    login_response = _employee_login(client, site_id=store["id"], username="riley")
    before = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_employee_auth(login_response),
    )
    assert len(before.json()["shifts"]) == 1

    unpublish_response = client.post(
        f"/api/v1/sites/{store['id']}/rota/unpublish",
        json={"week_start": WEEK_START},
        headers=_auth(admin),
    )
    assert unpublish_response.status_code == 200
    after = client.get(
        "/api/v1/employee/rota/my",
        params={"week_start": WEEK_START},
        headers=_employee_auth(login_response),
    )

    assert after.status_code == 200
    assert after.json()["shifts"] == []
