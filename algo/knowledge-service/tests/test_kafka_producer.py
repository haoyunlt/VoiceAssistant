"""
Unit Tests for Kafka Producer
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infrastructure.kafka_producer import KafkaProducer


@pytest.fixture
def mock_producer():
    """Mock Kafka producer"""
    producer = MagicMock()
    producer.produce = MagicMock()
    producer.poll = MagicMock()
    producer.flush = MagicMock()
    return producer


@pytest.fixture
def mock_compensation_service():
    """Mock compensation service"""
    service = AsyncMock()
    service.record_failed_event = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_publish_event_success(mock_producer):
    """测试发布事件成功"""
    kafka_producer = KafkaProducer()
    kafka_producer.producer = mock_producer

    await kafka_producer.publish_event(
        "test.event",
        {"key": "value"},
        {"source": "test"}
    )

    # Verify produce was called
    assert mock_producer.produce.called
    assert mock_producer.poll.called


@pytest.mark.asyncio
async def test_publish_event_with_compensation(mock_producer, mock_compensation_service):
    """测试发布失败时记录补偿"""
    kafka_producer = KafkaProducer()
    kafka_producer.producer = mock_producer
    kafka_producer.compensation_service = mock_compensation_service

    # Simulate failure
    mock_producer.produce.side_effect = Exception("Kafka error")

    with pytest.raises(Exception):
        await kafka_producer.publish_event("test.event", {"key": "value"})

    # Verify compensation service was called
    mock_compensation_service.record_failed_event.assert_called_once()


@pytest.mark.asyncio
async def test_publish_entity_created(mock_producer):
    """测试发布实体创建事件"""
    kafka_producer = KafkaProducer()
    kafka_producer.producer = mock_producer

    await kafka_producer.publish_entity_created(
        entity_id="entity-123",
        tenant_id="tenant-1",
        entity_data={"name": "Test Entity", "type": "Person"}
    )

    assert mock_producer.produce.called


def test_get_metrics(mock_producer):
    """测试获取指标"""
    kafka_producer = KafkaProducer()
    kafka_producer.sent_count = 10
    kafka_producer.failed_count = 2

    metrics = kafka_producer.get_metrics()

    assert metrics["sent_count"] == 10
    assert metrics["failed_count"] == 2


@pytest.mark.asyncio
async def test_close_producer(mock_producer):
    """测试关闭生产者"""
    kafka_producer = KafkaProducer()
    kafka_producer.producer = mock_producer

    await kafka_producer.close()

    # Verify flush was called
    mock_producer.flush.assert_called_once()
