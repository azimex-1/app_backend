import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.models.payment import PaymentAccount, PaymentType
from app.models.pos_session import CashMovement, PosSession
from app.models.receipt import Receipt, ReceiptPayment
from app.models.refund import RefundDocument
from app.schemas.pos_session import (
    AccountBreakdown,
    CashMovementCreate,
    CashMovementRead,
    PosSessionRead,
    SessionClose,
    SessionOpen,
    SessionReport,
)

router = APIRouter()


async def _current_open(db: DbSession) -> PosSession | None:
    return await db.scalar(select(PosSession).where(PosSession.status == "open").order_by(PosSession.opened_at.desc()))


async def _build_report(db: DbSession, session: PosSession) -> SessionReport:
    end = session.closed_at or datetime.now(timezone.utc)
    start = session.opened_at

    # payment-method breakdown (all accounts) in the session window
    rows = (
        await db.execute(
            select(
                ReceiptPayment.account_name,
                ReceiptPayment.currency,
                func.count(ReceiptPayment.id),
                func.coalesce(func.sum(ReceiptPayment.amount_minor), 0),
                func.coalesce(func.sum(ReceiptPayment.dalasi_value_minor), 0),
            )
            .join(Receipt, Receipt.id == ReceiptPayment.receipt_id)
            .where(Receipt.created_at >= start, Receipt.created_at <= end)
            .group_by(ReceiptPayment.account_name, ReceiptPayment.currency)
            .order_by(ReceiptPayment.account_name)
        )
    ).all()

    by_account = [
        AccountBreakdown(
            account_name=r[0] or "—",
            currency=r[1] or "GMD",
            count=int(r[2]),
            amount_minor=int(r[3]),
            dalasi_value_minor=int(r[4]),
        )
        for r in rows
    ]
    total_sales_minor = sum(b.dalasi_value_minor for b in by_account)

    # cash sales = payments into Cash-type accounts (dalasi)
    cash_sales_minor = int(
        await db.scalar(
            select(func.coalesce(func.sum(ReceiptPayment.dalasi_value_minor), 0))
            .join(Receipt, Receipt.id == ReceiptPayment.receipt_id)
            .join(PaymentAccount, PaymentAccount.id == ReceiptPayment.account_id)
            .join(PaymentType, PaymentType.id == PaymentAccount.type_id)
            .where(Receipt.created_at >= start, Receipt.created_at <= end, PaymentType.name == "Cash")
        )
        or 0
    )

    # refunds by account (money out) in the window
    refund_rows = (
        await db.execute(
            select(
                RefundDocument.account_name,
                RefundDocument.currency,
                func.count(RefundDocument.id),
                func.coalesce(func.sum(RefundDocument.total_minor), 0),
                func.coalesce(func.sum(RefundDocument.total_minor), 0),
            )
            .where(RefundDocument.created_at >= start, RefundDocument.created_at <= end)
            .group_by(RefundDocument.account_name, RefundDocument.currency)
            .order_by(RefundDocument.account_name)
        )
    ).all()
    refunds_by_account = [
        AccountBreakdown(
            account_name=r[0] or "—",
            currency=r[1] or "GMD",
            count=int(r[2]),
            amount_minor=int(r[3]),
            dalasi_value_minor=int(r[4]),
        )
        for r in refund_rows
    ]
    total_refunds_minor = sum(b.dalasi_value_minor for b in refunds_by_account)

    cash_refunds_minor = int(
        await db.scalar(
            select(func.coalesce(func.sum(RefundDocument.total_minor), 0))
            .join(PaymentAccount, PaymentAccount.id == RefundDocument.account_id)
            .join(PaymentType, PaymentType.id == PaymentAccount.type_id)
            .where(RefundDocument.created_at >= start, RefundDocument.created_at <= end, PaymentType.name == "Cash")
        )
        or 0
    )

    cash_in_minor = int(
        await db.scalar(
            select(func.coalesce(func.sum(CashMovement.amount_minor), 0)).where(
                CashMovement.session_id == session.id, CashMovement.direction == "in"
            )
        )
        or 0
    )
    cash_out_minor = int(
        await db.scalar(
            select(func.coalesce(func.sum(CashMovement.amount_minor), 0)).where(
                CashMovement.session_id == session.id, CashMovement.direction == "out"
            )
        )
        or 0
    )

    expected_cash_minor = (
        session.opening_float_minor + cash_sales_minor - cash_refunds_minor + cash_in_minor - cash_out_minor
    )

    mv_rows = (
        await db.scalars(
            select(CashMovement).where(CashMovement.session_id == session.id).order_by(CashMovement.created_at.desc())
        )
    ).all()

    return SessionReport(
        session=PosSessionRead.model_validate(session),
        by_account=by_account,
        total_sales_minor=total_sales_minor,
        cash_sales_minor=cash_sales_minor,
        refunds_by_account=refunds_by_account,
        total_refunds_minor=total_refunds_minor,
        cash_refunds_minor=cash_refunds_minor,
        cash_in_minor=cash_in_minor,
        cash_out_minor=cash_out_minor,
        expected_cash_minor=expected_cash_minor,
        counted_cash_minor=session.counted_cash_minor,
        difference_minor=session.difference_minor,
        movements=[CashMovementRead.model_validate(m) for m in mv_rows],
    )


@router.post("/open", response_model=PosSessionRead, status_code=status.HTTP_201_CREATED)
async def open_session(
    payload: SessionOpen,
    db: DbSession,
    _=Depends(require_permission("pos.session.manage")),
) -> PosSession:
    if await _current_open(db) is not None:
        raise HTTPException(status_code=409, detail="A session is already open. Close it first.")
    session = PosSession(
        opening_float_minor=payload.opening_float_minor,
        opened_by=payload.opened_by,
        status="open",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/current", response_model=PosSessionRead | None)
async def current_session(
    db: DbSession,
    _=Depends(require_permission("pos.access")),
) -> PosSession | None:
    return await _current_open(db)


@router.get("/{session_id}/report", response_model=SessionReport)
async def session_report(
    session_id: uuid.UUID,
    db: DbSession,
    _=Depends(require_permission("pos.access")),
) -> SessionReport:
    session = await db.get(PosSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _build_report(db, session)


@router.post("/{session_id}/cash-movements", response_model=CashMovementRead, status_code=status.HTTP_201_CREATED)
async def add_movement(
    session_id: uuid.UUID,
    payload: CashMovementCreate,
    db: DbSession,
    _=Depends(require_permission("pos.cash_movement")),
) -> CashMovement:
    session = await db.get(PosSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="Session is closed")
    movement = CashMovement(
        session_id=session_id,
        direction=payload.direction,
        amount_minor=payload.amount_minor,
        reason=payload.reason,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


@router.post("/{session_id}/close", response_model=SessionReport)
async def close_session(
    session_id: uuid.UUID,
    payload: SessionClose,
    db: DbSession,
    _=Depends(require_permission("pos.session.manage")),
) -> SessionReport:
    session = await db.get(PosSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="Session is already closed")

    session.closed_at = datetime.now(timezone.utc)
    report = await _build_report(db, session)  # expected computed against closed_at

    session.status = "closed"
    session.expected_cash_minor = report.expected_cash_minor
    session.counted_cash_minor = payload.counted_cash_minor
    session.difference_minor = payload.counted_cash_minor - report.expected_cash_minor
    session.close_note = payload.note
    await db.commit()
    await db.refresh(session)

    return await _build_report(db, session)