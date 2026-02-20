from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    test_session_local = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=test_engine)

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
    test_engine.dispose()


def test_create_hot_food_demand_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/hot-food/demand-inputs",
        json={
            "store_id": "store-001",
            "item_id": "item-123",
            "ts": "2026-02-20T12:00:00",
            "units_sold": 14,
        },
    )

    body = response.json()
    assert response.status_code == 201
    assert body["id"] > 0
    assert body["store_id"] == "store-001"
    assert body["item_id"] == "item-123"
    assert body["ts"].startswith("2026-02-20T12:00:00")
    assert body["units_sold"] == 14


def test_list_hot_food_demand_inputs(client: TestClient) -> None:
    payloads = [
        {
            "store_id": "store-001",
            "item_id": "item-1",
            "ts": "2026-02-20T10:00:00",
            "units_sold": 10,
        },
        {
            "store_id": "store-001",
            "item_id": "item-2",
            "ts": "2026-02-20T11:00:00",
            "units_sold": 12,
        },
        {
            "store_id": "store-002",
            "item_id": "item-3",
            "ts": "2026-02-20T11:30:00",
            "units_sold": 8,
        },
    ]
    for payload in payloads:
        create_response = client.post("/api/v1/hot-food/demand-inputs", json=payload)
        assert create_response.status_code == 201

    response = client.get(
        "/api/v1/hot-food/demand-inputs",
        params={"store_id": "store-001", "limit": 10},
    )

    body = response.json()
    assert response.status_code == 200
    assert len(body) == 2
    assert body[0]["item_id"] == "item-2"
    assert body[1]["item_id"] == "item-1"
