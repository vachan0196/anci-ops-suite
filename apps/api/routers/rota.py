from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.shift import Shift
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.rota import GenerateWeekRequest, GenerateWeekResponse

router = APIRouter()


def _week_bounds(week_start) -> tuple[datetime, datetime]:
    start_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=7)
    return start_at, end_at


def _get_store_or_404(db: Session, *, tenant_id, store_id) -> Store:
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )
    return store


@router.post("/generate-week", response_model=GenerateWeekResponse)
def generate_week_shifts(
    payload: GenerateWeekRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> GenerateWeekResponse:
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=payload.store_id)

    week_start_at, week_end_at = _week_bounds(payload.week_start)

    existing_shift = db.scalar(
        select(Shift).where(
            Shift.tenant_id == membership.tenant_id,
            Shift.store_id == payload.store_id,
            Shift.start_at >= week_start_at,
            Shift.start_at < week_end_at,
        )
    )
    if existing_shift is not None:
        raise ApiError(
            status_code=409,
            code="ROTA_WEEK_ALREADY_EXISTS",
            message="Shifts already exist for this store and week",
        )

    templates = db.scalars(
        select(CoverageTemplate).where(
            CoverageTemplate.tenant_id == membership.tenant_id,
            CoverageTemplate.store_id == payload.store_id,
            CoverageTemplate.is_active.is_(True),
        )
    ).all()

    created_count = 0
    for day_offset in range(7):
        current_date = payload.week_start + timedelta(days=day_offset)
        current_day_of_week = current_date.weekday()

        day_templates = [template for template in templates if template.day_of_week == current_day_of_week]
        for template in day_templates:
            start_at = datetime.combine(current_date, template.start_time, tzinfo=timezone.utc)
            end_at = datetime.combine(current_date, template.end_time, tzinfo=timezone.utc)

            for _ in range(template.required_headcount):
                db.add(
                    Shift(
                        tenant_id=membership.tenant_id,
                        store_id=payload.store_id,
                        assigned_user_id=None,
                        start_at=start_at,
                        end_at=end_at,
                        status="scheduled",
                        published_at=None,
                        published_by_user_id=None,
                    )
                )
                created_count += 1

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="generate_week",
            entity_type="shift",
            entity_id=str(payload.store_id),
        )
    )
    db.commit()

    return GenerateWeekResponse(created_count=created_count)
