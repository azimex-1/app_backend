import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_permission
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate

router = APIRouter()


async def _load_permissions(db: DbSession, ids: list[uuid.UUID]) -> list[Permission]:
    if not ids:
        return []
    result = await db.scalars(select(Permission).where(Permission.id.in_(ids)))
    perms = list(result.all())
    if len(perms) != len(set(ids)):
        raise HTTPException(status_code=400, detail="One or more permission_ids are invalid")
    return perms


async def _get_role_in_org(db: DbSession, role_id: uuid.UUID, org_id: uuid.UUID) -> Role:
    result = await db.scalars(
        select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
    )
    role = result.one_or_none()
    if role is None or role.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.get("", response_model=list[RoleRead])
async def list_roles(user: CurrentUser, db: DbSession) -> list[Role]:
    result = await db.scalars(
        select(Role)
        .where(Role.organization_id == user.organization_id)
        .options(selectinload(Role.permissions))
        .order_by(Role.name)
    )
    return list(result.all())


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("role.manage"))],
) -> Role:
    role = Role(
        organization_id=user.organization_id,
        name=payload.name,
        description=payload.description,
        permissions=await _load_permissions(db, payload.permission_ids),
    )
    db.add(role)
    await db.commit()
    await db.refresh(role, attribute_names=["permissions"])
    return role


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(role_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Role:
    return await _get_role_in_org(db, role_id, user.organization_id)


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("role.manage"))],
) -> Role:
    role = await _get_role_in_org(db, role_id, user.organization_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        role.name = data["name"]
    if "description" in data:
        role.description = data["description"]
    if payload.permission_ids is not None:
        role.permissions = await _load_permissions(db, payload.permission_ids)
    await db.commit()
    await db.refresh(role, attribute_names=["permissions"])
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("role.manage"))],
) -> None:
    role = await _get_role_in_org(db, role_id, user.organization_id)
    await db.delete(role)
    await db.commit()