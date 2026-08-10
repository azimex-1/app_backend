import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.permission import PermissionRead


class RoleBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)


class RoleCreate(RoleBase):
    permission_ids: list[uuid.UUID] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    permission_ids: list[uuid.UUID] | None = None


class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    permissions: list[PermissionRead] = []
