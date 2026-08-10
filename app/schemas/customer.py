import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    customer_type: str | None = Field(default=None, max_length=60)
    contact_person: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    tax_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="Active", max_length=30)
    credit_enabled: bool = False
    credit_limit_minor: int = Field(default=0, ge=0)
    payment_terms: str | None = Field(default=None, max_length=30)
    credit_hold_reason: str | None = Field(default=None, max_length=500)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    customer_type: str | None = Field(default=None, max_length=60)
    contact_person: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    tax_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, max_length=30)
    is_archived: bool | None = None
    credit_enabled: bool | None = None
    credit_limit_minor: int | None = Field(default=None, ge=0)
    payment_terms: str | None = Field(default=None, max_length=30)
    credit_hold_reason: str | None = Field(default=None, max_length=500)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    customer_type: str | None
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    tax_number: str | None
    notes: str | None
    status: str
    is_archived: bool
    credit_enabled: bool
    credit_limit_minor: int
    payment_terms: str | None
    credit_hold_reason: str | None
    created_at: datetime