from collections.abc import Generator
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.core.settings import settings
from apps.api.models.audit_log import AuditLog


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_hot_food.db"
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


def _register_and_login(client: TestClient, email: str) -> str:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_create_hot_food_demand_input_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/hot-food/demand-inputs",
        json={
            "store_id": "store-001",
            "item_id": "item-123",
            "ts": "2026-02-20T12:00:00",
            "units_sold": 14,
        },
    )
    assert response.status_code == 401


def test_list_hot_food_demand_inputs_requires_auth(client: TestClient) -> None:
    response = client.get(
        "/api/v1/hot-food/demand-inputs",
        params={"store_id": "store-001"},
    )
    assert response.status_code == 401


def test_create_and_list_hot_food_demand_inputs_are_tenant_scoped(client: TestClient) -> None:
    token_a = _register_and_login(client, f"user-a-{uuid.uuid4()}@example.com")
    token_b = _register_and_login(client, f"user-b-{uuid.uuid4()}@example.com")

    response_a = client.post(
        "/api/v1/hot-food/demand-inputs",
        json={
            "store_id": "store-001",
            "item_id": "item-a",
            "ts": "2026-02-20T10:00:00",
            "units_sold": 10,
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response_a.status_code == 201

    response_b = client.post(
        "/api/v1/hot-food/demand-inputs",
        json={
            "store_id": "store-001",
            "item_id": "item-b",
            "ts": "2026-02-20T11:00:00",
            "units_sold": 12,
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response_b.status_code == 201

    list_a = client.get(
        "/api/v1/hot-food/demand-inputs",
        params={"store_id": "store-001", "limit": 10},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    body_a = list_a.json()
    assert list_a.status_code == 200
    assert len(body_a) == 1
    assert body_a[0]["item_id"] == "item-a"

    list_b = client.get(
        "/api/v1/hot-food/demand-inputs",
        params={"store_id": "store-001", "limit": 10},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    body_b = list_b.json()
    assert list_b.status_code == 200
    assert len(body_b) == 1
    assert body_b[0]["item_id"] == "item-b"


def test_create_hot_food_demand_input_writes_audit_log(
    client: TestClient,
    test_session_local,
) -> None:
    email = f"audit-{uuid.uuid4()}@example.com"
    token = _register_and_login(client, email)

    create_response = client.post(
        "/api/v1/hot-food/demand-inputs",
        json={
            "store_id": "store-001",
            "item_id": "item-audit",
            "ts": "2026-02-20T12:00:00",
            "units_sold": 14,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = create_response.json()
    assert create_response.status_code == 201

    db = test_session_local()
    try:
        logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc())).all()
        assert len(logs) == 1
        assert logs[0].action == "create"
        assert logs[0].entity_type == "hot_food_demand_input"
        assert logs[0].entity_id == str(body["id"])
    finally:
        db.close()


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED,
    reason="Rate limiting disabled for test run",
)
def test_demand_input_create_rate_limit(client: TestClient) -> None:
    token = _register_and_login(client, f"ratelimit-{uuid.uuid4()}@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    last_response = None
    for i in range(51):
        last_response = client.post(
            "/api/v1/hot-food/demand-inputs",
            json={
                "store_id": "store-rate",
                "item_id": f"item-{i}",
                "ts": "2026-02-20T12:00:00",
                "units_sold": 1,
            },
            headers=headers,
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert last_response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
