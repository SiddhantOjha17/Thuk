"""Tests for recurring expenses: date advancement, lazy materialization, and the REST API."""

from datetime import date, timedelta
from decimal import Decimal

from app.database import crud
from app.database.crud import _advance_date  # unit-testing the internal date helper directly


async def _register_and_auth(client, email="recurring@example.com"):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_advance_date_weekly():
    assert _advance_date(date(2026, 1, 1), "weekly") == date(2026, 1, 8)


def test_advance_date_monthly_clamps_short_month():
    # Jan 31 -> Feb has only 28 days in 2026 (not a leap year)
    assert _advance_date(date(2026, 1, 31), "monthly") == date(2026, 2, 28)


def test_advance_date_monthly_rolls_year():
    assert _advance_date(date(2026, 12, 15), "monthly") == date(2027, 1, 15)


def test_advance_date_yearly_clamps_leap_day():
    assert _advance_date(date(2024, 2, 29), "yearly") == date(2025, 2, 28)


async def test_materialize_creates_expense_and_advances_next_run_date(client, db_session):
    headers = await _register_and_auth(client)
    me = await client.get("/api/me", headers=headers)
    user_id = me.json()["id"]

    recurring = await crud.create_recurring_expense(
        db_session,
        user_id=user_id,
        amount=Decimal("500"),
        currency="INR",
        description="Netflix",
        cadence="monthly",
        start_date=date.today() - timedelta(days=1),
    )

    created = await crud.materialize_due_recurring_expenses(db_session, user_id)
    assert len(created) == 1
    assert created[0].description == "Netflix"
    assert created[0].amount == Decimal("500")

    await db_session.refresh(recurring)
    assert recurring.next_run_date > date.today()


async def test_materialize_catches_up_multiple_missed_periods(client, db_session):
    headers = await _register_and_auth(client, email="catchup@example.com")
    me = await client.get("/api/me", headers=headers)
    user_id = me.json()["id"]

    await crud.create_recurring_expense(
        db_session,
        user_id=user_id,
        amount=Decimal("100"),
        currency="INR",
        description="Weekly gym",
        cadence="weekly",
        start_date=date.today() - timedelta(weeks=3),
    )

    created = await crud.materialize_due_recurring_expenses(db_session, user_id)
    # Due at -21d, -14d, -7d, and today itself = 4 occurrences
    assert len(created) == 4


async def test_materialize_is_a_noop_when_nothing_due(client, db_session):
    headers = await _register_and_auth(client, email="notdue@example.com")
    me = await client.get("/api/me", headers=headers)
    user_id = me.json()["id"]

    await crud.create_recurring_expense(
        db_session,
        user_id=user_id,
        amount=Decimal("100"),
        currency="INR",
        description="Future rent",
        cadence="monthly",
        start_date=date.today() + timedelta(days=5),
    )

    created = await crud.materialize_due_recurring_expenses(db_session, user_id)
    assert created == []


async def test_get_current_user_materializes_on_request(client, db_session):
    """A due recurring expense should show up in /api/expenses without any
    explicit materialization call — get_current_user does it automatically."""
    headers = await _register_and_auth(client, email="autoflow@example.com")
    me = await client.get("/api/me", headers=headers)
    user_id = me.json()["id"]

    await crud.create_recurring_expense(
        db_session,
        user_id=user_id,
        amount=Decimal("250"),
        currency="INR",
        description="Spotify",
        cadence="monthly",
        start_date=date.today(),
    )

    resp = await client.get("/api/expenses", headers=headers)
    descriptions = [e["description"] for e in resp.json()]
    assert "Spotify" in descriptions


async def test_create_list_and_stop_recurring_via_api(client):
    headers = await _register_and_auth(client, email="restapi@example.com")

    create = await client.post(
        "/api/recurring",
        json={"amount": "999", "description": "Rent", "cadence": "monthly"},
        headers=headers,
    )
    assert create.status_code == 201
    recurring_id = create.json()["id"]
    assert create.json()["cadence"] == "monthly"

    listing = await client.get("/api/recurring", headers=headers)
    assert listing.status_code == 200
    assert any(r["id"] == recurring_id for r in listing.json())

    stop = await client.delete(f"/api/recurring/{recurring_id}", headers=headers)
    assert stop.status_code == 204

    listing_after = await client.get("/api/recurring", headers=headers)
    assert all(r["id"] != recurring_id for r in listing_after.json())


async def test_cannot_stop_another_users_recurring_expense(client):
    headers_a = await _register_and_auth(client, email="rec_usera@example.com")
    headers_b = await _register_and_auth(client, email="rec_userb@example.com")

    create = await client.post(
        "/api/recurring",
        json={"amount": "50", "description": "Gym", "cadence": "monthly"},
        headers=headers_a,
    )
    recurring_id = create.json()["id"]

    resp = await client.delete(f"/api/recurring/{recurring_id}", headers=headers_b)
    assert resp.status_code == 404
