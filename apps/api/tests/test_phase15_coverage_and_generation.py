from collections.abc import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.shift import Shift
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User


PASSWORD = "password123"


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
        "id": uuid.UUID(register_body["id"]),
        "active_tenant_id": uuid.UUID(register_body["active_tenant_id"]),
        "token": token,
    }


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
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase15_coverage_and_generation.db"
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


def test_coverage_templates_admin_crud_happy_path(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-ct-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-CT-001")

    create_response = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 2,
            "required_role": "crew",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_response.status_code == 201
    template_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/coverage-templates",
        params={"store_id": store_id},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    patch_response = client.patch(
        f"/api/v1/coverage-templates/{template_id}",
        json={"required_headcount": 3, "is_active": False},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["required_headcount"] == 3
    assert patch_response.json()["is_active"] is False

    delete_response = client.delete(
        f"/api/v1/coverage-templates/{template_id}",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert delete_response.status_code == 200


def test_coverage_templates_cross_tenant_access_returns_404(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"p15-ct-iso-admin-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p15-ct-iso-admin-b-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin_a["token"], "P15-CT-ISO")

    create_response = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 1,
            "start_time": "10:00:00",
            "end_time": "18:00:00",
            "required_headcount": 1,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert create_response.status_code == 201
    template_id = create_response.json()["id"]

    cross_patch = client.patch(
        f"/api/v1/coverage-templates/{template_id}",
        json={"required_headcount": 2},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_patch.status_code == 404

    cross_delete = client.delete(
        f"/api/v1/coverage-templates/{template_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_delete.status_code == 404


def test_coverage_templates_validation_errors(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-ct-validation-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-CT-VAL")

    bad_day = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 7,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert bad_day.status_code == 422

    bad_headcount = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 2,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 0,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert bad_headcount.status_code == 422

    bad_time = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 2,
            "start_time": "17:00:00",
            "end_time": "09:00:00",
            "required_headcount": 1,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert bad_time.status_code == 422


def test_generate_week_creates_expected_shifts_and_fields(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p15-rota-generate-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-ROTA-001")

    create_template_monday = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 2,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_template_monday.status_code == 201

    create_template_tuesday = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 1,
            "start_time": "12:00:00",
            "end_time": "16:00:00",
            "required_headcount": 1,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_template_tuesday.status_code == 201

    generate = client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_id, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert generate.status_code == 200
    assert generate.json()["created_count"] == 3

    db = test_session_local()
    try:
        shifts = db.scalars(select(Shift).where(Shift.store_id == uuid.UUID(store_id))).all()
        assert len(shifts) == 3
        assert all(shift.assigned_user_id is None for shift in shifts)
        assert all(shift.status == "scheduled" for shift in shifts)
        assert all(shift.published_at is None for shift in shifts)
    finally:
        db.close()


def test_generate_week_returns_409_if_shifts_already_exist(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-rota-conflict-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-ROTA-409")

    template = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert template.status_code == 201

    existing_shift = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": "2026-04-06T09:00:00Z",
            "end_at": "2026-04-06T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert existing_shift.status_code == 201

    generate = client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_id, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert generate.status_code == 409


def test_generate_week_cross_tenant_store_returns_404(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"p15-rota-iso-admin-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p15-rota-iso-admin-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a["token"], "P15-ROTA-ISO")

    generate = client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_a, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert generate.status_code == 404
