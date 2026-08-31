"""Debts endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import crud
from app.database.base import get_db
from app.database.models import DebtDirection, User
from app.database.schemas import DebtResponse, DebtSummaryResponse

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
