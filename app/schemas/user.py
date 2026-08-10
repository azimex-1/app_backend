import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.branch import BranchRead
from app.schemas.role import RoleRead


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)
    role_ids: list[uuid.UUID] = []
    branch_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
    role_ids: list[uuid.UUID] | None = None
    branch_ids: list[uuid.UUID] | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    is_owner: bool


class UserDetail(UserRead):
    roles: list[RoleRead] = []
    branches: list[BranchRead] = []
