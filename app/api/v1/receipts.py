import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models.payment import PaymentAccount
from app.models.product import Product
from app.models.receipt import Receipt, ReceiptItem, ReceiptPayment
from app.schemas.receipt import ReceiptCreate, ReceiptRead, ReceiptSummary

router = APIRouter()


async def _next_receipt_number(db: DbSession) -> str:
    count = await db.scalar(select(func.count(Receipt.id)))
    return f"R-{(count or 0) + 1:06d}"


@router.post("", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
async def create_receipt(payload: ReceiptCreate, db: DbSession) -> Receipt:
    # ── Items (server computes the money) ──
    product_ids = [i.product_id for i in payload.items]
    result = await db.scalars(select(Product).where(Product.id.in_(product_ids)))
    products = {p.id: p for p in result.all()}

    items: list[ReceiptItem] = []
    subtotal = 0
    for line in payload.items:
        product = products.get(line.product_id)
        if product is None:
            raise HTTPException(status_code=400, detail=f"Product {line.product_id} not found")
        line_total = line.unit_price_minor * line.quantity
        subtotal += line_total
        items.append(
            ReceiptItem(
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                unit_price_minor=line.unit_price_minor,
                quantity=line.quantity,
                line_total_minor=line_total,
            )
        )

    total = max(0, subtotal - payload.discount_minor + payload.tax_minor)
    if payload.total_minor is not None and payload.total_minor != total:
        raise HTTPException(
            status_code=400,
            detail=f"Total mismatch: server computed {total}, app sent {payload.total_minor}",
        )

    # ── Payments (snapshot account + currency; check coverage) ──
    payments: list[ReceiptPayment] = []
    if payload.payments:
        account_ids = [p.account_id for p in payload.payments]
        acc_result = await db.scalars(select(PaymentAccount).where(PaymentAccount.id.in_(account_ids)))
        accounts = {a.id: a for a in acc_result.all()}

        paid_dalasi = 0
        for pay in payload.payments:
            account = accounts.get(pay.account_id)
            if account is None:
                raise HTTPException(status_code=400, detail=f"Payment account {pay.account_id} not found")
            paid_dalasi += pay.dalasi_value_minor
            payments.append(
                ReceiptPayment(
                    account_id=account.id,
                    account_name=account.name,
                    amount_minor=pay.amount_minor,
                    currency=account.currency,   # currency comes from the account
                    dalasi_value_minor=pay.dalasi_value_minor,
                )
            )

        # Paid-in-full: dalasi value of tenders must cover the total.
        if paid_dalasi < total:
            raise HTTPException(
                status_code=400,
                detail=f"Payments cover {paid_dalasi} but the total is {total}",
            )

    receipt = Receipt(
        receipt_number=await _next_receipt_number(db),
        customer_name=payload.customer_name,
        salesperson=payload.salesperson,
        notes=payload.notes,
        subtotal_minor=subtotal,
        discount_minor=payload.discount_minor,
        tax_minor=payload.tax_minor,
        total_minor=total,
        items=items,
        payments=payments,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return receipt


@router.get("", response_model=list[ReceiptSummary])
async def list_receipts(
    db: DbSession,
    q: str | None = None,
    salesperson: str | None = None,
    customer: str | None = None,
    sku: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_total: int | None = None,
    max_total: int | None = None,
) -> list[Receipt]:
    """Recent receipts, newest first, narrowed by any combination of filters."""
    stmt = select(Receipt).order_by(Receipt.created_at.desc()).limit(200)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Receipt.receipt_number.ilike(like),
                Receipt.customer_name.ilike(like),
                Receipt.salesperson.ilike(like),
            )
        )
    if salesperson:
        stmt = stmt.where(Receipt.salesperson.ilike(f"%{salesperson}%"))
    if customer:
        stmt = stmt.where(Receipt.customer_name.ilike(f"%{customer}%"))
    if sku:
        stmt = stmt.where(
            Receipt.id.in_(select(ReceiptItem.receipt_id).where(ReceiptItem.sku.ilike(f"%{sku}%")))
        )
    if date_from:
        stmt = stmt.where(Receipt.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Receipt.created_at < date_to + timedelta(days=1))
    if min_total is not None:
        stmt = stmt.where(Receipt.total_minor >= min_total)
    if max_total is not None:
        stmt = stmt.where(Receipt.total_minor <= max_total)

    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/{receipt_id}", response_model=ReceiptRead)
async def get_receipt(receipt_id: uuid.UUID, db: DbSession) -> Receipt:
    result = await db.scalars(
        select(Receipt)
        .where(Receipt.id == receipt_id)
        .options(selectinload(Receipt.items), selectinload(Receipt.payments))
    )
    receipt = result.one_or_none()
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt