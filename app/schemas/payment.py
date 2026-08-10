import uuid

from pydantic import BaseModel, ConfigDict, Field


class PaymentAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    type_id: uuid.UUID
    currency: str = Field(default="GMD", max_length=3)
    account_number: str | None = Field(default=None, max_length=120)
    is_active: bool = True


class PaymentAccountUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    type_id: uuid.UUID | None = None
    currency: str | None = Field(default=None, max_length=3)
    account_number: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class PaymentAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type_id: uuid.UUID
    type_name: str | None
    currency: str
    account_number: str | None
    is_active: bool