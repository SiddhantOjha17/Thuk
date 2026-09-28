"""Tests for partial debt repayment: crud logic, the manual REST path, and the
chat disambiguation flow when a person has more than one unsettled debt."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.split_agent import SplitAgent
from app.database import crud
from app.database.models import DebtDirection
from app.memory.redis_store import store

pytestmark = pytest.mark.asyncio


async def _register_and_auth(client, email="debts@example.com"):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _make_user_and_debt(client, db_session, email, amount="500"):
    headers = await _register_and_auth(client, email=email)
    me = await client.get("/api/me", headers=headers)
    user_id = me.json()["id"]
    debt = await crud.create_debt(
        db_session,
        user_id=user_id,
        person_name="Rahul",
        amount=Decimal(amount),
        currency="INR",
        direction=DebtDirection.OWES_ME,
    )
    return headers, user_id, debt


# ── CRUD-level ───────────────────────────────────────────────────────────────


async def test_apply_partial_payment_reduces_amount(client, db_session):
    _, _, debt = await _make_user_and_debt(client, db_session, "partial@example.com", amount="500")

    updated = await crud.apply_partial_payment(db_session, debt, Decimal("200"))
    assert updated.amount == Decimal("300")
    assert updated.is_settled is False


async def test_apply_partial_payment_settles_on_full_amount(client, db_session):
    _, _, debt = await _make_user_and_debt(client, db_session, "full@example.com", amount="500")

    updated = await crud.apply_partial_payment(db_session, debt, Decimal("500"))
    assert updated.amount == Decimal("0")
    assert updated.is_settled is True


async def test_apply_partial_payment_clamps_overpayment(client, db_session):
    _, _, debt = await _make_user_and_debt(client, db_session, "over@example.com", amount="500")

    updated = await crud.apply_partial_payment(db_session, debt, Decimal("9999"))
    assert updated.amount == Decimal("0")
    assert updated.is_settled is True


# ── Manual REST path (unambiguous — targets a specific debt id) ─────────────


async def test_list_debt_items_and_pay_one_directly(client, db_session):
    headers, _, debt = await _make_user_and_debt(client, db_session, "manualpay@example.com", amount="500")

    listing = await client.get("/api/debts/Rahul/items", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == str(debt.id)

    pay = await client.post(
        f"/api/debts/items/{debt.id}/pay", json={"amount": "200"}, headers=headers
    )
    assert pay.status_code == 200
    assert pay.json()["amount"] == 300
    assert pay.json()["is_settled"] is False


async def test_pay_nonexistent_debt_404s(client):
    headers = await _register_and_auth(client, email="nodebtpay@example.com")
    resp = await client.post(
        "/api/debts/items/00000000-0000-0000-0000-000000000000/pay",
        json={"amount": "100"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_cannot_pay_another_users_debt(client, db_session):
    _, _, debt = await _make_user_and_debt(client, db_session, "victim@example.com", amount="500")
    other_headers = await _register_and_auth(client, email="attacker@example.com")

    resp = await client.post(
        f"/api/debts/items/{debt.id}/pay", json={"amount": "100"}, headers=other_headers
    )
    assert resp.status_code == 404


# ── Chat flow: ambiguous case asks which debt instead of guessing ───────────


def _mock_redis():
    """Patch app.memory.redis_store.store.redis with an in-memory fake sufficient
    for set_flag/get_flag/delete_flag (mirrors the pattern in test_memory.py)."""
    fake = {}

    mock_redis = MagicMock()
    mock_redis.setex = AsyncMock(side_effect=lambda k, ttl, v: fake.__setitem__(k, v))
    mock_redis.get = AsyncMock(side_effect=lambda k: fake.get(k))
    mock_redis.delete = AsyncMock(side_effect=lambda k: fake.pop(k, None))
    return mock_redis


async def test_settle_with_amount_and_single_debt_applies_directly(client, db_session):
    _, user_id, debt = await _make_user_and_debt(client, db_session, "singledebt@example.com", amount="500")

    with patch.object(store, "redis", _mock_redis()):
        agent = SplitAgent()
        user = MagicMock(id=user_id)
        response = await agent.settle_debt(db_session, user, "Rahul", amount=Decimal("200"))

    assert "Recorded" in response
    await db_session.refresh(debt)
    assert debt.amount == Decimal("300")


async def test_settle_with_amount_and_multiple_debts_asks_which_one(client, db_session):
    headers = await _register_and_auth(client, email="multidebt@example.com")
    me = await client.get("/api/me", headers=headers)
    user_id = me.json()["id"]

    await crud.create_debt(
        db_session, user_id=user_id, person_name="Rahul", amount=Decimal("300"),
        currency="INR", direction=DebtDirection.OWES_ME,
    )
    await crud.create_debt(
        db_session, user_id=user_id, person_name="Rahul", amount=Decimal("200"),
        currency="INR", direction=DebtDirection.OWES_ME,
    )

    with patch.object(store, "redis", _mock_redis()):
        agent = SplitAgent()
        user = MagicMock(id=user_id)
        response = await agent.settle_debt(db_session, user, "Rahul", amount=Decimal("100"))

        assert "2 separate debts" in response
        assert "1." in response and "2." in response

        # Now resolve by picking the first one
        resolved = await agent.resolve_pending_settle(db_session, user, "1")
        assert "Recorded" in resolved
