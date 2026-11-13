import uuid
from datetime import datetime

from pydantic import BaseModel


class StockMovementRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    product_id: uuid.UUID
    product_name: str
    sku: str
    location_id: uuid.UUID | None = None
    location_name: str
    quantity_change: int  # + in / - out
    movement_type: str    # count | receive | sale | transfer_in | transfer_out | adjustment
    reference: str | None = None
    note: str | None = None
    created_by_name: str | None = None