from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Receipt(Base, UUIDMixin, TimestampMixin):
    """A completed sale (the header). Line items in ReceiptItem, tenders in ReceiptPayment."""

    __tablename__ = "receipts"

    receipt_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    salesperson: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    subtotal_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")

    items: Mapped[list[ReceiptItem]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", lazy="selectin",
    )
    payments: Mapped[list[ReceiptPayment]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", lazy="selectin",
    )


class ReceiptItem(Base, UUIDMixin, TimestampMixin):
    """One line on a receipt — a SNAPSHOT of the product, at the AGREED price."""

    __tablename__ = "receipt_items"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    receipt: Mapped[Receipt] = relationship(back_populates="items")


class ReceiptPayment(Base, UUIDMixin, TimestampMixin):
    """One tender on a receipt. Records the ORIGINAL amount+currency AND its
    dalasi value (converted at the rate agreed at sale time)."""

    __tablename__ = "receipt_payments"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Which account it landed in (the reconciliation bucket). Nullable + SET NULL:
    # the payment line (with its snapshot) survives if the account is deleted.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)  # snapshot

    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)       # original tender
    currency: Mapped[str] = mapped_column(String(3), nullable=False)         # original currency
    dalasi_value_minor: Mapped[int] = mapped_column(Integer, nullable=False) # counts toward the total

    receipt: Mapped[Receipt] = relationship(back_populates="payments")