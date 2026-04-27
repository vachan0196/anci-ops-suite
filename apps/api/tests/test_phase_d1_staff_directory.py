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
SENSITIVE_DIRECTORY_FIELDS = {
    "password",
    "hashed_password",
    "hourly_rate",
    "nationalInsuranceNumber",
    "national_insurance_number",
    "document_type",
    "right_to_work",
    "rtw_status",
    "weekly_hour_cap",
    "overtime_rate",
    "base_hours",
    "tenant_id",
}


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_d1_staff_directory.db"
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


def _create_store(client: TestClient, admin: dict, name: str = "Directory Store") -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"DIR-{uuid.uuid4()}",
            "name": name,
            "timezone": "Europe/London",
            "address_line1": "1 Directory Road",
            "city": None,
            "postcode": None,
            "phone": "07111111111",
            "manager_user_id": None,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_tenant_user(
    client: TestClient,
    admin: dict,
    *,
    email: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email or f"directory-staff-{uuid.uuid4()}@example.com",
            "password": "staff-password-123",
            "full_name": "Directory Staff",
            "role": "member",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_staff_profile(
    client: TestClient,
    admin: dict,
    *,
    user_id: str,
    store_id: str | None = None,
    display_name: str = "Directory Staff",
    is_active: bool = True,
) -> dict:
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user_id,
            "store_id": store_id,
            "display_name": display_name,
            "job_title": "Cashier",
            "hourly_rate": "12.50",
            "pay_type": "hourly",
            "phone": "07111111111",
            "rtw_status": "pending",
            "is_active": is_active,
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _add_role(client: TestClient, admin: dict, staff_id: str, role: str) -> dict:
    response = client.post(
        f"/api/v1/staff/{staff_id}/roles",
        json={"role": role},
        headers=_auth(admin),
    )
    assert response.status_code == 200
    return response.json()


def _create_directory_staff(
    client: TestClient,
    admin: dict,
    *,
    store: dict | None = None,
    display_name: str = "Directory Staff",
    email: str | None = None,
    roles: list[str] | None = None,
    is_active: bool = True,
) -> tuple[dict, dict, dict | None]:
    tenant_user = _create_tenant_user(client, admin, email=email)
    staff = _create_staff_profile(
        client,
        admin,
        user_id=tenant_user["id"],
        store_id=store["id"] if store else None,
        display_name=display_name,
        is_active=is_active,
    )
    for role in roles or []:
        _add_role(client, admin, staff["id"], role)
    return tenant_user, staff, store


def _list_directory(client: TestClient, admin: dict, query: str = "") -> list[dict]:
    response = client.get(
        f"/api/v1/staff/directory{query}",
        headers=_auth(admin),
    )
    assert response.status_code == 200
    return response.json()


def test_admin_can_list_staff_directory_with_email_store_and_role(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, f"d1-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, name="Directory Location")
    staff_email = f"d1-staff-{uuid.uuid4()}@example.com"
    _, staff, _ = _create_directory_staff(
        client,
        admin,
        store=store,
        display_name="Directory Person",
        email=staff_email,
        roles=["Cashier"],
    )

    body = _list_directory(client, admin)
    item = next(row for row in body if row["id"] == staff["id"])

    assert item["display_name"] == "Directory Person"
    assert item["email"] == staff_email
    assert item["phone"] == "07111111111"
    assert item["store_id"] == store["id"]
    assert item["store_name"] == "Directory Location"
    assert item["roles"] == ["cashier"]
    assert item["is_active"] is True
    assert item["created_at"]


def test_directory_includes_multiple_normalized_roles(client: TestClient) -> None:
    admin = _register_and_login(client, f"d1-roles-admin-{uuid.uuid4()}@example.com")
    _, staff, _ = _create_directory_staff(
        client,
        admin,
        display_name="Multi Role Staff",
        roles=["Supervisor", "Cashier"],
    )

    item = next(row for row in _list_directory(client, admin) if row["id"] == staff["id"])

    assert item["roles"] == ["cashier", "supervisor"]


def test_directory_includes_store_name(client: TestClient) -> None:
    admin = _register_and_login(client, f"d1-store-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, name="Store Name Read Model")
    _, staff, _ = _create_directory_staff(client, admin, store=store)

    item = next(row for row in _list_directory(client, admin) if row["id"] == staff["id"])

    assert item["store_name"] == "Store Name Read Model"


def test_directory_supports_unassigned_staff(client: TestClient) -> None:
    admin = _register_and_login(client, f"d1-unassigned-admin-{uuid.uuid4()}@example.com")
    _, staff, _ = _create_directory_staff(client, admin, store=None)

    item = next(row for row in _list_directory(client, admin) if row["id"] == staff["id"])

    assert item["store_id"] is None
    assert item["store_name"] is None


def test_directory_tenant_isolation(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"d1-tenant-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"d1-tenant-b-{uuid.uuid4()}@example.com")
    _, staff_a, _ = _create_directory_staff(
        client,
        admin_a,
        display_name="Tenant A Staff",
    )

    body = _list_directory(client, admin_b)

    assert all(row["id"] != staff_a["id"] for row in body)
    assert all(row["display_name"] != "Tenant A Staff" for row in body)


def test_directory_store_id_filter(client: TestClient) -> None:
    admin = _register_and_login(client, f"d1-filter-admin-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin, name="Filter Store A")
    store_b = _create_store(client, admin, name="Filter Store B")
    _, staff_a, _ = _create_directory_staff(
        client,
        admin,
        store=store_a,
        display_name="Filter Staff A",
    )
    _, staff_b, _ = _create_directory_staff(
        client,
        admin,
        store=store_b,
        display_name="Filter Staff B",
    )

    body = _list_directory(client, admin, query=f"?store_id={store_a['id']}")

    assert any(row["id"] == staff_a["id"] for row in body)
    assert all(row["id"] != staff_b["id"] for row in body)


def test_directory_sensitive_fields_not_returned(client: TestClient) -> None:
    admin = _register_and_login(client, f"d1-sensitive-admin-{uuid.uuid4()}@example.com")
    _, staff, _ = _create_directory_staff(client, admin, roles=["Cashier"])

    item = next(row for row in _list_directory(client, admin) if row["id"] == staff["id"])

    assert SENSITIVE_DIRECTORY_FIELDS.isdisjoint(item.keys())


def test_directory_unauthenticated_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/staff/directory")

    assert response.status_code == 401
