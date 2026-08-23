import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RefundableLine(BaseModel):
    receipt_item_id: uuid.UUID
    product_name: str
    sku: str
    unit_price_minor: int
    sold_qty: int
    refunded_qty: int
    returnable_qty: int


class RefundableReceipt(BaseModel):
    receipt_id: uuid.UUID
    receipt_number: str
    status: str
    customer_name: str | None
    suggested_account_id: uuid.UUID | None  # the sale's payment method (default)
    lines: list[RefundableLine]


class RefundLineInput(BaseModel):
    receipt_item_id: uuid.UUID
    quantity: int = Field(gt=0)


class RefundCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=60)
    reason_detail: str | None = Field(default=None, max_length=500)
    account_id: uuid.UUID
    salesperson: str | None = None
    lines: list[RefundLineInput] = Field(min_length=1)


class RefundLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    sku: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int


class RefundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    refund_number: str
    receipt_id: uuid.UUID
    reason: str
    reason_detail: str | None
    account_name: str
    currency: str
    total_minor: int
    salesperson: str | None
    created_at: datetime
    lines: list[RefundLineRead]