"""Database CRUD operations."""

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Category,
    Debt,
    DebtDirection,
    Expense,
    RecurringExpense,
    SourceType,
    Split,
    User,
)

# ============== User / Auth Operations ==============


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get user by email address."""
    result = await db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Get user by primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, name: str, email: str, password_hash: str) -> User:
    """Create a new user and seed default categories."""
    user = User(name=name, email=email.lower(), password_hash=password_hash)
    db.add(user)
    await db.flush()

    default_categories = [
        ("Food",          "#F97316"),
        ("Transport",     "#38BDF8"),
        ("Shopping",      "#A78BFA"),
        ("Bills",         "#FBBF24"),
        ("Entertainment", "#F472B6"),
        ("Health",        "#34D399"),
        ("Other",         "#9CA3AF"),
    ]
    for name_, color in default_categories:
        db.add(Category(user_id=user.id, name=name_, color=color, is_default=True))

    await db.flush()
    return user


# ── Refresh tokens ────────────────────────────────────────────────────────────


async def store_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at,
) -> None:
    from app.database.models import RefreshToken
    db.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    await db.flush()


async def get_refresh_token(db: AsyncSession, token_hash: str):
    from app.database.models import RefreshToken
    now = datetime.now(UTC)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token_hash: str) -> None:
    from app.database.models import RefreshToken
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token:
        await db.delete(token)
        await db.flush()


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
    color: str | None = None,
) -> Category:
    """Create a new category for a user."""
    category = Category(
        user_id=user_id,
        name=name,
        color=color,
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
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Expense]:
    """Get expenses for a user with optional filters, newest first."""
    query = (
        select(Expense)
        .options(selectinload(Expense.category))
        .outerjoin(Category, Expense.category_id == Category.id)
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
    if search:
        like = f"%{search}%"
        query = query.where(
            Expense.description.ilike(like) | Category.name.ilike(like)
        )

    query = (
        query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

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
        .outerjoin(Category, Expense.category_id == Category.id)
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
    by_category = {row.name or "Others": row.total for row in cat_result.all()}

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


async def create_split_expense(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    description: str | None,
    category_id: uuid.UUID | None,
    source_type: SourceType,
    expense_date: date | None,
    split_count: int | None,
    split_people: list[str] | None,
) -> Expense:
    """Create an expense split across multiple people, plus debt records for named participants.

    `amount` is the total amount paid, not the user's share. The expense is recorded
    at the user's share only; the difference is tracked as debts owed by named
    participants (if any were given).
    """
    count = split_count or (len(split_people or []) + 1)
    per_person = amount / Decimal(count)
    user_share = per_person

    expense = await create_expense(
        db=db,
        user_id=user_id,
        amount=user_share,
        currency=currency,
        description=description,
        category_id=category_id,
        source_type=source_type,
        expense_date=expense_date,
        metadata={
            "original_amount": str(amount),
            "split_count": count,
        },
    )

    await create_split(
        db=db,
        expense_id=expense.id,
        user_id=user_id,
        total_people=count,
        user_paid=amount,
        total_amount=amount,
    )

    if split_people:
        for person_name in split_people:
            await create_debt(
                db=db,
                user_id=user_id,
                person_name=person_name,
                amount=per_person,
                currency=currency,
                direction=DebtDirection.OWES_ME,
                related_expense_id=expense.id,
            )

    return expense


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
    """Get debt summary aggregated by person."""
    debts = await get_user_debts(db, user_id, settled=False)

    total_owed_to_me = Decimal("0")
    total_i_owe = Decimal("0")

    # Aggregate per person: {name: {direction, total, currency, count}}
    aggregated: dict[str, dict] = {}
    for debt in debts:
        key = debt.person_name.lower()
        if key not in aggregated:
            aggregated[key] = {
                "person_name": debt.person_name,
                "direction": debt.direction,
                "total": Decimal("0"),
                "currency": debt.currency,
                "count": 0,
            }
        aggregated[key]["total"] += debt.amount
        aggregated[key]["count"] += 1

        if debt.direction == DebtDirection.OWES_ME.value:
            total_owed_to_me += debt.amount
        else:
            total_i_owe += debt.amount

    return {
        "total_owed_to_me": total_owed_to_me,
        "total_i_owe": total_i_owe,
        "aggregated": list(aggregated.values()),
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


# ============== Recurring Expense Operations ==============

VALID_CADENCES = ("weekly", "monthly", "yearly")


def _advance_date(d: date, cadence: str) -> date:
    """Move a date forward by one cadence period, clamping day-of-month overflow
    (e.g. rent due the 31st advances to the last day of a shorter next month)."""
    if cadence == "weekly":
        return d + timedelta(days=7)
    if cadence == "yearly":
        try:
            return d.replace(year=d.year + 1)
        except ValueError:
            # Feb 29 on a non-leap year
            return d.replace(year=d.year + 1, day=28)
    # monthly (default/fallback)
    month = d.month + 1
    year = d.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


async def create_recurring_expense(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    description: str,
    cadence: str,
    category_id: uuid.UUID | None = None,
    start_date: date | None = None,
) -> RecurringExpense:
    """Create a new recurring expense rule, starting from `start_date` (default today)."""
    recurring = RecurringExpense(
        user_id=user_id,
        amount=amount,
        currency=currency,
        description=description,
        cadence=cadence if cadence in VALID_CADENCES else "monthly",
        category_id=category_id,
        next_run_date=start_date or date.today(),
        is_active=True,
    )
    db.add(recurring)
    await db.flush()
    return recurring


async def get_user_recurring_expenses(
    db: AsyncSession, user_id: uuid.UUID, active_only: bool = True
) -> list[RecurringExpense]:
    """List a user's recurring expense rules."""
    query = select(RecurringExpense).where(RecurringExpense.user_id == user_id)
    if active_only:
        query = query.where(RecurringExpense.is_active == True)  # noqa: E712
    query = query.order_by(RecurringExpense.description)
    result = await db.execute(query)
    return list(result.scalars().all())


