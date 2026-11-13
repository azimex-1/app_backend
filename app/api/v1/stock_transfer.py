import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.location import ItemLocation, Location
from app.models.product import Product
from app.models.user import User
from app.schemas.stock_transfer import StockTransferCreate, StockTransferResult
from app.services.stock import apply_movement, next_priority_for

router = APIRouter()


@router.post("", response_model=StockTransferResult, status_code=201)
async def create_transfer(
    payload: StockTransferCreate,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> StockTransferResult:
    """Move stock from one location to another within this branch.
    Posts two movements (transfer_out at source, transfer_in at destination)
    sharing one reference, and completes instantly."""
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(status_code=400, detail="Source and destination must differ")

    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Item not found")

    src = await db.get(Location, payload.from_location_id)
    if src is None or src.organization_id != current.organization_id:
        raise HTTPException(status_code=404, detail="Source location not found")

    dst = await db.get(Location, payload.to_location_id)
    if dst is None or dst.organization_id != current.organization_id:
        raise HTTPException(status_code=404, detail="Destination location not found")

    # You cannot move stock you don't physically have at the source.
    src_level = await db.scalar(
        select(ItemLocation).where(
            ItemLocation.product_id == payload.product_id,
            ItemLocation.location_id == payload.from_location_id,
        )
    )
    on_hand = src_level.quantity if src_level else 0
    if on_hand < payload.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Only {on_hand} on hand at source; cannot move {payload.quantity}",
        )

    reference = f"TRF-{uuid.uuid4().hex[:8].upper()}"

    out_il = await apply_movement(
        db,
        product_id=payload.product_id,
        location_id=payload.from_location_id,
        quantity_change=-payload.quantity,
        movement_type="transfer_out",
        reference=reference,
        note=payload.note,
        created_by=current.id,
        next_priority=await next_priority_for(db, payload.product_id),
    )
    in_il = await apply_movement(
        db,
        product_id=payload.product_id,
        location_id=payload.to_location_id,
        quantity_change=payload.quantity,
        movement_type="transfer_in",
        reference=reference,
        note=payload.note,
        created_by=current.id,
        next_priority=await next_priority_for(db, payload.product_id),
    )
    await db.commit()
    await db.refresh(out_il)
    await db.refresh(in_il)

    return StockTransferResult(
        product_id=payload.product_id,
        from_location_id=payload.from_location_id,
        to_location_id=payload.to_location_id,
        quantity=payload.quantity,
        reference=reference,
        from_quantity=out_il.quantity,
        to_quantity=in_il.quantity,
    )