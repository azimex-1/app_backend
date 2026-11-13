import uuid

from pydantic import BaseModel, ConfigDict, Field


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str | None
    description: str | None
    is_active: bool


class LocationWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class ItemLocationRead(BaseModel):
    location_id: uuid.UUID
    location_name: str
    priority: int
    quantity: int


class ItemLocationSet(BaseModel):
    location_id: uuid.UUID
    priority: int = Field(ge=0)
    quantity: int = Field(default=0, ge=0)


class ItemLocationsUpdate(BaseModel):
    """Replace the full ordered list of locations for an item."""
    locations: list[ItemLocationSet] = Field(default_factory=list)