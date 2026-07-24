import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class _WorkAreaLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("label must not be blank")
        return normalized


class WorkAreaCreate(_WorkAreaLabel):
    pass


class WorkAreaPatch(_WorkAreaLabel):
    pass


class WorkAreaRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    label: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
