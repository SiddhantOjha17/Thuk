"""SQLAlchemy database models."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    pass


class SourceType(str, Enum):
    """Source type for expense entries."""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"


class DebtDirection(str, Enum):
    """Direction of debt."""

    OWES_ME = "owes_me"
    I_OWE = "i_owe"


class User(Base):
    """User model - each WhatsApp user who interacts with the bot."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Relationships
    categories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    debts: Mapped[list["Debt"]] = relationship(
        "Debt",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(phone={self.phone_number})>"


class Category(Base):
    """Expense category - both default and user-defined."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    icon: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="categories")
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="category",
    )

    def __repr__(self) -> str:
        return f"<Category(name={self.name})>"


class Expense(Base):
    """Expense entry - tracks individual expenses."""

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(10),
        default=SourceType.TEXT.value,
    )
    expense_date: Mapped[date] = mapped_column(
        Date,
        default=lambda: datetime.now(UTC).date(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="expenses")
    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="expenses",
    )
    split: Mapped["Split | None"] = relationship(
        "Split",
        back_populates="expense",
        uselist=False,
        cascade="all, delete-orphan",
    )
    debts: Mapped[list["Debt"]] = relationship(
        "Debt",
        back_populates="related_expense",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Expense(amount={self.amount} {self.currency})>"


class Split(Base):
    """Split payment tracking for shared expenses."""

    __tablename__ = "splits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    total_people: Mapped[int] = mapped_column(
        nullable=False,
    )
    per_person_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    user_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    user_share: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # Relationships
    expense: Mapped["Expense"] = relationship("Expense", back_populates="split")

    def __repr__(self) -> str:
        return f"<Split(total_people={self.total_people}, per_person={self.per_person_amount})>"


class Debt(Base):
    """Debt tracking for split payments and IOUs."""

    __tablename__ = "debts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    is_settled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    related_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="debts")
    related_expense: Mapped["Expense | None"] = relationship(
        "Expense",
        back_populates="debts",
    )

    def __repr__(self) -> str:
        return f"<Debt(person={self.person_name}, amount={self.amount}, direction={self.direction})>"
