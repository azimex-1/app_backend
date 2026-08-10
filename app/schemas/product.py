import uuid

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    # SKU + name are generated server-side (name optional to override).
    manufacturer_code: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=64)

    price_minor: int = Field(ge=0)  # selling price
    selling_currency: str = Field(default="GMD", max_length=3)
    cost_price_minor: int | None = Field(default=None, ge=0)
    cost_currency: str | None = Field(default=None, max_length=3)

    reorder_level: int = Field(default=0, ge=0)
    available_for_sale: bool = True
    track_stock: bool = True
    unit: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=500)


class ProductUpdate(BaseModel):
    # Partial update — only sent fields change. SKU stays fixed once created.
    name: str | None = Field(default=None, max_length=255)
    manufacturer_code: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=64)
    price_minor: int | None = Field(default=None, ge=0)
    selling_currency: str | None = Field(default=None, max_length=3)
    cost_price_minor: int | None = Field(default=None, ge=0)
    cost_currency: str | None = Field(default=None, max_length=3)
    quantity: int | None = Field(default=None, ge=0)  # interim manual adjustment
    reorder_level: int | None = Field(default=None, ge=0)
    available_for_sale: bool | None = None
    track_stock: bool | None = None
    is_active: bool | None = None
    unit: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=500)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sku: str
    manufacturer_code: str | None
    barcode: str | None
    brand: str | None
    category: str | None
    price_minor: int
    selling_currency: str
    cost_price_minor: int | None
    cost_currency: str | None
    quantity: int
    reorder_level: int
    available_for_sale: bool
    track_stock: bool
    is_active: bool
    unit: str | None
    description: str | None
    image_url: str | None