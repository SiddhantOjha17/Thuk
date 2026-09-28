"""Tests for the expense CRUD API, including cross-user isolation."""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


async def _register_and_auth(client, email="expenses@example.com"):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_list_expenses_requires_auth(client):
    resp = await client.get("/api/expenses")
    assert resp.status_code == 401


async def test_create_and_list_expense(client):
    headers = await _register_and_auth(client)

    create = await client.post(
        "/api/expenses",
        json={"amount": "150.50", "currency": "INR", "description": "Lunch"},
        headers=headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["amount"] == 150.50
    assert body["description"] == "Lunch"
    assert body["category_id"] is None

    listing = await client.get("/api/expenses", headers=headers)
    assert listing.status_code == 200
    ids = [e["id"] for e in listing.json()]
    assert body["id"] in ids


async def test_list_expenses_filters_by_date_range(client):
    headers = await _register_and_auth(client, email="daterange@example.com")

    today = date.today()
    old_date = (today - timedelta(days=30)).isoformat()

    await client.post(
        "/api/expenses",
        json={"amount": "10", "description": "old one", "expense_date": old_date},
        headers=headers,
    )
    recent = await client.post(
        "/api/expenses",
        json={"amount": "20", "description": "recent one"},
        headers=headers,
    )

    resp = await client.get(
        "/api/expenses",
        params={"start": today.isoformat()},
        headers=headers,
    )
    assert resp.status_code == 200
    descriptions = [e["description"] for e in resp.json()]
    assert "recent one" in descriptions
    assert "old one" not in descriptions
    assert recent.json()["id"] in [e["id"] for e in resp.json()]


async def test_update_expense(client):
    headers = await _register_and_auth(client, email="update@example.com")
    create = await client.post(
        "/api/expenses", json={"amount": "100", "description": "original"}, headers=headers
    )
    expense_id = create.json()["id"]

    resp = await client.put(
        f"/api/expenses/{expense_id}",
        json={"amount": "200", "description": "updated"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount"] == 200
    assert body["description"] == "updated"


async def test_delete_expense(client):
    headers = await _register_and_auth(client, email="delete@example.com")
    create = await client.post(
        "/api/expenses", json={"amount": "50", "description": "to delete"}, headers=headers
    )
    expense_id = create.json()["id"]

    resp = await client.delete(f"/api/expenses/{expense_id}", headers=headers)
    assert resp.status_code == 204

    listing = await client.get("/api/expenses", headers=headers)
    assert expense_id not in [e["id"] for e in listing.json()]


async def test_list_expenses_pagination(client):
    headers = await _register_and_auth(client, email="pagination@example.com")

    for i in range(5):
        await client.post(
            "/api/expenses", json={"amount": str(i + 1), "description": f"item {i}"}, headers=headers
        )

    first_page = await client.get(
        "/api/expenses", params={"limit": 2, "offset": 0}, headers=headers
    )
    second_page = await client.get(
        "/api/expenses", params={"limit": 2, "offset": 2}, headers=headers
    )
    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 2

    first_ids = {e["id"] for e in first_page.json()}
    second_ids = {e["id"] for e in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


async def test_list_expenses_search(client):
    headers = await _register_and_auth(client, email="search@example.com")

    await client.post(
        "/api/expenses", json={"amount": "10", "description": "coffee with friends"}, headers=headers
    )
    await client.post(
        "/api/expenses", json={"amount": "20", "description": "groceries"}, headers=headers
    )

    resp = await client.get("/api/expenses", params={"q": "coffee"}, headers=headers)
    assert resp.status_code == 200
    descriptions = [e["description"] for e in resp.json()]
    assert "coffee with friends" in descriptions
    assert "groceries" not in descriptions


async def test_cannot_access_another_users_expense(client):
    """A user must not be able to read, update, or delete another user's expense."""
    headers_a = await _register_and_auth(client, email="usera@example.com")
    headers_b = await _register_and_auth(client, email="userb@example.com")

    create = await client.post(
        "/api/expenses", json={"amount": "999", "description": "user A's expense"}, headers=headers_a
    )
    expense_id = create.json()["id"]

    listing_b = await client.get("/api/expenses", headers=headers_b)
    assert expense_id not in [e["id"] for e in listing_b.json()]

    update_attempt = await client.put(
        f"/api/expenses/{expense_id}", json={"amount": "1"}, headers=headers_b
    )
    assert update_attempt.status_code == 404

    delete_attempt = await client.delete(f"/api/expenses/{expense_id}", headers=headers_b)
    assert delete_attempt.status_code == 404
