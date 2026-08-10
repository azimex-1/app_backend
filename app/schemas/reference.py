import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReferenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str