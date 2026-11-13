import uuid

from pydantic import BaseModel, Field


class CountLineInput(BaseModel):
    product_id: uuid.UUID
    counted_qty: int = Field(ge=0)


class StockCountCommit(BaseModel):
    location_id: uuid.UUID
    note: str | None = Field(default=None, max_length=255)
    lines: list[CountLineInput] = Field(min_length=1)


class CountReviewLine(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    system_qty: int
    counted_qty: int
    variance: int


class StockCountResult(BaseModel):
    location_id: uuid.UUID
    location_name: str
    lines: list[CountReviewLine]