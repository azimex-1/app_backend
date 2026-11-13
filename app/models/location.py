import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Location(Base, UUIDMixin, TimestampMixin):
    """A named place where stock lives. Granular by design — the name itself
    carries the detail, e.g. 'Zone A - Shelf B - Row 3' or 'Warehouse B'.
    Picked from a dropdown; managed as a list. Belongs to the organization
    (and optionally a branch, for future multi-branch reporting)."""

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_locations_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ItemLocation(Base, UUIDMixin, TimestampMixin):
    """Where an item is stocked, in priority order, with the quantity there.
    priority 0 = sell from here first; higher numbers are fallbacks.
    quantity is the on-hand at that location (movement-sourced later)."""

    __tablename__ = "item_locations"
    __table_args__ = (UniqueConstraint("product_id", "location_id", name="uq_item_location"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)