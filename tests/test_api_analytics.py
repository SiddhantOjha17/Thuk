"""Tests for the analytics summary endpoint, including the multi-currency flag."""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def _register_and_auth(client, email="analytics@example.com"):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_summary_totals_only_the_requested_currency(client):
    headers = await _register_and_auth(client)
    today = date.today().isoformat()

    await client.post(
        "/api/expenses", json={"amount": "100", "currency": "INR", "expense_date": today}, headers=headers
    )
    await client.post(
        "/api/expenses", json={"amount": "50", "currency": "USD", "expense_date": today}, headers=headers
    )

    resp = await client.get(
        "/api/analytics/summary",
        params={"start": today, "end": today, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 100
    assert body["currency"] == "INR"


async def test_summary_flags_other_currencies_not_silently_dropped(client):
    headers = await _register_and_auth(client, email="mixedcurrency@example.com")
    today = date.today().isoformat()

    await client.post(
        "/api/expenses", json={"amount": "100", "currency": "INR", "expense_date": today}, headers=headers
    )
    await client.post(
        "/api/expenses", json={"amount": "50", "currency": "USD", "expense_date": today}, headers=headers
    )

    resp = await client.get(
        "/api/analytics/summary",
        params={"start": today, "end": today, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["other_currencies"] == ["USD"]


async def test_summary_no_other_currencies_when_single_currency(client):
    headers = await _register_and_auth(client, email="singlecurrency@example.com")
    today = date.today().isoformat()

    await client.post(
        "/api/expenses", json={"amount": "100", "currency": "INR", "expense_date": today}, headers=headers
    )

    resp = await client.get(
        "/api/analytics/summary",
        params={"start": today, "end": today, "currency": "INR"},
        headers=headers,
    )
    assert resp.json()["other_currencies"] == []
