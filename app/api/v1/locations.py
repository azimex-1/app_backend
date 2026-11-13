import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_permission
from app.models.location import ItemLocation, Location
from app.models.product import Product
from app.models.user import User
from app.schemas.location import (
    ItemLocationRead,
    ItemLocationsUpdate,
    LocationRead,
    LocationWrite,
)

# ── Location CRUD (mounted at /locations) ──
router = APIRouter()


@router.get("", response_model=list[LocationRead])
async def list_locations(
    user: CurrentUser,
    db: DbSession,
    _=Depends(require_permission("inventory.view")),
    include_inactive: bool = False,
) -> list[Location]:
    stmt = select(Location).where(Location.organization_id == user.organization_id)
    if not include_inactive:
        stmt = stmt.where(Location.is_active.is_(True))
    stmt = stmt.order_by(Location.name)
    return list((await db.scalars(stmt)).all())


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationWrite,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> Location:
    name = payload.name.strip()
    # Idempotent by name within the org (dropdown add-on-the-fly).
    existing = await db.scalar(
        select(Location).where(
            Location.organization_id == current.organization_id,
            func.lower(Location.name) == name.lower(),
        )
    )
    if existing:
        return existing
    loc = Location(
        organization_id=current.organization_id,
        name=name,
        code=payload.code,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


async def _get_location(db: DbSession, location_id: uuid.UUID, org_id: uuid.UUID) -> Location:
    loc = await db.get(Location, location_id)
    if loc is None or loc.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc


@router.put("/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: uuid.UUID,
    payload: LocationWrite,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> Location:
    loc = await _get_location(db, location_id, current.organization_id)
    loc.name = payload.name.strip()
    loc.code = payload.code
    loc.description = payload.description
    loc.is_active = payload.is_active
    await db.commit()
    await db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: uuid.UUID,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> None:
    loc = await _get_location(db, location_id, current.organization_id)
    in_use = await db.scalar(select(func.count(ItemLocation.id)).where(ItemLocation.location_id == location_id))
    if in_use:
        raise HTTPException(status_code=400, detail=f"Location is used by {in_use} item(s)")
    await db.delete(loc)
    await db.commit()


# ── Item ↔ location priority list (mounted at /products) ──
item_locations_router = APIRouter()


@item_locations_router.get("/{product_id}/locations", response_model=list[ItemLocationRead])
async def get_item_locations(
    product_id: uuid.UUID,
    db: DbSession,
    _=Depends(require_permission("inventory.view")),
) -> list[ItemLocationRead]:
    rows = (
        await db.execute(
            select(ItemLocation, Location.name)
            .join(Location, Location.id == ItemLocation.location_id)
            .where(ItemLocation.product_id == product_id)
            .order_by(ItemLocation.priority, Location.name)
        )
    ).all()
    return [
        ItemLocationRead(
            location_id=il.location_id,
            location_name=name,
            priority=il.priority,
            quantity=il.quantity,
        )
        for (il, name) in rows
    ]


@item_locations_router.put("/{product_id}/locations", response_model=list[ItemLocationRead])
async def set_item_locations(
    product_id: uuid.UUID,
    payload: ItemLocationsUpdate,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("inventory.manage"))],
) -> list[ItemLocationRead]:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate all locations belong to the org.
    loc_ids = [l.location_id for l in payload.locations]
    if loc_ids:
        valid = (
            await db.scalars(
                select(Location.id).where(
                    Location.id.in_(loc_ids), Location.organization_id == current.organization_id
                )
            )
        ).all()
        if len(set(valid)) != len(set(loc_ids)):
            raise HTTPException(status_code=400, detail="One or more locations are invalid")

    # Replace-all: delete existing rows, insert the new ordered set.
    existing = (await db.scalars(select(ItemLocation).where(ItemLocation.product_id == product_id))).all()
    for row in existing:
        await db.delete(row)
    for entry in payload.locations:
        db.add(
            ItemLocation(
                product_id=product_id,
                location_id=entry.location_id,
                priority=entry.priority,
                quantity=entry.quantity,
            )
        )
    await db.commit()

    return await get_item_locations(product_id, db)  # type: ignore[arg-type]