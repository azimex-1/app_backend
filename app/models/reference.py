from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Brand(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "brands"
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)


class Category(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "categories"
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)


class Unit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "units"
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)