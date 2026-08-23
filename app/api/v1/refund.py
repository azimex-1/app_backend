import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models.payment import PaymentAccount
from app.models.receipt import Receipt, ReceiptItem
from app.models.refund import RefundDocument, RefundLine
from app.schemas.refund import RefundableLine, RefundableReceipt, RefundCreate, RefundRead

router = APIRouter()


async def _refunded_by_item(db: DbSession, receipt_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = (
        await db.execute(
            select(RefundLine.receipt_item_id, func.coalesce(func.sum(RefundLine.quantity), 0))
            .join(RefundDocument, RefundDocument.id == RefundLine.refund_id)
            .where(RefundDocument.receipt_id == receipt_id)
            .group_by(RefundLine.receipt_item_id)
        )
    ).all()
    return {r[0]: int(r[1]) for r in rows if r[0] is not None}


async def _load_receipt(db: DbSession, receipt_id: uuid.UUID) -> Receipt:
    receipt = await db.scalar(
        select(Receipt)
        .where(Receipt.id == receipt_id)
        .options(selectinload(Receipt.items), selectinload(Receipt.payments))
    )
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.get("/{receipt_id}/refundable", response_model=RefundableReceipt)
async def get_refundable(receipt_id: uuid.UUID, db: DbSession) -> RefundableReceipt:
    receipt = await _load_receipt(db, receipt_id)
    refunded = await _refunded_by_item(db, receipt_id)

    lines = []
    for item in receipt.items:
        already = refunded.get(item.id, 0)
        lines.append(
            RefundableLine(
                receipt_item_id=item.id,
                product_name=item.product_name,
                sku=item.sku,
                unit_price_minor=item.unit_price_minor,
                sold_qty=item.quantity,
                refunded_qty=already,
                returnable_qty=max(0, item.quantity - already),
            )
        )

    suggested = receipt.payments[0].account_id if receipt.payments else None

    return RefundableReceipt(
        receipt_id=receipt.id,
        receipt_number=receipt.receipt_number,
        status=receipt.status,
        customer_name=receipt.customer_name,
        suggested_account_id=suggested,
        lines=lines,
    )


@router.post("/{receipt_id}/refunds", response_model=RefundRead, status_code=status.HTTP_201_CREATED)
async def create_refund(receipt_id: uuid.UUID, payload: RefundCreate, db: DbSession) -> RefundDocument:
    receipt = await _load_receipt(db, receipt_id)
    refunded = await _refunded_by_item(db, receipt_id)
    items_by_id = {item.id: item for item in receipt.items}

    account = await db.get(PaymentAccount, payload.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Refund account not found")

    # Validate + build lines
    refund_lines: list[RefundLine] = []
    total = 0
    for line in payload.lines:
        item = items_by_id.get(line.receipt_item_id)
        if item is None:
            raise HTTPException(status_code=400, detail="Item is not on this receipt")
        returnable = item.quantity - refunded.get(item.id, 0)
        if line.quantity > returnable:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot refund {line.quantity} of {item.product_name} — only {returnable} returnable",
            )
        line_total = item.unit_price_minor * line.quantity
        total += line_total
        refund_lines.append(
            RefundLine(
                receipt_item_id=item.id,
                product_name=item.product_name,
                sku=item.sku,
                quantity=line.quantity,
                unit_price_minor=item.unit_price_minor,
                line_total_minor=line_total,
            )
        )

    count = int(await db.scalar(select(func.count(RefundDocument.id))) or 0)
    refund_number = f"RF-{count + 1:06d}"

    doc = RefundDocument(
        refund_number=refund_number,
        receipt_id=receipt.id,
        reason=payload.reason,
        reason_detail=payload.reason_detail,
        account_id=account.id,
        account_name=account.name,
        currency=account.currency,
        total_minor=total,
        salesperson=payload.salesperson,
        lines=refund_lines,
    )
    db.add(doc)

    # Recompute receipt status from total refunded vs total sold.
    total_sold = sum(item.quantity for item in receipt.items)
    total_refunded = sum(refunded.values()) + sum(l.quantity for l in payload.lines)
    if total_refunded <= 0:
        receipt.status = "completed"
    elif total_refunded >= total_sold:
        receipt.status = "fully_refunded"
    else:
        receipt.status = "partially_refunded"

    await db.commit()
    await db.refresh(doc)
    return doc