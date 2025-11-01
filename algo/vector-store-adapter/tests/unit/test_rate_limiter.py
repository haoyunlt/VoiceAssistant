"""Unit tests for rate limiter middleware"""

import time
from unittest.mock import AsyncMock, Mock

import pytest
from app.middleware.rate_limiter import RateLimiterMiddleware
from fastapi import HTTPException, Request, Response
from starlette.datastructures import Headers


@pytest.mark.unit
class TestRateLimiterMiddleware:
    """Test rate limiter middleware"""

    @pytest.fixture
    def middleware(self, mock_redis_client):
        """Create rate limiter middleware"""
        app = Mock()
        return RateLimiterMiddleware(
            app,
            redis_client=mock_redis_client,
            max_requests=10,
            window_seconds=60,
            enabled=True,
        )

    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.client.host = "127.0.0.1"
        request.headers = Headers({})
        request.state = Mock()
        request.state.trace_id = "test_trace_id"
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create mock call_next function"""

        async def call_next(_request):
            return Response(content="OK", status_code=200)

        return call_next

    @pytest.mark.asyncio
    async def test_disabled_middleware(self, mock_request, mock_call_next):
        """Test disabled middleware"""
        app = Mock()
        middleware = RateLimiterMiddleware(app, enabled=False)

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_skip_health_endpoints(self, middleware, mock_call_next):
        """Test skipping health check endpoints"""
        for path in ["/health", "/ready", "/metrics"]:
            request = Mock(spec=Request)
            request.url.path = path

            response = await middleware.dispatch(request, mock_call_next)
            assert response.status_code == 200

    def test_get_client_id_with_tenant(self, middleware):
        """Test get client ID with tenant header"""
        request = Mock(spec=Request)
        request.headers = Headers({"X-Tenant-Id": "tenant_123"})

        client_id = middleware._get_client_id(request)
        assert client_id == "tenant:tenant_123"

    def test_get_client_id_with_ip(self, middleware):
        """Test get client ID with IP"""
        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client.host = "192.168.1.100"

        client_id = middleware._get_client_id(request)
        assert client_id == "ip:192.168.1.100"

    @pytest.mark.asyncio
    async def test_rate_limit_redis_success(self, middleware, mock_redis_client):
        """Test rate limit check with Redis (allowed)"""
        middleware.redis_client = mock_redis_client
        mock_redis_client.zcard = AsyncMock(return_value=5)  # Under limit

        current_time = time.time()
        allowed = await middleware._check_rate_limit_redis("test_key", current_time)

        assert allowed is True
        mock_redis_client.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_redis_exceeded(self, middleware, mock_redis_client):
        """Test rate limit check with Redis (exceeded)"""
        middleware.redis_client = mock_redis_client
        mock_redis_client.zcard = AsyncMock(return_value=10)  # At limit

        current_time = time.time()
        allowed = await middleware._check_rate_limit_redis("test_key", current_time)

        assert allowed is False

    def test_rate_limit_memory_success(self, middleware):
        """Test rate limit check with memory (allowed)"""
        current_time = time.time()

        # First 10 requests should be allowed
        for i in range(10):
            allowed = middleware._check_rate_limit_memory("test_key", current_time + i)
            assert allowed is True

    def test_rate_limit_memory_exceeded(self, middleware):
        """Test rate limit check with memory (exceeded)"""
        current_time = time.time()

        # Fill up the limit
        for i in range(10):
            middleware._check_rate_limit_memory("test_key", current_time + i)

        # 11th request should be denied
        allowed = middleware._check_rate_limit_memory("test_key", current_time + 10)
        assert allowed is False

    def test_rate_limit_memory_sliding_window(self, middleware):
        """Test sliding window behavior"""
        current_time = time.time()

        # Add 10 requests
        for i in range(10):
            middleware._check_rate_limit_memory("test_key", current_time + i)

        # After window expires, should be allowed again
        allowed = middleware._check_rate_limit_memory(
            "test_key", current_time + middleware.window_seconds + 1
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_dispatch_allowed(
        self, middleware, mock_request, mock_call_next, mock_redis_client
    ):
        """Test dispatch with allowed request"""
        mock_redis_client.zcard = AsyncMock(return_value=5)

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_rate_limited(
        self, middleware, mock_request, mock_call_next, mock_redis_client
    ):
        """Test dispatch with rate limited request"""
        mock_redis_client.zcard = AsyncMock(return_value=10)

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dispatch_redis_fallback_to_memory(
        self, middleware, mock_request, mock_call_next, mock_redis_client
    ):
        """Test fallback to memory when Redis fails"""
        mock_redis_client.zcard = AsyncMock(side_effect=Exception("Redis error"))

        # Should fall back to memory cache
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200
