"""Recurring expense endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import crud
from app.database.base import get_db
from app.database.models import RecurringExpense, User
from app.database.schemas import RecurringExpenseCreate, RecurringExpenseResponse

router = APIRouter()


@router.get("", response_model=list[RecurringExpenseResponse])
async def list_recurring(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active recurring expenses."""
    result = await db.execute(
        select(RecurringExpense)
        .options(selectinload(RecurringExpense.category))
        .where(RecurringExpense.user_id == user.id, RecurringExpense.is_active == True)  # noqa: E712
        .order_by(RecurringExpense.description)
    )
    return result.scalars().all()


@router.post("", response_model=RecurringExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_recurring(
    body: RecurringExpenseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set up a new recurring expense."""
    recurring = await crud.create_recurring_expense(
        db,
        user_id=user.id,
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        cadence=body.cadence,
        category_id=body.category_id,
    )
    result = await db.execute(
        select(RecurringExpense)
        .options(selectinload(RecurringExpense.category))
        .where(RecurringExpense.id == recurring.id)
    )
    return result.scalar_one()


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_recurring(
    recurring_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop a recurring expense (keeps the expenses it already created)."""
    result = await db.execute(
        select(RecurringExpense).where(
            RecurringExpense.id == recurring_id, RecurringExpense.user_id == user.id
        )
    )
    recurring = result.scalar_one_or_none()
    if not recurring:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring expense not found")

    recurring.is_active = False
