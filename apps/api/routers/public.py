from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.core.errors import ApiError
from apps.api.core.rate_limit import limiter
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.store import Store
from apps.api.schemas.store import PublicSiteLookupResponse

router = APIRouter()


@router.get("/sites/lookup", response_model=PublicSiteLookupResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def lookup_site_by_code(
    request: Request,
    code: str,
    db: Session = Depends(get_db),
) -> PublicSiteLookupResponse:
    normalized_code = code.strip()
    if not normalized_code:
        raise ApiError(
            status_code=404,
            code="SITE_LOOKUP_NOT_FOUND",
            message="Site not found",
        )

    matches = db.scalars(
        select(Store)
        .where(
            Store.code.is_not(None),
            Store.is_active.is_(True),
            func.lower(Store.code) == normalized_code.lower(),
        )
        .order_by(Store.created_at.asc())
        .limit(2)
    ).all()

    if not matches:
        raise ApiError(
            status_code=404,
            code="SITE_LOOKUP_NOT_FOUND",
            message="Site not found",
        )

    if len(matches) > 1:
        raise ApiError(
            status_code=409,
            code="SITE_LOOKUP_AMBIGUOUS",
            message="Multiple active sites use this code. Please contact your manager.",
        )

    site = matches[0]
    return PublicSiteLookupResponse(
        site_id=site.id,
        site_code=site.code or normalized_code,
        site_name=site.name,
    )
