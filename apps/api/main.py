from fastapi import APIRouter, FastAPI

from services.hot_food_forecast.service import forecast_hot_food

app = FastAPI()
hot_food_router = APIRouter(prefix="/hot-food", tags=["hot-food"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@hot_food_router.get("/forecast")
def hot_food_forecast(store_id: str, horizon_days: int) -> dict:
    return forecast_hot_food(store_id=store_id, horizon_days=horizon_days)


app.include_router(hot_food_router)
