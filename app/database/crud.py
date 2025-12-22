"""Database CRUD operations."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Category, Debt, DebtDirection, Expense, Split, SourceType, User


# ============== User Operations ==============


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> User | None:
    """Get user by phone number."""
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, phone_number: str) -> User:
    """Create a new user and initialize default categories."""
    user = User(phone_number=phone_number)
    db.add(user)
    await db.flush()

    # Create default categories
    default_categories = [
        ("Food", None),
        ("Transport", None),
        ("Shopping", None),
        ("Bills", None),
        ("Entertainment", None),
        ("Health", None),
        ("Other", None),
    ]

    for name, icon in default_categories:
        category = Category(
            user_id=user.id,
            name=name,
            icon=icon,
            is_default=True,
        )
        db.add(category)

    await db.flush()
    return user


async def update_user_api_key(
    db: AsyncSession, user_id: uuid.UUID, encrypted_key: str
) -> User | None:
    """Update user's encrypted API key."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.openai_api_key_encrypted = encrypted_key
        await db.flush()
    return user


# ============== Category Operations ==============


async def get_user_categories(db: AsyncSession, user_id: uuid.UUID) -> list[Category]:
    """Get all categories for a user."""
    result = await db.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.name)
    )
    return list(result.scalars().all())


async def get_category_by_name(
    db: AsyncSession, user_id: uuid.UUID, name: str
) -> Category | None:
    """Get category by name for a user."""
    result = await db.execute(
        select(Category).where(
            and_(
                Category.user_id == user_id,
                func.lower(Category.name) == name.lower(),
            )
        )
    )
    return result.scalar_one_or_none()


async def create_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    icon: str | None = None,
) -> Category:
    """Create a new category for a user."""
    category = Category(
        user_id=user_id,
        name=name,
        icon=icon,
        is_default=False,
    )
    db.add(category)
    await db.flush()
    return category


# ============== Expense Operations ==============


async def create_expense(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: Decimal,
    currency: str = "INR",
    description: str | None = None,
    category_id: uuid.UUID | None = None,
    source_type: SourceType = SourceType.TEXT,
    expense_date: date | None = None,
    metadata: dict | None = None,
) -> Expense:
    """Create a new expense."""
    expense = Expense(
        user_id=user_id,
        amount=amount,
        currency=currency,
        description=description,
        category_id=category_id,
        source_type=source_type.value,
        expense_date=expense_date or date.today(),
        metadata_=metadata or {},
    )
    db.add(expense)
    await db.flush()
    return expense


async def get_user_expenses(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: uuid.UUID | None = None,
    currency: str | None = None,
    limit: int = 50,
) -> list[Expense]:
    """Get expenses for a user with optional filters."""
    query = (
        select(Expense)
        .options(selectinload(Expense.category))
        .where(Expense.user_id == user_id)
    )

    if start_date:
        query = query.where(Expense.expense_date >= start_date)
    if end_date:
        query = query.where(Expense.expense_date <= end_date)
    if category_id:
        query = query.where(Expense.category_id == category_id)
    if currency:
        query = query.where(Expense.currency == currency)

    query = query.order_by(Expense.expense_date.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_expense_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    currency: str = "INR",
) -> dict:
    """Get expense summary for a user."""
    query = select(
        func.sum(Expense.amount).label("total"),
        func.count().label("count"),
    ).where(
        and_(
            Expense.user_id == user_id,
            Expense.currency == currency,
        )
    )

    if start_date:
        query = query.where(Expense.expense_date >= start_date)
    if end_date:
        query = query.where(Expense.expense_date <= end_date)

    result = await db.execute(query)
    row = result.one()

    # Get by category
    cat_query = (
        select(
            Category.name,
            func.sum(Expense.amount).label("total"),
        )
        .join(Category, Expense.category_id == Category.id)
        .where(
            and_(
                Expense.user_id == user_id,
                Expense.currency == currency,
            )
        )
        .group_by(Category.name)
    )

    if start_date:
        cat_query = cat_query.where(Expense.expense_date >= start_date)
    if end_date:
        cat_query = cat_query.where(Expense.expense_date <= end_date)

    cat_result = await db.execute(cat_query)
    by_category = {row.name: row.total for row in cat_result.all()}

    return {
        "total_amount": row.total or Decimal("0"),
        "count": row.count,
        "by_category": by_category,
        "currency": currency,
        "start_date": start_date,
        "end_date": end_date,
    }


async def delete_last_expense(db: AsyncSession, user_id: uuid.UUID) -> Expense | None:
    """Delete the most recent expense for a user."""
    result = await db.execute(
        select(Expense)
        .where(Expense.user_id == user_id)
        .order_by(Expense.created_at.desc())
        .limit(1)
    )
    expense = result.scalar_one_or_none()
    if expense:
        await db.delete(expense)
        await db.flush()
    return expense


# ============== Split Operations ==============


async def create_split(
    db: AsyncSession,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
    total_people: int,
    user_paid: Decimal,
    total_amount: Decimal,
) -> Split:
    """Create a split for an expense."""
    per_person = total_amount / total_people
    user_share = per_person

    split = Split(
        expense_id=expense_id,
        user_id=user_id,
        total_people=total_people,
        per_person_amount=per_person,
        user_paid=user_paid,
        user_share=user_share,
    )
    db.add(split)
    await db.flush()
    return split


# ============== Debt Operations ==============


async def create_debt(
    db: AsyncSession,
    user_id: uuid.UUID,
    person_name: str,
    amount: Decimal,
    currency: str,
    direction: DebtDirection,
    related_expense_id: uuid.UUID | None = None,
) -> Debt:
    """Create a new debt record."""
    debt = Debt(
        user_id=user_id,
        person_name=person_name,
        amount=amount,
        currency=currency,
        direction=direction.value,
        related_expense_id=related_expense_id,
    )
    db.add(debt)
    await db.flush()
    return debt


async def get_user_debts(
    db: AsyncSession,
    user_id: uuid.UUID,
    settled: bool | None = None,
) -> list[Debt]:
    """Get all debts for a user."""
    query = select(Debt).where(Debt.user_id == user_id)
    if settled is not None:
        query = query.where(Debt.is_settled == settled)
    query = query.order_by(Debt.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_debt_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get debt summary for a user."""
    debts = await get_user_debts(db, user_id, settled=False)

    total_owed_to_me = Decimal("0")
    total_i_owe = Decimal("0")

    for debt in debts:
        if debt.direction == DebtDirection.OWES_ME.value:
            total_owed_to_me += debt.amount
        else:
            total_i_owe += debt.amount

    return {
        "total_owed_to_me": total_owed_to_me,
        "total_i_owe": total_i_owe,
        "debts": debts,
    }


async def settle_debt(db: AsyncSession, debt_id: uuid.UUID) -> Debt | None:
    """Mark a debt as settled."""
    result = await db.execute(select(Debt).where(Debt.id == debt_id))
    debt = result.scalar_one_or_none()
    if debt:
        debt.is_settled = True
        await db.flush()
    return debt


async def settle_debts_by_person(
    db: AsyncSession, user_id: uuid.UUID, person_name: str
) -> int:
    """Settle all debts with a specific person."""
    result = await db.execute(
        select(Debt).where(
            and_(
                Debt.user_id == user_id,
                func.lower(Debt.person_name) == person_name.lower(),
                Debt.is_settled == False,  # noqa: E712
            )
        )
    )
    debts = result.scalars().all()
    count = 0
    for debt in debts:
        debt.is_settled = True
        count += 1
    await db.flush()
    return count
