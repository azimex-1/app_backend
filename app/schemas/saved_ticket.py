import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SavedTicketLine(BaseModel):
    product_id: str
    name: str
    sku: str
    unit_price_minor: int
    quantity: int


class SavedTicketCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    total_minor: int = Field(default=0, ge=0)
    lines: list[SavedTicketLine] = Field(min_length=1)


class SavedTicketSummary(BaseModel):
    id: uuid.UUID
    name: str
    customer_name: str | None
    total_minor: int
    item_count: int
    created_at: datetime


class SavedTicketDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    total_minor: int
    created_at: datetime
    lines: list[SavedTicketLine]