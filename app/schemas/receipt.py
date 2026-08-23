import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Create ──
class ReceiptItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0)
    unit_price_minor: int = Field(ge=0)


class ReceiptPaymentCreate(BaseModel):
    account_id: uuid.UUID
    amount_minor: int = Field(ge=0)          # original tender, in the account's currency
    dalasi_value_minor: int = Field(ge=0)    # dalasi value that counts toward the total


class ReceiptCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    customer_name: str = Field(default="Walk-in Customer", max_length=255)
    salesperson: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    discount_minor: int = Field(default=0, ge=0)
    tax_minor: int = Field(default=0, ge=0)
    total_minor: int | None = Field(default=None, ge=0)
    credit_minor: int = Field(default=0, ge=0)   # amount intentionally put on the customer's account
    items: list[ReceiptItemCreate] = Field(min_length=1)
    payments: list[ReceiptPaymentCreate] = Field(default_factory=list)


# ── Read ──
class ReceiptItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str
    sku: str
    unit_price_minor: int
    quantity: int
    line_total_minor: int


class ReceiptPaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID | None
    account_name: str
    amount_minor: int
    currency: str
    dalasi_value_minor: int


class ReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_number: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    salesperson: str | None
    notes: str | None
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    status: str
    created_at: datetime
    items: list[ReceiptItemRead]
    payments: list[ReceiptPaymentRead]


class ReceiptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_number: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    salesperson: str | None
    total_minor: int
    status: str
    created_at: datetime


class DailyAccountBreakdown(BaseModel):
    account_name: str
    currency: str
    count: int
    amount_minor: int          # original tender summed (in the account's currency)
    dalasi_value_minor: int    # dalasi value summed


class DailySummary(BaseModel):
    date_from: date
    date_to: date
    receipt_count: int
    total_minor: int           # sum of receipt totals (dalasi)
    by_account: list[DailyAccountBreakdown]