"""API router — all mobile endpoints."""

from fastapi import APIRouter

from app.api import auth, chat, expenses, categories, budget, debts, analytics, export, me

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(me.router, tags=["me"])
router.include_router(chat.router, prefix="/api/chat", tags=["chat"])
router.include_router(expenses.router, prefix="/api/expenses", tags=["expenses"])
router.include_router(categories.router, prefix="/api/categories", tags=["categories"])
router.include_router(budget.router, prefix="/api/budget", tags=["budget"])
router.include_router(debts.router, prefix="/api/debts", tags=["debts"])
router.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
router.include_router(export.router, prefix="/api/export", tags=["export"])
