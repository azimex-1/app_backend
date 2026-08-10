import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_permission
from app.core.security import hash_password
from app.models.branch import Branch
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserDetail, UserRead, UserUpdate

router = APIRouter()


async def _load_roles(db: DbSession, ids: list[uuid.UUID], org_id: uuid.UUID) -> list[Role]:
    if not ids:
        return []
    result = await db.scalars(
        select(Role).where(Role.id.in_(ids), Role.organization_id == org_id)
    )
    roles = list(result.all())
    if len(roles) != len(set(ids)):
        raise HTTPException(status_code=400, detail="One or more role_ids are invalid")
    return roles


async def _load_branches(db: DbSession, ids: list[uuid.UUID], org_id: uuid.UUID) -> list[Branch]:
    if not ids:
        return []
    result = await db.scalars(
        select(Branch).where(Branch.id.in_(ids), Branch.organization_id == org_id)
    )
    branches = list(result.all())
    if len(branches) != len(set(ids)):
        raise HTTPException(status_code=400, detail="One or more branch_ids are invalid")
    return branches


async def _get_user_detail(db: DbSession, user_id: uuid.UUID, org_id: uuid.UUID) -> User:
    result = await db.scalars(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),
            selectinload(User.branches),
        )
    )
    user = result.one_or_none()
    if user is None or user.organization_id != org_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=list[UserRead])
async def list_users(user: CurrentUser, db: DbSession) -> list[User]:
    result = await db.scalars(
        select(User).where(User.organization_id == user.organization_id).order_by(User.full_name)
    )
    return list(result.all())


@router.post("", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("user.manage"))],
) -> User:
    if await db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        organization_id=current.organization_id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        roles=await _load_roles(db, payload.role_ids, current.organization_id),
        branches=await _load_branches(db, payload.branch_ids, current.organization_id),
    )
    db.add(new_user)
    await db.commit()
    return await _get_user_detail(db, new_user.id, current.organization_id)


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(user_id: uuid.UUID, current: CurrentUser, db: DbSession) -> User:
    return await _get_user_detail(db, user_id, current.organization_id)


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("user.manage"))],
) -> User:
    target = await _get_user_detail(db, user_id, current.organization_id)
    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data:
        target.full_name = data["full_name"]
    if "is_active" in data:
        target.is_active = data["is_active"]
    if payload.role_ids is not None:
        target.roles = await _load_roles(db, payload.role_ids, current.organization_id)
    if payload.branch_ids is not None:
        target.branches = await _load_branches(db, payload.branch_ids, current.organization_id)
    await db.commit()
    return await _get_user_detail(db, user_id, current.organization_id)