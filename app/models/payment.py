from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PaymentType(Base, UUIDMixin, TimestampMixin):
    """The KIND of tender: Cash, Cheque, Bank Transfer, Mobile Money, Foreign Cash."""

    __tablename__ = "payment_types"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)


class PaymentAccount(Base, UUIDMixin, TimestampMixin):
    """A specific bucket money lands in — the reconciliation unit.

    e.g. "Main till" (Cash/GMD), "Ecobank acc02939" (Bank Transfer/GMD),
    "Euro drawer" (Foreign Cash/EUR). Each belongs to a type and holds one currency.
    """

    __tablename__ = "payment_accounts"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GMD", server_default="GMD")
    account_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    type: Mapped[PaymentType] = relationship(lazy="selectin")

    @property
    def type_name(self) -> str | None:
        return self.type.name if self.type else None