import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionOpen(BaseModel):
    opening_float_minor: int = Field(default=0, ge=0)
    opened_by: str | None = None


class SessionClose(BaseModel):
    counted_cash_minor: int = Field(ge=0)
    note: str | None = None


class CashMovementCreate(BaseModel):
    direction: str = Field(pattern="^(in|out)$")
    amount_minor: int = Field(gt=0)
    reason: str | None = None


class CashMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    direction: str
    amount_minor: int
    reason: str | None
    created_at: datetime


class PosSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    opened_at: datetime
    opening_float_minor: int
    opened_by: str | None
    status: str
    closed_at: datetime | None
    expected_cash_minor: int | None
    counted_cash_minor: int | None
    difference_minor: int | None
    close_note: str | None


class AccountBreakdown(BaseModel):
    account_name: str
    currency: str
    count: int
    amount_minor: int          # original tender total
    dalasi_value_minor: int    # converted to GMD


class SessionReport(BaseModel):
    session: PosSessionRead
    by_account: list[AccountBreakdown]
    total_sales_minor: int      # all payments, dalasi
    cash_sales_minor: int       # cash-type payments, dalasi
    refunds_by_account: list[AccountBreakdown]
    total_refunds_minor: int    # all refunds, dalasi
    cash_refunds_minor: int     # cash-type refunds, dalasi
    cash_in_minor: int
    cash_out_minor: int
    expected_cash_minor: int    # opening + cash sales - cash refunds + cash_in - cash_out
    counted_cash_minor: int | None
    difference_minor: int | None
    movements: list[CashMovementRead]