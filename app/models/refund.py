import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class RefundDocument(Base, UUIDMixin, TimestampMixin):
    """A refund (RF-000001) linked to an original receipt. Money paid back out
    via a payment account. Does not edit or delete the original receipt."""

    __tablename__ = "refund_documents"

    refund_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    reason: Mapped[str] = mapped_column(String(60), nullable=False)
    reason_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_accounts.id", ondelete="SET NULL"), nullable=True
    )
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)  # snapshot
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GMD")

    total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # dalasi
    salesperson: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lines: Mapped[list["RefundLine"]] = relationship(
        back_populates="refund", cascade="all, delete-orphan", lazy="selectin"
    )


class RefundLine(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "refund_lines"

    refund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refund_documents.id", ondelete="CASCADE"), nullable=False
    )
    receipt_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipt_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    refund: Mapped[RefundDocument] = relationship(back_populates="lines")