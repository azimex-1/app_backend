import re
import uuid

from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate

router = APIRouter()


def _slug(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _build_name(brand: str | None, category: str | None, code: str) -> str:
    parts = [p for p in [brand, category, code] if p and p.strip()]
    return " ".join(parts).strip() or code


async def _generate_sku(db: DbSession, brand: str | None, code: str) -> str:
    base = f"{_slug(brand)}-{_slug(code)}" if brand else _slug(code)
    base = base.strip("-") or "ITEM"
    candidate, n = base, 1
    while await db.scalar(select(Product.id).where(Product.sku == candidate)):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


@router.get("", response_model=list[ProductRead])
async def list_products(db: DbSession, _=Depends(require_permission("inventory.view"))) -> list[Product]:
    result = await db.scalars(select(Product).order_by(Product.name))
    return list(result.all())


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: DbSession, _=Depends(require_permission("inventory.manage"))) -> Product:
    code = payload.manufacturer_code.strip().upper()  # normalize to CAPS
    sku = await _generate_sku(db, payload.brand, code)
    name = payload.name or _build_name(payload.brand, payload.category, code)

    product = Product(
        name=name,
        sku=sku,
        manufacturer_code=code,
        barcode=payload.barcode,
        brand=payload.brand,
        category=payload.category,
        price_minor=payload.price_minor,
        selling_currency=payload.selling_currency,
        cost_price_minor=payload.cost_price_minor,
        cost_currency=payload.cost_currency,
        reorder_level=payload.reorder_level,
        available_for_sale=payload.available_for_sale,
        track_stock=payload.track_stock,
        unit=payload.unit,
        description=payload.description,
        image_url=payload.image_url,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(product_id: uuid.UUID, payload: ProductUpdate, db: DbSession, _=Depends(require_permission("inventory.manage"))) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    data = payload.model_dump(exclude_unset=True)
    if data.get("manufacturer_code"):
        data["manufacturer_code"] = data["manufacturer_code"].strip().upper()
    for field, value in data.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: uuid.UUID, db: DbSession, _=Depends(require_permission("inventory.manage"))) -> None:
    # Hard delete for now; becomes soft delete once sales reference products.
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()