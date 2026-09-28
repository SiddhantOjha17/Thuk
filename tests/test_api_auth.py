"""Tests for register/login/refresh — including refresh-token rotation.

The rotation tests matter because APIClient.swift had to add coalescing for
concurrent 401s specifically because a refresh token is single-use: reusing
an already-rotated token must fail, or a losing concurrent request silently
gets an invalid token back.
"""

import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email="user@example.com", password="password123", name="Test User"):
    return await client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )


async def test_register_returns_tokens(client):
    resp = await _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email_rejected(client):
    await _register(client, email="dupe@example.com")
    resp = await _register(client, email="dupe@example.com")
    assert resp.status_code == 409


async def test_login_success(client):
    await _register(client, email="login@example.com", password="password123")
    resp = await client.post(
        "/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_login_wrong_password_rejected(client):
    await _register(client, email="wrongpw@example.com", password="password123")
    resp = await client.post(
        "/auth/login", json={"email": "wrongpw@example.com", "password": "not-the-password"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_rejected(client):
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert resp.status_code == 401


async def test_refresh_issues_new_tokens(client):
    reg = await _register(client, email="refresh@example.com")
    old_refresh = reg.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"] != old_refresh


async def test_refresh_token_is_single_use(client):
    """A refresh token must not be usable twice — this is what the rotation
    coalescing in APIClient.swift exists to avoid tripping on concurrent requests."""
    reg = await _register(client, email="singleuse@example.com")
    old_refresh = reg.json()["refresh_token"]

    first = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200

    second = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert second.status_code == 401


async def test_refresh_with_garbage_token_rejected(client):
    resp = await client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401
