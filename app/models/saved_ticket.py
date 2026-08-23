import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SavedTicket(Base, UUIDMixin, TimestampMixin):
    """A parked basket (not a sale). Holds the cart as JSON so it can be
    restored later. Consumed (deleted) when restored to the basket."""

    __tablename__ = "saved_tickets"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # [{product_id, name, sku, unit_price_minor, quantity}, ...]
    lines: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)