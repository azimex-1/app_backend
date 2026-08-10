import uuid

from pydantic import BaseModel, ConfigDict, Field


class BranchBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    address: str | None = Field(default=None, max_length=500)


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class BranchRead(BranchBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
