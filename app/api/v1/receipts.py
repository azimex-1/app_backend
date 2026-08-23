import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models.customer import Customer, CustomerLedgerEntry
from app.models.payment import PaymentAccount
from app.models.product import Product
from app.models.receipt import Receipt, ReceiptItem, ReceiptPayment
from app.schemas.receipt import (
    DailyAccountBreakdown,
    DailySummary,
    ReceiptCreate,
    ReceiptRead,
    ReceiptSummary,
)

router = APIRouter()


async def _next_receipt_number(db: DbSession) -> str:
    count = await db.scalar(select(func.count(Receipt.id)))
    return f"R-{(count or 0) + 1:06d}"


async def _outstanding_minor(db: DbSession, customer_id: uuid.UUID) -> int:
    row = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    CustomerLedgerEntry.debit_minor
                    - CustomerLedgerEntry.credit_minor
                ),
                0,
            )
        ).where(CustomerLedgerEntry.customer_id == customer_id)
    )

    return int(row.scalar_one())


@router.post("", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
async def create_receipt(payload: ReceiptCreate, db: DbSession) -> Receipt:
    product_ids = [item.product_id for item in payload.items]

    result = await db.scalars(
        select(Product).where(Product.id.in_(product_ids))
    )

    products = {product.id: product for product in result.all()}

    items: list[ReceiptItem] = []
    subtotal = 0

    for line in payload.items:
        product = products.get(line.product_id)

        if product is None:
            raise HTTPException(
                status_code=400,
                detail=f"Product {line.product_id} not found",
            )

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

    total = max(
        0,
        subtotal - payload.discount_minor + payload.tax_minor,
    )

    if payload.total_minor is not None and payload.total_minor != total:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Total mismatch: server computed {total}, "
                f"app sent {payload.total_minor}"
            ),
        )

    customer: Customer | None = None

    if payload.customer_id is not None:
        customer = await db.get(Customer, payload.customer_id)

        if customer is None:
            raise HTTPException(
                status_code=400,
                detail="Customer not found",
            )

    payments: list[ReceiptPayment] = []
    paid_dalasi = 0

    if payload.payments:
        account_ids = [payment.account_id for payment in payload.payments]

        acc_result = await db.scalars(
            select(PaymentAccount).where(PaymentAccount.id.in_(account_ids))
        )

        accounts = {account.id: account for account in acc_result.all()}

        for pay in payload.payments:
            account = accounts.get(pay.account_id)

            if account is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment account {pay.account_id} not found",
                )

            paid_dalasi += pay.dalasi_value_minor

            payments.append(
                ReceiptPayment(
                    account_id=account.id,
                    account_name=account.name,
                    amount_minor=pay.amount_minor,
                    currency=account.currency,
                    dalasi_value_minor=pay.dalasi_value_minor,
                )
            )

    credit = payload.credit_minor

    if credit > 0:
        if customer is None:
            raise HTTPException(
                status_code=400,
                detail="A credit sale needs a real customer, not Walk-in",
            )

        if not customer.credit_enabled:
            raise HTTPException(
                status_code=400,
                detail="Credit is not enabled for this customer",
            )

        outstanding = await _outstanding_minor(db, customer.id)
        available = customer.credit_limit_minor - outstanding

        if credit > available:
            raise HTTPException(
                status_code=400,
                detail=f"Credit {credit} exceeds available credit {available}",
            )

    if (payload.payments or credit) and (paid_dalasi + credit) < total:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Payments ({paid_dalasi}) + credit ({credit}) "
                f"do not cover the total ({total})"
            ),
        )

    receipt = Receipt(
        receipt_number=await _next_receipt_number(db),
        customer_id=payload.customer_id,
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

    if credit > 0 and customer is not None:
        db.add(
            CustomerLedgerEntry(
                customer_id=customer.id,
                entry_type="invoice",
                description=f"Credit sale {receipt.receipt_number}",
                debit_minor=credit,
                credit_minor=0,
                reference=receipt.receipt_number,
                receipt_id=receipt.id,
            )
        )

    await db.commit()
    await db.refresh(receipt)

    return receipt


@router.get("", response_model=list[ReceiptSummary])
async def list_receipts(
    db: DbSession,
    q: str | None = None,
    query: str | None = None,
    salesperson: str | None = None,
    customer: str | None = None,
    customer_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    product_ids: list[uuid.UUID] = Query(default_factory=list),
    payment_method_id: uuid.UUID | None = None,
    sku: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_total: int | None = None,
    max_total: int | None = None,
) -> list[Receipt]:
    stmt = select(Receipt)

    search_text = query or q

    if search_text:
        like = f"%{search_text}%"

        item_search_subquery = (
            select(ReceiptItem.receipt_id)
            .join(Product, ReceiptItem.product_id == Product.id)
            .where(
                or_(
                    ReceiptItem.sku.ilike(like),
                    ReceiptItem.product_name.ilike(like),
                    Product.sku.ilike(like),
                    Product.name.ilike(like),
                    Product.barcode.ilike(like),
                    Product.manufacturer_code.ilike(like),
                )
            )
        )

        stmt = stmt.where(
            or_(
                Receipt.receipt_number.ilike(like),
                Receipt.customer_name.ilike(like),
                Receipt.salesperson.ilike(like),
                Receipt.id.in_(item_search_subquery),
            )
        )

    if salesperson:
        stmt = stmt.where(
            Receipt.salesperson.ilike(f"%{salesperson}%")
        )

    if customer:
        stmt = stmt.where(
            Receipt.customer_name.ilike(f"%{customer}%")
        )

    if customer_id:
        stmt = stmt.where(
            Receipt.customer_id == customer_id
        )

    selected_product_ids = list(product_ids)

    if product_id is not None:
        selected_product_ids.append(product_id)

    for selected_product_id in selected_product_ids:
        stmt = stmt.where(
            Receipt.id.in_(
                select(ReceiptItem.receipt_id).where(
                    ReceiptItem.product_id == selected_product_id
                )
            )
        )

    if sku:
        stmt = stmt.where(
            Receipt.id.in_(
                select(ReceiptItem.receipt_id).where(
                    ReceiptItem.sku.ilike(f"%{sku}%")
                )
            )
        )

    if payment_method_id:
        stmt = stmt.where(
            Receipt.id.in_(
                select(ReceiptPayment.receipt_id).where(
                    ReceiptPayment.account_id == payment_method_id
                )
            )
        )

    if date_from:
        stmt = stmt.where(
            Receipt.created_at >= date_from
        )

    if date_to:
        stmt = stmt.where(
            Receipt.created_at < date_to + timedelta(days=1)
        )

    if min_total is not None:
        stmt = stmt.where(
            Receipt.total_minor >= min_total
        )

    if max_total is not None:
        stmt = stmt.where(
            Receipt.total_minor <= max_total
        )

    stmt = stmt.order_by(
        Receipt.created_at.desc()
    ).limit(200)

    result = await db.scalars(stmt)

    return list(result.all())


@router.get("/summary", response_model=DailySummary)
async def daily_summary(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    customer_id: uuid.UUID | None = None,
) -> DailySummary:
    today = date.today()

    df = date_from or today
    dt = date_to or today

    start = df
    end = dt + timedelta(days=1)

    rstmt = select(
        func.count(Receipt.id),
        func.coalesce(func.sum(Receipt.total_minor), 0),
    ).where(
        Receipt.created_at >= start,
        Receipt.created_at < end,
    )

    if customer_id:
        rstmt = rstmt.where(
            Receipt.customer_id == customer_id
        )

    rcount, rtotal = (await db.execute(rstmt)).one()

    pstmt = (
        select(
            ReceiptPayment.account_name,
            ReceiptPayment.currency,
            func.count(ReceiptPayment.id),
            func.coalesce(func.sum(ReceiptPayment.amount_minor), 0),
            func.coalesce(func.sum(ReceiptPayment.dalasi_value_minor), 0),
        )
        .join(Receipt, ReceiptPayment.receipt_id == Receipt.id)
        .where(
            Receipt.created_at >= start,
            Receipt.created_at < end,
        )
    )

    if customer_id:
        pstmt = pstmt.where(
            Receipt.customer_id == customer_id
        )

    pstmt = pstmt.group_by(
        ReceiptPayment.account_name,
        ReceiptPayment.currency,
    ).order_by(
        ReceiptPayment.account_name
    )

    rows = (await db.execute(pstmt)).all()

    by_account = [
        DailyAccountBreakdown(
            account_name=row[0],
            currency=row[1],
            count=int(row[2]),
            amount_minor=int(row[3]),
            dalasi_value_minor=int(row[4]),
        )
        for row in rows
    ]

    return DailySummary(
        date_from=df,
        date_to=dt,
        receipt_count=int(rcount),
        total_minor=int(rtotal),
        by_account=by_account,
    )


@router.get("/{receipt_id}", response_model=ReceiptRead)
async def get_receipt(
    receipt_id: uuid.UUID,
    db: DbSession,
) -> Receipt:
    result = await db.scalars(
        select(Receipt)
        .where(Receipt.id == receipt_id)
        .options(
            selectinload(Receipt.items),
            selectinload(Receipt.payments),
        )
    )

    receipt = result.one_or_none()

    if receipt is None:
        raise HTTPException(
            status_code=404,
            detail="Receipt not found",
        )

    return receipt