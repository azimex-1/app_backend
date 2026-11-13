"""Central place to change stock.

Source of truth is Product.quantity (the item's store-wide total). Every
change goes through apply_movement, which (1) logs an append-only
StockMovement, (2) updates Product.quantity, and (3) — only when a bin is
given — also keeps that bin's ItemLocation level. Bins are optional
findability detail; the store total is authoritative."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import ItemLocation
from app.models.product import Product
from app.models.stock_movement import StockMovement


async def apply_movement(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    quantity_change: int,
    movement_type: str,
    location_id: uuid.UUID | None = None,
    reference: str | None = None,
    note: str | None = None,
    created_by: uuid.UUID | None = None,
    next_priority: int = 0,
) -> ItemLocation | None:
    """Record a movement and update the item's store total. If a location is
    given, also update that bin's level. Does NOT commit."""
    db.add(
        StockMovement(
            product_id=product_id,
            location_id=location_id,
            quantity_change=quantity_change,
            movement_type=movement_type,
            reference=reference,
            note=note,
            created_by=created_by,
        )
    )

    # Source of truth: the item's store-wide quantity.
    product = await db.get(Product, product_id)
    if product is not None:
        product.quantity = (product.quantity or 0) + quantity_change

    # Optional bin level (findability detail), only when a location was given.
    il: ItemLocation | None = None
    if location_id is not None:
        il = await db.scalar(
            select(ItemLocation).where(
                ItemLocation.product_id == product_id,
                ItemLocation.location_id == location_id,
            )
        )
        if il is None:
            il = ItemLocation(
                product_id=product_id,
                location_id=location_id,
                priority=next_priority,
                quantity=quantity_change if quantity_change > 0 else 0,
            )
            db.add(il)
        else:
            il.quantity = il.quantity + quantity_change
    return il


async def next_priority_for(db: AsyncSession, product_id: uuid.UUID) -> int:
    rows = (await db.scalars(select(ItemLocation.priority).where(ItemLocation.product_id == product_id))).all()
    return (max(rows) + 1) if rows else 0


async def deduct_sale(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    quantity: int,
    reference: str | None = None,
    created_by: uuid.UUID | None = None,
) -> None:
    """Deduct a sold quantity from the item's store total and log it.
    Store-level (no bin). Never blocks the sale; total may go negative,
    which is a visible discrepancy to reconcile with a stock count."""
    if quantity <= 0:
        return
    await apply_movement(
        db,
        product_id=product_id,
        quantity_change=-quantity,
        movement_type="sale",
        reference=reference,
        created_by=created_by,
    )