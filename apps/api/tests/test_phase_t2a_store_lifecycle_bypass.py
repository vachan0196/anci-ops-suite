from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.store import Store


PASSWORD = "password123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_t2a_store_lifecycle_bypass.db"
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_owner(client: TestClient, email_prefix: str) -> dict:
    email = f"{email_prefix}-{uuid.uuid4()}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    body = register.json()
    body["email"] = email
    body["token"] = login.json()["access_token"]
    return body


def _create_admin(client: TestClient, owner: dict, label: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"t2a-admin-{label}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Phase T2a Admin {label}",
            "role": "admin",
        },
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 201, response.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": response.json()["email"], "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    body = response.json()
    body["token"] = login.json()["access_token"]
    return body


def _create_store(client: TestClient, owner: dict, label: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"T2A-{label}-{uuid.uuid4()}",
            "name": f"Phase T2a {label}",
            "timezone": "Europe/London",
        },
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 201, response.text
    assert response.json()["is_active"] is True
    return response.json()


def _get_store(client: TestClient, owner: dict, store_id: str) -> dict:
    response = client.get(f"/api/v1/stores/{store_id}", headers=_auth(owner["token"]))
    assert response.status_code == 200, response.text
    return response.json()


def _force_store_active_state(test_session_local, store_id: str, *, is_active: bool) -> None:
    db = test_session_local()
    try:
        store = db.get(Store, uuid.UUID(store_id))
        assert store is not None
        store.is_active = is_active
        db.commit()
    finally:
        db.close()


def test_patch_cannot_deactivate_store_and_state_remains_active(client: TestClient) -> None:
    owner = _register_owner(client, "t2a-patch-deactivate-owner")
    store = _create_store(client, owner, "patch-deactivate")

    response = client.patch(
        f"/api/v1/stores/{store['id']}",
        json={"is_active": False},
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 422

    after = _get_store(client, owner, store["id"])
    assert after["is_active"] is True
    assert after["name"] == store["name"]


def test_patch_cannot_reactivate_store_and_state_remains_inactive(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, "t2a-patch-reactivate-owner")
    store = _create_store(client, owner, "patch-reactivate")
    _force_store_active_state(test_session_local, store["id"], is_active=False)

    before = _get_store(client, owner, store["id"])
    assert before["is_active"] is False

    response = client.patch(
        f"/api/v1/stores/{store['id']}",
        json={"is_active": True},
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 422

    after = _get_store(client, owner, store["id"])
    assert after["is_active"] is False
    assert after["name"] == store["name"]


def test_normal_store_patch_still_updates_allowed_fields_and_keeps_lifecycle_state(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "t2a-normal-patch-owner")
    store = _create_store(client, owner, "normal-patch")

    response = client.patch(
        f"/api/v1/stores/{store['id']}",
        json={"name": "Phase T2a Updated Store", "city": "London"},
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Phase T2a Updated Store"
    assert response.json()["city"] == "London"
    assert response.json()["is_active"] is True

    after = _get_store(client, owner, store["id"])
    assert after["name"] == "Phase T2a Updated Store"
    assert after["city"] == "London"
    assert after["is_active"] is True


def test_mixed_normal_and_lifecycle_patch_is_rejected_without_partial_update(
    client: TestClient,
) -> None:
    owner = _register_owner(client, "t2a-mixed-patch-owner")
    store = _create_store(client, owner, "mixed-patch")

    response = client.patch(
        f"/api/v1/stores/{store['id']}",
        json={"name": "Should Not Persist", "is_active": False},
        headers=_auth(owner["token"]),
    )
    assert response.status_code == 422

    after = _get_store(client, owner, store["id"])
    assert after["name"] == store["name"]
    assert after["is_active"] is True


def test_deactivate_endpoint_remains_protected(client: TestClient) -> None:
    owner = _register_owner(client, "t2a-deactivate-owner")
    admin = _create_admin(client, owner, "deactivate")
    store = _create_store(client, owner, "deactivate-protected")

    admin_response = client.post(
        f"/api/v1/stores/{store['id']}/deactivate",
        headers=_auth(admin["token"]),
    )
    assert admin_response.status_code == 403
    assert admin_response.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    owner_without_step_up = client.post(
        f"/api/v1/stores/{store['id']}/deactivate",
        headers=_auth(owner["token"]),
    )
    assert owner_without_step_up.status_code == 403
    assert owner_without_step_up.json()["error"]["code"] == "AUTH_EMAIL_VERIFICATION_REQUIRED"

    after = _get_store(client, owner, store["id"])
    assert after["is_active"] is True


def test_cross_tenant_patch_with_lifecycle_field_is_blocked_and_state_unchanged(
    client: TestClient,
) -> None:
    owner_a = _register_owner(client, "t2a-cross-owner-a")
    owner_b = _register_owner(client, "t2a-cross-owner-b")
    store_b = _create_store(client, owner_b, "cross-tenant")

    normal_cross_tenant = client.patch(
        f"/api/v1/stores/{store_b['id']}",
        json={"name": "Cross Tenant Rename"},
        headers=_auth(owner_a["token"]),
    )
    assert normal_cross_tenant.status_code == 404
    assert normal_cross_tenant.json()["error"]["code"] == "STORE_NOT_FOUND"

    response = client.patch(
        f"/api/v1/stores/{store_b['id']}",
        json={"is_active": False},
        headers=_auth(owner_a["token"]),
    )
    assert response.status_code in {404, 422}

    after = _get_store(client, owner_b, store_b["id"])
    assert after["is_active"] is True
    assert after["name"] == store_b["name"]
