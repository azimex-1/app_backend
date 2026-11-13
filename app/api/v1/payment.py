import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, require_permission
from app.api.v1.reference import _make_reference_router
from app.models.payment import PaymentAccount, PaymentType
from app.schemas.payment import PaymentAccountCreate, PaymentAccountRead, PaymentAccountUpdate

# PaymentType is name-only -> reuse the reference factory (idempotent create).
# Cashiers must be able to read payment methods at checkout (pos.access),
# while only managers create/edit them (settings.manage).
payment_types_router = _make_reference_router(
    PaymentType, view_permission="pos.access", manage_permission="settings.manage"
)

accounts_router = APIRouter()


async def _with_type(db: DbSession, account_id: uuid.UUID) -> PaymentAccount:
    result = await db.scalars(
        select(PaymentAccount).where(PaymentAccount.id == account_id).options(selectinload(PaymentAccount.type))
    )
    acc = result.one_or_none()
    if acc is None:
        raise HTTPException(status_code=404, detail="Payment account not found")
    return acc


@accounts_router.get("", response_model=list[PaymentAccountRead])
async def list_accounts(db: DbSession, _=Depends(require_permission("pos.access")), active_only: bool = False):
    stmt = select(PaymentAccount).options(selectinload(PaymentAccount.type)).order_by(PaymentAccount.name)
    if active_only:
        stmt = stmt.where(PaymentAccount.is_active.is_(True))
    result = await db.scalars(stmt)
    return list(result.all())


@accounts_router.post("", response_model=PaymentAccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(payload: PaymentAccountCreate, db: DbSession, _=Depends(require_permission("settings.manage"))):
    if await db.get(PaymentType, payload.type_id) is None:
        raise HTTPException(status_code=400, detail="Unknown payment type")
    clash = await db.scalar(
        select(PaymentAccount.id).where(func.lower(PaymentAccount.name) == payload.name.strip().lower())
    )
    if clash:
        raise HTTPException(status_code=400, detail="A payment account with this name already exists")

    acc = PaymentAccount(
        name=payload.name.strip(),
        type_id=payload.type_id,
        currency=payload.currency,
        account_number=payload.account_number,
        is_active=payload.is_active,
    )
    db.add(acc)
    await db.commit()
    return await _with_type(db, acc.id)


@accounts_router.put("/{account_id}", response_model=PaymentAccountRead)
async def update_account(account_id: uuid.UUID, payload: PaymentAccountUpdate, db: DbSession, _=Depends(require_permission("settings.manage"))):
    acc = await db.get(PaymentAccount, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="Payment account not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("type_id") and await db.get(PaymentType, data["type_id"]) is None:
        raise HTTPException(status_code=400, detail="Unknown payment type")
    for field, value in data.items():
        setattr(acc, field, value)
    await db.commit()
    return await _with_type(db, account_id)


@accounts_router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: uuid.UUID, db: DbSession):
    acc = await db.get(PaymentAccount, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="Payment account not found")
    await db.delete(acc)
    await db.commit()