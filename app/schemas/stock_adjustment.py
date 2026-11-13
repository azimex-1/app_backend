import uuid

from pydantic import BaseModel, ConfigDict, Field


class StockAdjustmentCreate(BaseModel):
    product_id: uuid.UUID
    location_id: uuid.UUID
    # Positive = add stock, negative = remove (damage, write-off, correction).
    quantity_change: int = Field(description="Signed quantity: +add / -remove. Cannot be 0.")
    reason: str = Field(min_length=1, max_length=60)  # Damage, Write-off, Found, Correction, Other
    note: str | None = Field(default=None, max_length=255)


class StockAdjustmentResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: uuid.UUID
    location_id: uuid.UUID
    quantity_change: int
    new_quantity: int