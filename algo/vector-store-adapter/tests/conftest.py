"""Pytest fixtures for vector-store-adapter tests"""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========================================
# Test Data Fixtures
# ========================================

@pytest.fixture
def sample_vector_data():
    """Sample vector data for testing"""
    return {
        "chunk_id": "chunk_123",
        "document_id": "doc_abc",
        "content": "This is a test document chunk.",
        "embedding": [0.1] * 1024,
        "tenant_id": "tenant_test",
        "metadata": {"source": "test"},
    }


@pytest.fixture
def sample_vector_data_batch():
    """Batch of sample vector data"""
    return [
        {
            "chunk_id": f"chunk_{i}",
            "document_id": "doc_abc",
            "content": f"Test chunk {i}",
            "embedding": [0.1 * i] * 1024,
            "tenant_id": "tenant_test",
        }
        for i in range(10)
    ]


@pytest.fixture
def sample_query_vector():
    """Sample query vector"""
    return [0.5] * 1024


# ========================================
# Mock Backend Fixtures
# ========================================

@pytest.fixture
def mock_milvus_connection():
    """Mock Milvus connection"""
    mock = MagicMock()
    mock.connect = Mock()
    mock.disconnect = Mock()
    return mock


@pytest.fixture
def mock_milvus_collection():
    """Mock Milvus collection"""
    mock = MagicMock()
    mock.insert = Mock(return_value=MagicMock(primary_keys=[1, 2, 3]))
    mock.search = Mock(return_value=[[]])
    mock.delete = Mock()
    mock.flush = Mock()
    mock.load = Mock()
    mock.num_entities = 100
    return mock


@pytest.fixture
async def mock_pgvector_pool():
    """Mock asyncpg connection pool"""
    pool = AsyncMock()

    # Mock connection context manager
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=100)

    # Mock acquire context manager
    acquire_mock = AsyncMock()
    acquire_mock.__aenter__ = AsyncMock(return_value=conn)
    acquire_mock.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = Mock(return_value=acquire_mock)

    pool.close = AsyncMock()

    return pool


@pytest.fixture
async def mock_redis_client():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.zadd = AsyncMock(return_value=1)
    redis.zcard = AsyncMock(return_value=0)
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.close = AsyncMock()
    return redis


# ========================================
# Backend Config Fixtures
# ========================================

@pytest.fixture
def milvus_config():
    """Milvus backend configuration"""
    return {
        "host": "localhost",
        "port": 19530,
        "user": "",
        "password": "",
    }


@pytest.fixture
def pgvector_config():
    """pgvector backend configuration"""
    return {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "postgres",
        "password": "password",
        "min_pool_size": 2,
        "max_pool_size": 10,
    }


# ========================================
# FastAPI Test Client
# ========================================

@pytest.fixture
def test_client(monkeypatch):
    """FastAPI test client with mocked dependencies"""
    # Mock environment variables
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("IDEMPOTENCY_ENABLED", "false")
    monkeypatch.setenv("OTEL_ENABLED", "false")

    # Import after setting env vars
    from main import app

    with TestClient(app) as client:
        yield client


# ========================================
# Integration Test Fixtures (require real services)
# ========================================

@pytest.fixture(scope="session")
async def real_milvus_connection():
    """Real Milvus connection (for integration tests)"""
    pytest.skip("Integration test: requires Milvus")
    # TODO: Implement with testcontainers
    # from testcontainers.milvus import MilvusContainer
    # with MilvusContainer() as milvus:
    #     yield milvus.get_connection()


@pytest.fixture(scope="session")
async def real_postgres_connection():
    """Real PostgreSQL connection (for integration tests)"""
    pytest.skip("Integration test: requires PostgreSQL")
    # TODO: Implement with testcontainers
    # from testcontainers.postgres import PostgresContainer
    # with PostgresContainer("postgres:15-alpine") as postgres:
    #     yield postgres.get_connection()


@pytest.fixture(scope="session")
async def real_redis_connection():
    """Real Redis connection (for integration tests)"""
    pytest.skip("Integration test: requires Redis")
    # TODO: Implement with testcontainers
    # from testcontainers.redis import RedisContainer
    # with RedisContainer() as redis:
    #     yield redis.get_connection()
