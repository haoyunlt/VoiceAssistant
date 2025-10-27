"""
Pytest Configuration and Fixtures
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_settings():
    """Mock settings"""
    settings = MagicMock()
    settings.NEO4J_URI = "bolt://localhost:7687"
    settings.NEO4J_USER = "neo4j"
    settings.NEO4J_PASSWORD = "password"
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
    settings.LOG_LEVEL = "INFO"
    return settings


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.eval = AsyncMock(return_value=1)
    return redis
