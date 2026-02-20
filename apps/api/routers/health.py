from fastapi import APIRouter

from apps.api.core.settings import settings

router = APIRouter()


@router.get("")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "env": settings.ENV,
    }
