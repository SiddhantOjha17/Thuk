"""Tests for Redis based Memory Store."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.memory.redis_store import store


@pytest.mark.asyncio
async def test_add_message():
    """Test adding message to history."""
    with patch.object(store, 'redis', new_callable=AsyncMock) as mock_redis:
        # We need to mock the pipeline context manager
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
        
        await store.add_message("1234567890", "user", "Hello")
        
        mock_pipeline.rpush.assert_called_once_with(
            "thuk:hist:1234567890", 
            json.dumps({"role": "user", "content": "Hello"})
        )
        mock_pipeline.ltrim.assert_called_once_with("thuk:hist:1234567890", -10, -1)
        mock_pipeline.expire.assert_called_once_with("thuk:hist:1234567890", 86400)
        mock_pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_history():
    """Test getting history."""
    with patch.object(store, 'redis', new_callable=AsyncMock) as mock_redis:
        mock_redis.lrange.return_value = [
            json.dumps({"role": "user", "content": "hi"}),
            json.dumps({"role": "assistant", "content": "hello"}),
        ]
        
        history = await store.get_history("1234567890")
        
        mock_redis.lrange.assert_called_once_with("thuk:hist:1234567890", -6, -1)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "hello"


@pytest.mark.asyncio
async def test_flags():
    """Test setting and getting flags."""
    with patch.object(store, 'redis', new_callable=AsyncMock) as mock_redis:
        # Set
        await store.set_flag("1234567890", "pending_delete", True, 60)
        mock_redis.setex.assert_called_once_with("thuk:flag:1234567890:pending_delete", 60, "true")
        
        # Get
        mock_redis.get.return_value = "true"
        val = await store.get_flag("1234567890", "pending_delete")
        assert val is True
        
        # Delete
        await store.delete_flag("1234567890", "pending_delete")
        mock_redis.delete.assert_called_once_with("thuk:flag:1234567890:pending_delete")


@pytest.mark.asyncio
async def test_rate_limit():
    """Test rate limiting logic."""
    with patch.object(store, 'redis', new_callable=AsyncMock) as mock_redis:
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
        
        # Test first request
        mock_pipeline.execute.return_value = [1, -1] # count=1, ttl=-1
        
        allowed = await store.check_rate_limit("12345", max_requests=20, window_secs=60)
        assert allowed is True
        mock_redis.expire.assert_called_once_with("thuk:rl:12345", 60)
        
        # Test 21st request
        mock_redis.expire.reset_mock()
        mock_pipeline.execute.return_value = [21, 50] # count=21, ttl=50
        
        allowed = await store.check_rate_limit("12345", max_requests=20, window_secs=60)
        assert allowed is False
        mock_redis.expire.assert_not_called()
