from fastapi import Depends, APIRouter
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.currency_rate import CurrencyRate
from app.schemas.currency_rate import CurrencyRateRead, CurrencyRateUpsert

router = APIRouter()


@router.get("", response_model=list[CurrencyRateRead])
async def list_rates(db: DbSession, _=Depends(require_permission("pos.access"))) -> list[CurrencyRate]:
    result = await db.scalars(select(CurrencyRate).order_by(CurrencyRate.currency))
    return list(result.all())


@router.put("/{currency}", response_model=CurrencyRateRead)
async def upsert_rate(currency: str, payload: CurrencyRateUpsert, db: DbSession, _=Depends(require_permission("settings.manage"))) -> CurrencyRate:
    code = currency.strip().upper()
    rate = await db.get(CurrencyRate, code)
    if rate is None:
        rate = CurrencyRate(currency=code, rate_to_gmd=payload.rate_to_gmd)
        db.add(rate)
    else:
        rate.rate_to_gmd = payload.rate_to_gmd
    await db.commit()
    await db.refresh(rate)
    return rate