async def find_recurring_expenses_by_description(
    db: AsyncSession, user_id: uuid.UUID, name: str
) -> list[RecurringExpense]:
    """Fuzzy-match active recurring expenses by description (e.g. 'netflix' -> 'Netflix')."""
    result = await db.execute(
        select(RecurringExpense).where(
            RecurringExpense.user_id == user_id,
            RecurringExpense.is_active == True,  # noqa: E712
            RecurringExpense.description.ilike(f"%{name}%"),
        )
    )
    return list(result.scalars().all())


async def deactivate_recurring_expense(
    db: AsyncSession, recurring_id: uuid.UUID
) -> RecurringExpense | None:
    """Stop a recurring expense (soft delete — keeps history of what it already created)."""
    result = await db.execute(
        select(RecurringExpense).where(RecurringExpense.id == recurring_id)
    )
    recurring = result.scalar_one_or_none()
    if recurring:
        recurring.is_active = False
        await db.flush()
    return recurring


async def materialize_due_recurring_expenses(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Expense]:
    """Create real Expense rows for every period a recurring expense has missed
    since it was last materialized, then advance `next_run_date` past today.

    Called lazily from `get_current_user` on every authenticated request rather
    than via a standing scheduler, since free-tier hosting scales to zero and
    would kill a scheduler anyway.
    """
    today = date.today()
    result = await db.execute(
        select(RecurringExpense).where(
            RecurringExpense.user_id == user_id,
            RecurringExpense.is_active == True,  # noqa: E712
            RecurringExpense.next_run_date <= today,
        )
    )
    due = list(result.scalars().all())
    created: list[Expense] = []
    for recurring in due:
        # Safety cap: a malformed cadence should never loop indefinitely.
        for _ in range(24):
            if recurring.next_run_date > today:
                break
            expense = await create_expense(
                db=db,
                user_id=user_id,
                amount=recurring.amount,
                currency=recurring.currency,
                description=recurring.description,
                category_id=recurring.category_id,
                source_type=SourceType.TEXT,
                expense_date=recurring.next_run_date,
                metadata={"recurring_expense_id": str(recurring.id)},
            )
            created.append(expense)
            recurring.next_run_date = _advance_date(recurring.next_run_date, recurring.cadence)
    if created:
        await db.flush()
    return created
