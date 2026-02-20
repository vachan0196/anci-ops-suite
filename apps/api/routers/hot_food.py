from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db.deps import get_db
from apps.api.models.hot_food import HotFoodDemandInput
from apps.api.schemas.hot_food import HotFoodDemandIn, HotFoodDemandOut
from services.hot_food_forecast.service import forecast_hot_food

router = APIRouter()


@router.get("/forecast")
def hot_food_forecast(store_id: str, horizon_days: int) -> dict:
    return forecast_hot_food(store_id=store_id, horizon_days=horizon_days)


@router.post("/demand-inputs", response_model=HotFoodDemandOut, status_code=201)
def create_hot_food_demand_input(
    payload: HotFoodDemandIn,
    db: Session = Depends(get_db),
) -> HotFoodDemandOut:
    demand_input = HotFoodDemandInput(**payload.model_dump())
    db.add(demand_input)
    db.commit()
    db.refresh(demand_input)
    return HotFoodDemandOut.model_validate(demand_input)


@router.get("/demand-inputs", response_model=list[HotFoodDemandOut])
def list_hot_food_demand_inputs(
    store_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[HotFoodDemandOut]:
    query = (
        select(HotFoodDemandInput)
        .where(HotFoodDemandInput.store_id == store_id)
        .order_by(HotFoodDemandInput.ts.desc())
        .limit(limit)
    )
    records = db.scalars(query).all()
    return [HotFoodDemandOut.model_validate(record) for record in records]
