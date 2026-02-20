from fastapi import APIRouter, FastAPI

from apps.api.core.errors import register_exception_handlers
from apps.api.core.logging import configure_logging
from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.session import engine
from apps.api import models  # noqa: F401
from apps.api.routers.health import router as health_router
from apps.api.routers.hot_food import router as hot_food_router

configure_logging()

app = FastAPI(title=settings.APP_NAME)
register_exception_handlers(app)

api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
api_v1_router.include_router(hot_food_router, prefix="/hot-food", tags=["hot-food"])
app.include_router(api_v1_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
