from fastapi import FastAPI

from apps.api.routers.health import router as health_router
from apps.api.routers.hot_food import router as hot_food_router

app = FastAPI()
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(hot_food_router, prefix="/hot-food", tags=["hot-food"])
