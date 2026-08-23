from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CurrencyRate(Base, TimestampMixin):
    """Shop-wide exchange rate: 1 unit of `currency` = `rate_to_gmd` dalasi.
    GMD is implicitly 1 and not stored."""

    __tablename__ = "currency_rates"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate_to_gmd: Mapped[float] = mapped_column(Float, nullable=False)