"""
Kafka Producer for Knowledge Service Events

知识图谱服务事件发布
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Kafka producer singleton
_kafka_producer_instance: Optional["KafkaProducer"] = None
_kafka_producer_lock = asyncio.Lock()


class KafkaProducer:
    """Kafka事件生产者"""

    def __init__(self, config: Optional[Dict] = None, compensation_service: Optional[Any] = None):
        """
        初始化Kafka生产者
        
        Args:
            config: Kafka配置
            compensation_service: 事件补偿服务（可选）
        """
        from app.core.config import settings
        
        self.config = config or {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "acks": settings.KAFKA_ACKS,
            "retries": settings.KAFKA_RETRIES,
            "linger.ms": settings.KAFKA_LINGER_MS,
            "compression.type": settings.KAFKA_COMPRESSION_TYPE,
        }

        # 延迟导入confluent_kafka
        try:
            from confluent_kafka import KafkaException, Producer
            self.Producer = Producer
            self.KafkaException = KafkaException
            self.producer = Producer(self.config)
        except ImportError:
            logger.warning("confluent_kafka not installed, using mock producer")
            self.producer = None
            self.Producer = None
            self.KafkaException = Exception

        self.topic_knowledge_events = settings.KAFKA_TOPIC_KNOWLEDGE_EVENTS
        self.compensation_service = compensation_service
        self.sent_count = 0
        self.failed_count = 0
        
        logger.info(
            f"Kafka Producer initialized with servers: {self.config.get('bootstrap.servers')}"
        )

    def _delivery_report(self, err: Any, msg: Any) -> None:
        """消息发送回调"""
        if err is not None:
            self.failed_count += 1
            logger.error(f"Message delivery failed: {err}")
        else:
            self.sent_count += 1
            logger.debug(
                f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}"
            )

    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """发布通用事件"""
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
            "metadata": metadata or {},
        }

        if not self.producer:
            logger.warning(f"Mock Kafka event: {event_type}")
            return

        try:
            # 使用asyncio.to_thread避免阻塞
            await asyncio.to_thread(
                self.producer.produce,
                self.topic_knowledge_events,
                key=payload.get("entity_id", payload.get("graph_id", "")).encode("utf-8"),
                value=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                callback=self._delivery_report,
            )
            # 刷新缓冲区
            await asyncio.to_thread(self.producer.poll, 0)
            logger.info(f"Published event '{event_type}'")
        except Exception as e:
            logger.error(f"Failed to publish event to Kafka: {e}")
            
            # 记录失败事件到补偿服务
            if self.compensation_service:
                try:
                    await self.compensation_service.record_failed_event(
                        event_type=event_type,
                        payload=payload,
                        error=str(e),
                        metadata=metadata,
                    )
                except Exception as comp_error:
                    logger.error(f"Failed to record failed event: {comp_error}")
            
            raise

    async def publish_entity_created(
        self, entity_id: str, tenant_id: str, entity_data: Dict[str, Any]
    ) -> None:
        """发布实体创建事件"""
        await self.publish_event(
            "entity.created",
            {
                "entity_id": entity_id,
                "tenant_id": tenant_id,
                "name": entity_data.get("name"),
                "type": entity_data.get("type"),
                "description": entity_data.get("description", ""),
            },
        )

    async def publish_entity_updated(
        self, entity_id: str, tenant_id: str, changes: Dict[str, Any]
    ) -> None:
        """发布实体更新事件"""
        await self.publish_event(
            "entity.updated",
            {"entity_id": entity_id, "tenant_id": tenant_id, "changes": changes},
        )

    async def publish_entity_deleted(self, entity_id: str, tenant_id: str) -> None:
        """发布实体删除事件"""
        await self.publish_event(
            "entity.deleted", {"entity_id": entity_id, "tenant_id": tenant_id}
        )

    async def publish_relation_created(
        self,
        relation_id: str,
        tenant_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
    ) -> None:
        """发布关系创建事件"""
        await self.publish_event(
            "relation.created",
            {
                "relation_id": relation_id,
                "tenant_id": tenant_id,
                "source_id": source_id,
                "target_id": target_id,
                "type": relation_type,
            },
        )

    async def publish_graph_built(
        self,
        graph_id: str,
        tenant_id: str,
        entity_count: int,
        relation_count: int,
        metadata: Dict[str, Any],
    ) -> None:
        """发布图谱构建完成事件"""
        await self.publish_event(
            "graph.built",
            {
                "graph_id": graph_id,
                "tenant_id": tenant_id,
                "entity_count": entity_count,
                "relation_count": relation_count,
            },
            metadata,
        )

    async def publish_community_detected(
        self,
        graph_id: str,
        tenant_id: str,
        community_count: int,
        algorithm: str,
        metadata: Dict[str, Any],
    ) -> None:
        """发布社区检测完成事件"""
        await self.publish_event(
            "community.detected",
            {
                "graph_id": graph_id,
                "tenant_id": tenant_id,
                "community_count": community_count,
                "algorithm": algorithm,
            },
            metadata,
        )

    async def close(self) -> None:
        """关闭生产者"""
        if self.producer:
            logger.info(
                f"Closing Kafka Producer... (sent={self.sent_count}, failed={self.failed_count})"
            )
            await asyncio.to_thread(self.producer.flush, 10)
            logger.info("Kafka Producer closed.")

    def get_metrics(self) -> Dict[str, int]:
        """获取生产者指标"""
        return {
            "sent_count": self.sent_count,
            "failed_count": self.failed_count,
        }


async def get_kafka_producer() -> KafkaProducer:
    """获取Kafka生产者单例"""
    global _kafka_producer_instance
    async with _kafka_producer_lock:
        if _kafka_producer_instance is None:
            _kafka_producer_instance = KafkaProducer()
        return _kafka_producer_instance


async def close_kafka_producer() -> None:
    """关闭Kafka生产者单例"""
    global _kafka_producer_instance
    async with _kafka_producer_lock:
        if _kafka_producer_instance:
            await _kafka_producer_instance.close()
            _kafka_producer_instance = None
