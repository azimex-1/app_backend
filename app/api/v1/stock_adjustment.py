from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.location import ItemLocation, Location
from app.models.product import Product
from app.models.user import User
from app.schemas.stock_adjustment import StockAdjustmentCreate, StockAdjustmentResult
from app.services.stock import apply_movement, next_priority_for

router = APIRouter()


@router.post("", response_model=StockAdjustmentResult, status_code=201)
async def create_adjustment(
    payload: StockAdjustmentCreate,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> StockAdjustmentResult:
    """Manual stock adjustment — damage, write-off, found, correction.
    Posts an 'adjustment' movement and updates the (product, location) level."""
    if payload.quantity_change == 0:
        raise HTTPException(status_code=400, detail="Quantity change cannot be zero")

    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Item not found")

    location = await db.get(Location, payload.location_id)
    if location is None or location.organization_id != current.organization_id:
        raise HTTPException(status_code=404, detail="Location not found")

    il = await apply_movement(
        db,
        product_id=payload.product_id,
        location_id=payload.location_id,
        quantity_change=payload.quantity_change,
        movement_type="adjustment",
        reference=payload.reason,
        note=payload.note,
        created_by=current.id,
        next_priority=await next_priority_for(db, payload.product_id),
    )
    await db.commit()
    await db.refresh(il)
    return StockAdjustmentResult(
        product_id=payload.product_id,
        location_id=payload.location_id,
        quantity_change=payload.quantity_change,
        new_quantity=il.quantity,
    )