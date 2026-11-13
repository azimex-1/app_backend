import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from app.api.deps import DbSession, require_permission
from app.models.location import Location
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.stock_ledger import StockMovementRead

router = APIRouter()


@router.get("", response_model=list[StockMovementRead])
async def list_movements(
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.view"))],
    product_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    movement_type: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[StockMovementRead]:
    """Read-only stock ledger — every movement, newest first.
    Scoped to the caller's organization via the location."""
    stmt = (
        select(
            StockMovement,
            Product.name,
            Product.sku,
            Location.name.label("location_name"),
            User.full_name,
        )
        .join(Product, Product.id == StockMovement.product_id)
        .outerjoin(Location, Location.id == StockMovement.location_id)
        .outerjoin(User, User.id == StockMovement.created_by)
        .where(
            or_(
                Location.organization_id == current.organization_id,
                StockMovement.location_id.is_(None),  # store-level movements (e.g. POS sales)
            )
        )
    )

    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if location_id is not None:
        stmt = stmt.where(StockMovement.location_id == location_id)
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)

    stmt = stmt.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset)

    rows = (await db.execute(stmt)).all()
    return [
        StockMovementRead(
            id=m.id,
            created_at=m.created_at,
            product_id=m.product_id,
            product_name=p_name,
            sku=sku,
            location_id=m.location_id,
            location_name=loc_name or "Store-wide",
            quantity_change=m.quantity_change,
            movement_type=m.movement_type,
            reference=m.reference,
            note=m.note,
            created_by_name=full_name,
        )
        for (m, p_name, sku, loc_name, full_name) in rows
    ]