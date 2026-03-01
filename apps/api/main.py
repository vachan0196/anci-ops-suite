import uuid

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.errors import register_exception_handlers
from apps.api.core.logging import configure_logging, request_id_ctx_var
from apps.api.core.rate_limit import limiter, rate_limit_exceeded_handler
from apps.api.core.settings import settings
from apps.api.routers.availability import router as availability_router
from apps.api.routers.auth import router as auth_router
from apps.api.routers.health import router as health_router
from apps.api.routers.hot_food import router as hot_food_router
from apps.api.routers.hour_targets import router as hour_targets_router
from apps.api.routers.shift_requests import router as shift_requests_router
from apps.api.routers.shifts import router as shifts_router
from apps.api.routers.staff import router as staff_router
from apps.api.routers.stores import router as stores_router
from slowapi.errors import RateLimitExceeded

configure_logging()

app = FastAPI(title=settings.APP_NAME)
register_exception_handlers(app)
if settings.RATE_LIMIT_ENABLED:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    token = request_id_ctx_var.set(request_id)
    try:
        return await call_next(request)
    finally:
        request_id_ctx_var.reset(token)

api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
api_v1_router.include_router(hot_food_router, prefix="/hot-food", tags=["hot-food"])
api_v1_router.include_router(stores_router, prefix="/stores", tags=["stores"])
api_v1_router.include_router(staff_router, prefix="/staff", tags=["staff"])
api_v1_router.include_router(shifts_router, prefix="/shifts", tags=["shifts"])
api_v1_router.include_router(shift_requests_router, prefix="/shift-requests", tags=["shift-requests"])
api_v1_router.include_router(availability_router, prefix="/availability", tags=["availability"])
api_v1_router.include_router(hour_targets_router, prefix="/hour-targets", tags=["hour-targets"])
app.include_router(api_v1_router)
