import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LedgerEntryRead(BaseModel):
    id: uuid.UUID
    entry_type: str
    description: str | None
    debit_minor: int
    credit_minor: int
    reference: str | None
    entry_date: date
    created_at: datetime
    balance_after_minor: int  # running balance up to and including this entry


class CustomerLedgerResponse(BaseModel):
    customer_id: uuid.UUID
    outstanding_minor: int                 # +ve = customer owes us
    credit_enabled: bool
    credit_limit_minor: int
    available_credit_minor: int | None     # limit - outstanding (None if credit disabled)
    entries: list[LedgerEntryRead]         # newest first


class PaymentCreate(BaseModel):
    amount_minor: int = Field(gt=0)
    account_id: uuid.UUID | None = None    # which payment account it landed in
    reference: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    entry_date: date | None = None


class AdjustmentCreate(BaseModel):
    direction: Literal["debit", "credit"]
    amount_minor: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=500)
    entry_date: date | None = None