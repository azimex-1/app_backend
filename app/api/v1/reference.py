import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.models.reference import Brand, Category, Unit
from app.schemas.reference import ReferenceCreate, ReferenceRead


def _make_reference_router(
    model,
    *,
    view_permission: str = "inventory.view",
    manage_permission: str = "inventory.manage",
) -> APIRouter:
    """Builds identical list/create/delete routes for a name-only table.
    Permissions are configurable so POS-facing lists (e.g. payment types)
    can be read by cashiers without an inventory permission."""
    key = model.__name__.lower()
    router = APIRouter()

    @router.get("", response_model=list[ReferenceRead], operation_id=f"list_{key}")
    async def list_items(db: DbSession, _=Depends(require_permission(view_permission))):
        result = await db.scalars(select(model).order_by(model.name))
        return list(result.all())

    @router.post(
        "",
        response_model=ReferenceRead,
        status_code=status.HTTP_201_CREATED,
        operation_id=f"create_{key}",
    )
    async def create_item(payload: ReferenceCreate, db: DbSession, _=Depends(require_permission(manage_permission))):
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be blank")
        # Case-insensitive dedup: adding an existing name just returns it
        # (idempotent — perfect for add-on-the-fly and the importer).
        existing = await db.scalar(select(model).where(func.lower(model.name) == name.lower()))
        if existing:
            return existing
        obj = model(name=name)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id=f"delete_{key}")
    async def delete_item(item_id: uuid.UUID, db: DbSession, _=Depends(require_permission(manage_permission))):
        obj = await db.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        await db.delete(obj)
        await db.commit()

    return router


brands_router = _make_reference_router(Brand)
categories_router = _make_reference_router(Category)
units_router = _make_reference_router(Unit)