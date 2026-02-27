import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import get_current_tenant_id, get_current_user
from apps.api.core.rate_limit import limiter
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.hot_food import HotFoodDemandInput
from apps.api.models.user import User
from apps.api.schemas.hot_food import HotFoodDemandIn, HotFoodDemandOut
from services.hot_food_forecast.service import forecast_hot_food

router = APIRouter()


@router.get("/forecast")
def hot_food_forecast(store_id: str, horizon_days: int) -> dict:
    return forecast_hot_food(store_id=store_id, horizon_days=horizon_days)


@router.post("/demand-inputs", response_model=HotFoodDemandOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_DEMAND_INPUT_CREATE)
def create_hot_food_demand_input(
    request: Request,
    payload: HotFoodDemandIn,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> HotFoodDemandOut:
    demand_input = HotFoodDemandInput(**payload.model_dump(), tenant_id=tenant_id)
    db.add(demand_input)
    db.flush()

    audit_log = AuditLog(
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="create",
        entity_type="hot_food_demand_input",
        entity_id=str(demand_input.id),
    )
    db.add(audit_log)
    db.commit()
    db.refresh(demand_input)
    return HotFoodDemandOut.model_validate(demand_input)


@router.get("/demand-inputs", response_model=list[HotFoodDemandOut])
def list_hot_food_demand_inputs(
    store_id: str,
    limit: int = 100,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> list[HotFoodDemandOut]:
    query = (
        select(HotFoodDemandInput)
        .where(
            HotFoodDemandInput.tenant_id == tenant_id,
            HotFoodDemandInput.store_id == store_id,
        )
        .order_by(HotFoodDemandInput.ts.desc())
        .limit(limit)
    )
    records = db.scalars(query).all()
    return [HotFoodDemandOut.model_validate(record) for record in records]
