"""Debts endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import crud
from app.database.base import get_db
from app.database.models import User
from app.database.schemas import DebtItemResponse, DebtPayment, DebtResponse, DebtSummaryResponse

router = APIRouter()


@router.get("", response_model=DebtSummaryResponse)
async def get_debts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated debt summary."""
    summary = await crud.get_debt_summary(db, user.id)
    debts = [
        DebtResponse(
            id=uuid.uuid4(),   # aggregated — no single ID
            person_name=p["person_name"],
            total=p["total"],
            currency=p["currency"],
            direction=p["direction"],
            count=p["count"],
        )
        for p in summary["aggregated"]
    ]
    return DebtSummaryResponse(
        total_owed_to_me=summary["total_owed_to_me"],
        total_i_owe=summary["total_i_owe"],
        debts=debts,
    )


@router.post("/{person_name}/settle", status_code=status.HTTP_200_OK)
async def settle_debts(
    person_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all debts with a person as settled."""
    count = await crud.settle_debts_by_person(db, user.id, person_name)
    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending debts found with {person_name}",
        )
    return {"settled": count, "person": person_name}


@router.get("/{person_name}/items", response_model=list[DebtItemResponse])
async def list_debt_items(
    person_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List a person's individual unsettled debts — use to pick one for a partial payment."""
    debts = await crud.get_unsettled_debts_by_person(db, user.id, person_name)
    return [
        DebtItemResponse(
            id=d.id,
            person_name=d.person_name,
            amount=d.amount,
            currency=d.currency,
            direction=d.direction,
            is_settled=d.is_settled,
            created_at=d.created_at,
            description=d.related_expense.description if d.related_expense else None,
        )
        for d in debts
    ]


@router.post("/items/{debt_id}/pay", response_model=DebtItemResponse)
async def pay_debt(
    debt_id: uuid.UUID,
    body: DebtPayment,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a payment (partial or full) against one specific debt, unambiguously by ID."""
    debt = await crud.get_debt_by_id(db, user.id, debt_id)
    if not debt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")

    debt = await crud.apply_partial_payment(db, debt, body.amount)
    return DebtItemResponse(
        id=debt.id,
        person_name=debt.person_name,
        amount=debt.amount,
        currency=debt.currency,
        direction=debt.direction,
        is_settled=debt.is_settled,
        created_at=debt.created_at,
        description=debt.related_expense.description if debt.related_expense else None,
    )
