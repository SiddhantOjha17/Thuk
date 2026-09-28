"""Tests for the CSV export endpoint's optional date range."""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


async def _register_and_auth(client, email="export@example.com"):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_export_csv_includes_everything_by_default(client):
    headers = await _register_and_auth(client)
    old_date = (date.today() - timedelta(days=100)).isoformat()

    await client.post(
        "/api/expenses", json={"amount": "10", "description": "old", "expense_date": old_date}, headers=headers
    )
    await client.post(
        "/api/expenses", json={"amount": "20", "description": "recent"}, headers=headers
    )

    resp = await client.get("/api/export/csv", headers=headers)
    assert resp.status_code == 200
    assert "old" in resp.text
    assert "recent" in resp.text


async def test_export_csv_respects_date_range(client):
    headers = await _register_and_auth(client, email="exportrange@example.com")
    today = date.today()
    old_date = (today - timedelta(days=100)).isoformat()

    await client.post(
        "/api/expenses", json={"amount": "10", "description": "old", "expense_date": old_date}, headers=headers
    )
    await client.post(
        "/api/expenses", json={"amount": "20", "description": "recent"}, headers=headers
    )

    resp = await client.get(
        "/api/export/csv", params={"start": today.isoformat()}, headers=headers
    )
    assert resp.status_code == 200
    assert "old" not in resp.text
    assert "recent" in resp.text
