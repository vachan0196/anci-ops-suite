from fastapi import APIRouter

from services.hot_food_forecast.service import forecast_hot_food

router = APIRouter()


@router.get("/forecast")
def hot_food_forecast(store_id: str, horizon_days: int) -> dict:
    return forecast_hot_food(store_id=store_id, horizon_days=horizon_days)
