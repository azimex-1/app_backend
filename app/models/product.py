from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Product(Base, UUIDMixin, TimestampMixin):
    """An item Azimex sells. Global for now; org scoping added with auth."""

    __tablename__ = "products"

    # ── Identity ──
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The code the user enters (e.g. "OX 123"); SKU is generated from it.
    manufacturer_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Auto-generated internal code, e.g. "MANN-OX123".
    sku: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    # ── Pricing (minor units / bututs for GMD amounts) ──
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # selling price
    selling_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="GMD", server_default="GMD"
    )
    cost_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # ── Stock (interim total; per-location comes later) ──
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # ── Flags ──
    available_for_sale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    track_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # ── Extra ──
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)  # piece, litre, set...
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)