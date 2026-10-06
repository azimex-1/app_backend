from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.core.permission_catalog import PERMISSION_CATALOG
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


@router.post("/seed", response_model=list[PermissionRead])
async def seed_permissions(
    db: DbSession,
    _=Depends(require_permission("role.manage")),
) -> list[Permission]:
    """Idempotent — inserts any catalog codes not already in the table.
    Updates the description if it changed. Never deletes."""
    existing = {p.code: p for p in (await db.scalars(select(Permission))).all()}
    for code, description in PERMISSION_CATALOG:
        if code in existing:
            if existing[code].description != description:
                existing[code].description = description
        else:
            db.add(Permission(code=code, description=description))
    await db.commit()
    result = await db.scalars(select(Permission).order_by(Permission.code))
    return list(result.all())