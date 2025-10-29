"""
Unit Tests for Neo4j Client
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.graph.neo4j_client import Neo4jClient


@pytest.fixture
def mock_driver():
    """Mock Neo4j driver"""
    driver = MagicMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__.return_value = session
    driver.session.return_value.__aexit__.return_value = None
    return driver, session


@pytest.mark.asyncio
async def test_execute_query_success(mock_driver):
    """测试执行查询成功"""
    driver, session = mock_driver

    # Mock query result
    result = AsyncMock()
    result.data.return_value = [{"name": "test", "count": 1}]
    session.run.return_value = result

    # Create client with mocked driver
    client = Neo4jClient()
    client.driver = driver

    # Execute query
    results = await client.execute_query("MATCH (n) RETURN n")

    # Verify
    assert len(results) == 1
    assert results[0]["name"] == "test"
    assert results[0]["count"] == 1
    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_execute_query_with_parameters(mock_driver):
    """测试带参数的查询"""
    driver, session = mock_driver

    result = AsyncMock()
    result.data.return_value = [{"id": "123"}]
    session.run.return_value = result

    client = Neo4jClient()
    client.driver = driver

    params = {"name": "test"}
    results = await client.execute_query("MATCH (n {name: $name}) RETURN n", params)

    assert len(results) == 1
    session.run.assert_called_once_with("MATCH (n {name: $name}) RETURN n", params)


@pytest.mark.asyncio
async def test_execute_query_failure(mock_driver):
    """测试查询失败"""
    driver, session = mock_driver

    session.run.side_effect = Exception("Connection error")

    client = Neo4jClient()
    client.driver = driver

    results = await client.execute_query("INVALID QUERY")

    # Should return empty list on error
    assert results == []


@pytest.mark.asyncio
async def test_create_node_success(mock_driver):
    """测试创建节点成功"""
    driver, session = mock_driver

    result = AsyncMock()
    result.data.return_value = [{"id": "node-123"}]
    session.run.return_value = result

    client = Neo4jClient()
    client.driver = driver

    node_id = await client.create_node("Person", {"name": "Alice", "age": 30})

    assert node_id == "node-123"
    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_create_relationship_success(mock_driver):
    """测试创建关系成功"""
    driver, session = mock_driver

    result = AsyncMock()
    result.data.return_value = [{"r": "relationship"}]
    session.run.return_value = result

    client = Neo4jClient()
    client.driver = driver

    success = await client.create_relationship(
        from_id="node-1",
        to_id="node-2",
        rel_type="KNOWS",
        properties={"since": 2020}
    )

    assert success is True
    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_health_check_success(mock_driver):
    """测试健康检查成功"""
    driver, session = mock_driver

    result = AsyncMock()
    result.data.return_value = [{"test": 1}]
    session.run.return_value = result

    client = Neo4jClient()
    client.driver = driver

    health = await client.health_check()

    assert health["healthy"] is True
    assert health["connected"] is True


@pytest.mark.asyncio
async def test_health_check_failure():
    """测试健康检查失败"""
    client = Neo4jClient()
    client.driver = None

    health = await client.health_check()

    assert health["healthy"] is False
    assert "error" in health

