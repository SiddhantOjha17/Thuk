"""Tests for Redis based Memory Store."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.redis_store import store


@pytest.mark.asyncio
async def test_add_message():
    """Test adding message to history."""
    # pipeline() is a *sync* call that returns an async context manager
    mock_pipeline = AsyncMock()
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=False)

    mock_redis = MagicMock()  # MagicMock so pipeline() is sync
    mock_redis.pipeline.return_value = mock_pipeline

    with patch.object(store, "redis", mock_redis):
        await store.add_message("1234567890", "user", "Hello")

        mock_pipeline.rpush.assert_called_once_with(
            "thuk:hist:1234567890",
            json.dumps({"role": "user", "content": "Hello"}),
        )
        mock_pipeline.ltrim.assert_called_once_with("thuk:hist:1234567890", -10, -1)
        mock_pipeline.expire.assert_called_once_with("thuk:hist:1234567890", 86400)
        mock_pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_history():
    """Test getting history."""
    with patch.object(store, "redis") as mock_redis:
        mock_redis.lrange = AsyncMock(
            return_value=[
                json.dumps({"role": "user", "content": "hi"}),
                json.dumps({"role": "assistant", "content": "hello"}),
            ]
        )

        history = await store.get_history("1234567890")

        mock_redis.lrange.assert_called_once_with("thuk:hist:1234567890", -6, -1)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "hello"


@pytest.mark.asyncio
async def test_flags():
    """Test setting and getting flags."""
    with patch.object(store, "redis") as mock_redis:
        mock_redis.setex = AsyncMock()
        mock_redis.get = AsyncMock(return_value="true")
        mock_redis.delete = AsyncMock()

        # Set
        await store.set_flag("1234567890", "pending_delete", True, 60)
        mock_redis.setex.assert_called_once_with(
            "thuk:flag:1234567890:pending_delete", 60, "true"
        )

        # Get
        val = await store.get_flag("1234567890", "pending_delete")
        assert val is True

        # Delete
        await store.delete_flag("1234567890", "pending_delete")
        mock_redis.delete.assert_called_once_with("thuk:flag:1234567890:pending_delete")


@pytest.mark.asyncio
async def test_rate_limit_allowed():
    """Rate limit returns True when under the limit."""
    with patch.object(store, "redis") as mock_redis:
        # Lua script returns current count = 5, well under max_requests=20
        mock_redis.eval = AsyncMock(return_value=5)

        allowed = await store.check_rate_limit("12345", max_requests=20, window_secs=60)

        assert allowed is True
        mock_redis.eval.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    """Rate limit returns False when over the limit."""
    with patch.object(store, "redis") as mock_redis:
        # Lua script returns current count = 21, over max_requests=20
        mock_redis.eval = AsyncMock(return_value=21)

        allowed = await store.check_rate_limit("12345", max_requests=20, window_secs=60)

        assert allowed is False
