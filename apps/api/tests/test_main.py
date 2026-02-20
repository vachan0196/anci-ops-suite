from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hot_food_forecast() -> None:
    response = client.get(
        "/hot-food/forecast",
        params={"store_id": "store-001", "horizon_days": 7},
    )

    assert response.status_code == 200
    assert response.json() == {
        "store_id": "store-001",
        "horizon_days": 7,
        "forecast": [],
        "model": "stub",
    }
