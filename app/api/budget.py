"""Budget endpoints."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.budget_agent import BudgetAgent
from app.auth.dependencies import get_current_user
from app.database.base import get_db
from app.database.models import User
from app.database.schemas import BudgetResponse, BudgetUpdate

router = APIRouter()
_agent = BudgetAgent()


@router.get("", response_model=BudgetResponse)
async def get_budget(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = user.preferences or {}
    budget_dict = prefs.get("monthly_budget")

    if not budget_dict:
        return BudgetResponse(
            amount=None, currency="INR", spent=Decimal("0"),
            remaining=None, percent_used=None,
        )

    budget_amount = Decimal(budget_dict["amount"])
    currency = budget_dict.get("currency", "INR")
    spent = await _agent._get_current_month_spend(db, user.id, currency)
    remaining = budget_amount - spent
    percent = float((spent / budget_amount) * 100) if budget_amount > 0 else 0.0

    return BudgetResponse(
        amount=budget_amount,
        currency=currency,
        spent=spent,
        remaining=remaining,
        percent_used=percent,
    )


@router.put("", response_model=BudgetResponse)
async def set_budget(
    body: BudgetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _agent.set_budget(db, user, body.amount, body.currency)
    # Return the updated status
    spent = await _agent._get_current_month_spend(db, user.id, body.currency)
    remaining = body.amount - spent
    percent = float((spent / body.amount) * 100) if body.amount > 0 else 0.0

    return BudgetResponse(
        amount=body.amount,
        currency=body.currency,
        spent=spent,
        remaining=remaining,
        percent_used=percent,
    )
