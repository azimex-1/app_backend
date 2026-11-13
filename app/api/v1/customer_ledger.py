import uuid
from datetime import date

from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.customer import Customer, CustomerLedgerEntry
from app.schemas.customer_ledger import (
    AdjustmentCreate,
    CustomerLedgerResponse,
    LedgerEntryRead,
    PaymentCreate,
)

router = APIRouter()


async def _require_customer(db: DbSession, customer_id: uuid.UUID) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/{customer_id}/ledger", response_model=CustomerLedgerResponse)
async def get_ledger(customer_id: uuid.UUID, db: DbSession, _=Depends(require_permission("customers.view"))) -> CustomerLedgerResponse:
    customer = await _require_customer(db, customer_id)

    entries = (
        await db.scalars(
            select(CustomerLedgerEntry)
            .where(CustomerLedgerEntry.customer_id == customer_id)
            .order_by(CustomerLedgerEntry.entry_date, CustomerLedgerEntry.created_at)
        )
    ).all()

    running = 0
    out: list[LedgerEntryRead] = []
    for e in entries:
        running += e.debit_minor - e.credit_minor
        out.append(LedgerEntryRead(
            id=e.id, entry_type=e.entry_type, description=e.description,
            debit_minor=e.debit_minor, credit_minor=e.credit_minor,
            reference=e.reference, entry_date=e.entry_date, created_at=e.created_at,
            balance_after_minor=running,
        ))

    outstanding = running
    available = (customer.credit_limit_minor - outstanding) if customer.credit_enabled else None

    out.reverse()  # newest first for display
    return CustomerLedgerResponse(
        customer_id=customer_id,
        outstanding_minor=outstanding,
        credit_enabled=customer.credit_enabled,
        credit_limit_minor=customer.credit_limit_minor,
        available_credit_minor=available,
        entries=out,
    )


@router.post("/{customer_id}/payments", status_code=status.HTTP_201_CREATED)
async def record_payment(customer_id: uuid.UUID, payload: PaymentCreate, db: DbSession, _=Depends(require_permission("customers.manage"))):
    await _require_customer(db, customer_id)
    entry = CustomerLedgerEntry(
        customer_id=customer_id,
        entry_type="payment",
        description=payload.description or "Payment received",
        credit_minor=payload.amount_minor,
        debit_minor=0,
        reference=payload.reference,
        payment_account_id=payload.account_id,
        entry_date=payload.entry_date or date.today(),
    )
    db.add(entry)
    await db.commit()
    return {"id": str(entry.id), "message": "Payment recorded"}


@router.post("/{customer_id}/adjustments", status_code=status.HTTP_201_CREATED)
async def add_adjustment(customer_id: uuid.UUID, payload: AdjustmentCreate, db: DbSession, _=Depends(require_permission("customers.manage"))):
    await _require_customer(db, customer_id)
    entry = CustomerLedgerEntry(
        customer_id=customer_id,
        entry_type="adjustment",
        description=payload.description,
        debit_minor=payload.amount_minor if payload.direction == "debit" else 0,
        credit_minor=payload.amount_minor if payload.direction == "credit" else 0,
        entry_date=payload.entry_date or date.today(),
    )
    db.add(entry)
    await db.commit()
    return {"id": str(entry.id), "message": "Adjustment recorded"}