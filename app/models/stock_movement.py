import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class StockMovement(Base, UUIDMixin, TimestampMixin):
    """Append-only log of every stock change. The ItemLocation.quantity is the
    fast current value; summing movements reconciles it. Never edited/deleted."""

    __tablename__ = "stock_movements"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: a store-level movement (e.g. a POS sale) has no specific bin.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Positive = stock in, negative = stock out.
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    # count | receive | sale | transfer_in | transfer_out | adjustment
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. receipt no, count id
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )