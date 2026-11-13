import uuid

from pydantic import BaseModel, Field


class StockTransferCreate(BaseModel):
    product_id: uuid.UUID
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    quantity: int = Field(gt=0, description="Units to move. Must be > 0.")
    note: str | None = Field(default=None, max_length=255)


class StockTransferResult(BaseModel):
    product_id: uuid.UUID
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    quantity: int
    reference: str
    from_quantity: int  # on-hand at source after the move
    to_quantity: int     # on-hand at destination after the move