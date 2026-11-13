import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_permission
from app.models.location import ItemLocation, Location
from app.models.product import Product
from app.models.user import User
from app.schemas.stock_count import CountReviewLine, StockCountCommit, StockCountResult
from app.services.stock import apply_movement, next_priority_for

router = APIRouter()


async def _system_qty(db: DbSession, product_id: uuid.UUID, location_id: uuid.UUID) -> int:
    il = await db.scalar(
        select(ItemLocation).where(
            ItemLocation.product_id == product_id, ItemLocation.location_id == location_id
        )
    )
    return il.quantity if il else 0


@router.post("/preview", response_model=StockCountResult)
async def preview_count(
    payload: StockCountCommit,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> StockCountResult:
    """Step 1 of a blind count: returns system vs counted vs variance for review.
    Posts NOTHING. The frontend shows this, then calls /commit to apply."""
    location = await db.get(Location, payload.location_id)
    if location is None or location.organization_id != current.organization_id:
        raise HTTPException(status_code=404, detail="Location not found")

    product_ids = [l.product_id for l in payload.lines]
    products = {
        p.id: p
        for p in (await db.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
    }
    missing = [str(pid) for pid in product_ids if pid not in products]
    if missing:
        raise HTTPException(status_code=400, detail="One or more items are invalid")

    review: list[CountReviewLine] = []
    for line in payload.lines:
        system = await _system_qty(db, line.product_id, payload.location_id)
        product = products[line.product_id]
        review.append(
            CountReviewLine(
                product_id=line.product_id,
                product_name=product.name,
                sku=product.sku,
                system_qty=system,
                counted_qty=line.counted_qty,
                variance=line.counted_qty - system,
            )
        )
    return StockCountResult(location_id=location.id, location_name=location.name, lines=review)


@router.post("/commit", response_model=StockCountResult)
async def commit_count(
    payload: StockCountCommit,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> StockCountResult:
    """Blind count, PARTIAL update: only the submitted items are adjusted.
    For each line: posts a 'count' movement for (counted - system) and sets the
    level to counted. Creates the item-location link if new. Returns the review
    (system vs counted vs variance) for the confirmation screen."""
    location = await db.get(Location, payload.location_id)
    if location is None or location.organization_id != current.organization_id:
        raise HTTPException(status_code=404, detail="Location not found")

    # Validate products exist.
    product_ids = [l.product_id for l in payload.lines]
    products = {
        p.id: p
        for p in (await db.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
    }
    missing = [str(pid) for pid in product_ids if pid not in products]
    if missing:
        raise HTTPException(status_code=400, detail="One or more items are invalid")

    review: list[CountReviewLine] = []
    for line in payload.lines:
        system = await _system_qty(db, line.product_id, payload.location_id)
        delta = line.counted_qty - system
        if delta != 0:
            await apply_movement(
                db,
                product_id=line.product_id,
                location_id=payload.location_id,
                quantity_change=delta,
                movement_type="count",
                reference="stock-count",
                note=payload.note,
                created_by=current.id,
                next_priority=await next_priority_for(db, line.product_id),
            )
        else:
            # Ensure the link exists even when counted == system (e.g. both 0 is odd,
            # but counted==system>0 with no prior link would need creation).
            il = await db.scalar(
                select(ItemLocation).where(
                    ItemLocation.product_id == line.product_id,
                    ItemLocation.location_id == payload.location_id,
                )
            )
            if il is None and line.counted_qty > 0:
                await apply_movement(
                    db,
                    product_id=line.product_id,
                    location_id=payload.location_id,
                    quantity_change=line.counted_qty,
                    movement_type="count",
                    reference="stock-count",
                    note=payload.note,
                    created_by=current.id,
                    next_priority=await next_priority_for(db, line.product_id),
                )
        product = products[line.product_id]
        review.append(
            CountReviewLine(
                product_id=line.product_id,
                product_name=product.name,
                sku=product.sku,
                system_qty=system,
                counted_qty=line.counted_qty,
                variance=line.counted_qty - system,
            )
        )

    await db.commit()
    return StockCountResult(
        location_id=location.id,
        location_name=location.name,
        lines=review,
    )