"""Expenses CRUD endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database.base import get_db
from app.database.models import Expense, User
from app.database.schemas import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    start: date | None = Query(None),
    end: date | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    limit: int = Query(default=50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List expenses with optional filters."""
    from app.database import crud
    expenses = await crud.get_user_expenses(
        db,
        user_id=user.id,
        start_date=start,
        end_date=end,
        category_id=category_id,
        limit=limit,
    )
    return expenses


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    body: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add an expense, optionally split with other people."""
    from app.database import crud
    from app.database.models import SourceType

    if body.split_count or body.split_people:
        expense = await crud.create_split_expense(
            db,
            user_id=user.id,
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            category_id=body.category_id,
            source_type=SourceType.TEXT,
            expense_date=body.expense_date or date.today(),
            split_count=body.split_count,
            split_people=body.split_people,
        )
    else:
        expense = await crud.create_expense(
            db,
            user_id=user.id,
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            category_id=body.category_id,
            source_type=SourceType.TEXT,
            expense_date=body.expense_date or date.today(),
        )
    # Reload with category
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.category))
        .where(Expense.id == expense.id)
    )
    return result.scalar_one()


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpenseUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update any field of an expense."""
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.category))
        .where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    if body.amount is not None:
        expense.amount = body.amount
    if body.currency is not None:
        expense.currency = body.currency
    if body.description is not None:
        expense.description = body.description
    if body.category_id is not None:
        expense.category_id = body.category_id
    if body.expense_date is not None:
        expense.expense_date = body.expense_date

    await db.flush()

    # Reload with updated category relationship
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.category))
        .where(Expense.id == expense_id)
    )
    return result.scalar_one()


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an expense."""
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    await db.delete(expense)
