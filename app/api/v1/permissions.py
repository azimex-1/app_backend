from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.permission import Permission
from app.schemas.permission import PermissionRead

router = APIRouter()


@router.get("", response_model=list[PermissionRead])
async def list_permissions(
    db: DbSession,
    _=Depends(require_permission("role.manage")),
) -> list[Permission]:
    result = await db.scalars(select(Permission).order_by(Permission.code))
    return list(result.all())
