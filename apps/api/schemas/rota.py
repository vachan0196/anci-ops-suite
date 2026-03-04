import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class GenerateWeekRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    week_start: date


class GenerateWeekResponse(BaseModel):
    created_count: int
