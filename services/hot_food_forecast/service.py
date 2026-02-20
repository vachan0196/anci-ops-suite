def forecast_hot_food(store_id: str, horizon_days: int) -> dict:
    return {
        "store_id": store_id,
        "horizon_days": horizon_days,
        "forecast": [],
        "model": "stub",
    }
