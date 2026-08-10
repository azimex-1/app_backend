import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_permission
from app.models.branch import Branch
from app.models.user import User
from app.schemas.branch import BranchCreate, BranchRead, BranchUpdate

router = APIRouter()


async def _get_branch_in_org(db: DbSession, branch_id: uuid.UUID, org_id: uuid.UUID) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


@router.get("", response_model=list[BranchRead])
async def list_branches(user: CurrentUser, db: DbSession) -> list[Branch]:
    result = await db.scalars(
        select(Branch).where(Branch.organization_id == user.organization_id).order_by(Branch.name)
    )
    return list(result.all())


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("branch.manage"))],
) -> Branch:
    branch = Branch(organization_id=user.organization_id, **payload.model_dump())
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.get("/{branch_id}", response_model=BranchRead)
async def get_branch(branch_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Branch:
    return await _get_branch_in_org(db, branch_id, user.organization_id)


@router.patch("/{branch_id}", response_model=BranchRead)
async def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("branch.manage"))],
) -> Branch:
    branch = await _get_branch_in_org(db, branch_id, user.organization_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    branch_id: uuid.UUID,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("branch.manage"))],
) -> None:
    branch = await _get_branch_in_org(db, branch_id, user.organization_id)
    await db.delete(branch)
    await db.commit()