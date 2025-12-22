"""Pydantic schemas for request/response validation."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ============== User Schemas ==============


class UserBase(BaseModel):
    """Base user schema."""

    phone_number: str


class UserCreate(UserBase):
    """Schema for creating a user."""

    pass


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    has_api_key: bool = False

    @classmethod
    def from_orm_with_key_check(cls, user) -> "UserResponse":
        """Create response with API key check."""
        return cls(
            id=user.id,
            phone_number=user.phone_number,
            created_at=user.created_at,
            has_api_key=user.openai_api_key_encrypted is not None,
        )


# ============== Category Schemas ==============


class CategoryBase(BaseModel):
    """Base category schema."""

    name: str
    icon: str | None = None


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""

    is_default: bool = False


class CategoryResponse(CategoryBase):
    """Schema for category response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_default: bool


# ============== Expense Schemas ==============


class ExpenseBase(BaseModel):
    """Base expense schema."""

    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    description: str | None = None
    expense_date: date | None = None


class ExpenseCreate(ExpenseBase):
    """Schema for creating an expense."""

    category_id: uuid.UUID | None = None
    source_type: str = "text"


class ExpenseResponse(ExpenseBase):
    """Schema for expense response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    source_type: str
    created_at: datetime


class ExpenseWithCategory(ExpenseResponse):
    """Expense with category details."""

    category: CategoryResponse | None = None


# ============== Split Schemas ==============


class SplitBase(BaseModel):
    """Base split schema."""

    total_people: int = Field(gt=1)
    user_paid: Decimal = Field(ge=0)


class SplitCreate(SplitBase):
    """Schema for creating a split."""

    expense_id: uuid.UUID


class SplitResponse(SplitBase):
    """Schema for split response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expense_id: uuid.UUID
    per_person_amount: Decimal
    user_share: Decimal


# ============== Debt Schemas ==============


class DebtBase(BaseModel):
    """Base debt schema."""

    person_name: str
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    direction: str  # "owes_me" or "i_owe"


class DebtCreate(DebtBase):
    """Schema for creating a debt."""

    related_expense_id: uuid.UUID | None = None


class DebtResponse(DebtBase):
    """Schema for debt response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_settled: bool
    created_at: datetime


class DebtSummary(BaseModel):
    """Summary of debts for a user."""

    total_owed_to_me: Decimal = Decimal("0")
    total_i_owe: Decimal = Decimal("0")
    debts: list[DebtResponse] = []


# ============== Query Schemas ==============


class ExpenseQuery(BaseModel):
    """Schema for querying expenses."""

    start_date: date | None = None
    end_date: date | None = None
    category_id: uuid.UUID | None = None
    currency: str | None = None


class ExpenseSummary(BaseModel):
    """Summary of expenses for a time period."""

    total_amount: Decimal = Decimal("0")
    currency: str = "INR"
    count: int = 0
    by_category: dict[str, Decimal] = {}
    start_date: date | None = None
    end_date: date | None = None


# ============== Message Schemas ==============


class WhatsAppMessage(BaseModel):
    """Incoming WhatsApp message."""

    from_number: str
    body: str | None = None
    media_url: str | None = None
    media_content_type: str | None = None
    num_media: int = 0


class AgentResponse(BaseModel):
    """Response from the agent system."""

    message: str
    expense_id: uuid.UUID | None = None
    action_taken: str | None = None
