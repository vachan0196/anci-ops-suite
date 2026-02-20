from fastapi.testclient import TestClient

from apps.api.core.settings import settings
from apps.api.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "env": settings.ENV,
    }


def test_hot_food_forecast() -> None:
    response = client.get(
        "/api/v1/hot-food/forecast",
        params={"store_id": "store-001", "horizon_days": 7},
    )

    assert response.status_code == 200
    assert response.json() == {
        "store_id": "store-001",
        "horizon_days": 7,
        "forecast": [],
        "model": "stub",
    }


def test_hot_food_forecast_validation_error() -> None:
    response = client.get(
        "/api/v1/hot-food/forecast",
        params={"store_id": "store-001"},
    )

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]
