from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_permission
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationRead, OrganizationUpdate

router = APIRouter()


@router.get("/current", response_model=OrganizationRead)
async def read_current_organization(user: CurrentUser, db: DbSession) -> Organization:
    return await db.get(Organization, user.organization_id)


@router.patch("/current", response_model=OrganizationRead)
async def update_current_organization(
    payload: OrganizationUpdate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("organization.manage"))],
) -> Organization:
    org = await db.get(Organization, user.organization_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return org