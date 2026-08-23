import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PosSession(Base, UUIDMixin, TimestampMixin):
    """A cash/register session (shift). One open at a time for the pilot."""

    __tablename__ = "pos_sessions"

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    opening_float_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opened_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")  # open | closed

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_cash_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)  # snapshot at close
    counted_cash_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difference_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CashMovement(Base, UUIDMixin, TimestampMixin):
    """A cash-in or cash-out during a session (not a sale/refund)."""

    __tablename__ = "cash_movements"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_sessions.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(3), nullable=False)  # in | out
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)