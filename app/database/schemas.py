"""Pydantic schemas for API request/response validation."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer

# Decimal fields serialized as JSON numbers (not strings) so iOS/JS can decode them
DecimalNumber = Annotated[
    Decimal,
    PlainSerializer(lambda x: float(x), return_type=float, when_used="json"),
]


# ── Auth ──────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── User ──────────────────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    created_at: datetime


# ── Category ──────────────────────────────────────────────────────────────────


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = None  # hex color, e.g. "#F97316"


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None
    is_default: bool


# ── Expense ───────────────────────────────────────────────────────────────────


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="INR", max_length=3)
    description: str | None = None
    category_id: uuid.UUID | None = None
    expense_date: date | None = None


class ExpenseUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=3)
    description: str | None = None
    category_id: uuid.UUID | None = None
    expense_date: date | None = None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: DecimalNumber
    currency: str
    description: str | None
    category_id: uuid.UUID | None
    source_type: str
    expense_date: date
    created_at: datetime
    category: CategoryResponse | None = None


# ── Budget ────────────────────────────────────────────────────────────────────


class BudgetUpdate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="INR", max_length=3)


class BudgetResponse(BaseModel):
    amount: DecimalNumber | None
    currency: str
    spent: DecimalNumber
    remaining: DecimalNumber | None
    percent_used: float | None


# ── Debt ──────────────────────────────────────────────────────────────────────


class DebtResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_name: str
    total: DecimalNumber
    currency: str
    direction: str   # "owes_me" | "i_owe"
    count: int       # number of unsettled debt records aggregated
    is_settled: bool = False


class DebtSummaryResponse(BaseModel):
    total_owed_to_me: DecimalNumber
    total_i_owe: DecimalNumber
    debts: list[DebtResponse]


# ── Analytics ─────────────────────────────────────────────────────────────────


class CategoryAmount(BaseModel):
    category_name: str
    amount: DecimalNumber
    color: str | None = None


class AnalyticsSummary(BaseModel):
    total: DecimalNumber
    currency: str
    count: int
    by_category: list[CategoryAmount]
    start_date: date
    end_date: date


class DailyAmount(BaseModel):
    date: date
    amount: DecimalNumber


class AnalyticsDaily(BaseModel):
    currency: str
    days: list[DailyAmount]
    start_date: date
    end_date: date


# ── Chat ──────────────────────────────────────────────────────────────────────


class ChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


class ChatResponse(BaseModel):
    response: str
    # Optional: populated when chat results in an expense being created/edited
    expense_id: uuid.UUID | None = None
