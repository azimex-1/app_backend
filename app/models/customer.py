from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Customer(Base, UUIDMixin, TimestampMixin):
    """Central customer record. The balance lives in CustomerLedgerEntry (derived)."""

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Active", server_default="Active")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # ── Credit policy (balance is derived from the ledger) ──
    credit_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    credit_limit_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    payment_terms: Mapped[str | None] = mapped_column(String(30), nullable=True)
    credit_hold_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CustomerLedgerEntry(Base, UUIDMixin, TimestampMixin):
    """One line in a customer's financial history. Balance is the running sum:
    debit increases what they owe, credit decreases it."""

    __tablename__ = "customer_ledger_entries"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # invoice | payment | credit_note | debit_note | return | adjustment
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    debit_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)   # owes more
    credit_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # owes less

    reference: Mapped[str | None] = mapped_column(String(60), nullable=True)  # receipt no / payment ref
    entry_date: Mapped[date] = mapped_column(nullable=False, default=date.today, index=True)

    # Optional links to source documents (nullable; survive deletion of source).
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True
    )
    payment_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_accounts.id", ondelete="SET NULL"), nullable=True
    )