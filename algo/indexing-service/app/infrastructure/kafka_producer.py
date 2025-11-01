"""Kafka事件发布者"""

import json
import logging
import os
from typing import Any

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka事件发布者

    用于发布文档索引相关的事件到Kafka，包括：
    - 文档索引完成事件
    - 文档索引失败事件
    - 分块创建事件
    - 向量化完成事件
    """

    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.producer: Producer | None = None
        self.admin_client: AdminClient | None = None

        # 主题配置
        self.topics = {
            "document_indexed": os.getenv("KAFKA_TOPIC_DOCUMENT_INDEXED", "document.indexed"),
            "document_failed": os.getenv("KAFKA_TOPIC_DOCUMENT_FAILED", "document.failed"),
            "chunks_created": os.getenv("KAFKA_TOPIC_CHUNKS_CREATED", "document.chunks.created"),
            "vectors_stored": os.getenv("KAFKA_TOPIC_VECTORS_STORED", "document.vectors.stored"),
        }

        logger.info(f"Kafka Producer initialized with servers: {self.bootstrap_servers}")
        logger.info(f"Topics: {self.topics}")

    async def initialize(self):
        """初始化生产者"""
        try:
            # 创建生产者
            config = {
                "bootstrap.servers": self.bootstrap_servers,
                "client.id": "indexing-service-producer",
                # 可靠性配置
                "acks": "all",  # 等待所有副本确认
                "retries": 3,  # 重试次数
                "max.in.flight.requests.per.connection": 1,  # 保证消息顺序
                # 性能配置
                "compression.type": "snappy",
                "linger.ms": 10,  # 批量发送延迟
                "batch.size": 32768,  # 批量大小
            }

            self.producer = Producer(config)

            # 创建管理客户端
            self.admin_client = AdminClient({"bootstrap.servers": self.bootstrap_servers})

            # 确保主题存在
            await self._ensure_topics_exist()

            logger.info("Kafka Producer initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Kafka Producer: {e}", exc_info=True)
            raise

    async def _ensure_topics_exist(self):
        """确保所有主题存在"""
        try:
            # 获取现有主题
            metadata = self.admin_client.list_topics(timeout=10)
            existing_topics = set(metadata.topics.keys())

            # 创建缺失的主题
            topics_to_create = []
            for topic_name in self.topics.values():
                if topic_name not in existing_topics:
                    topics_to_create.append(
                        NewTopic(
                            topic_name,
                            num_partitions=3,
                            replication_factor=1,
                        )
                    )

            if topics_to_create:
                logger.info(f"Creating topics: {[t.topic for t in topics_to_create]}")
                fs = self.admin_client.create_topics(topics_to_create)

                # 等待主题创建完成
                for topic, future in fs.items():
                    try:
                        future.result()
                        logger.info(f"Topic {topic} created successfully")
                    except Exception as e:
                        logger.warning(f"Failed to create topic {topic}: {e}")
            else:
                logger.info("All topics already exist")

        except Exception as e:
            logger.warning(f"Failed to ensure topics exist: {e}")

    async def publish_document_indexed(
        self,
        document_id: str,
        tenant_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        发布文档索引完成事件

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
            metadata: 索引元数据（分块数、向量数等）
        """
        event = {
            "event_type": "document.indexed",
            "document_id": document_id,
            "tenant_id": tenant_id,
            "metadata": metadata or {},
            "timestamp": self._get_timestamp(),
        }

        await self._publish(self.topics["document_indexed"], document_id, event)
        logger.info(f"Published document_indexed event for {document_id}")

    async def publish_document_failed(
        self,
        document_id: str,
        tenant_id: str,
        error: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        发布文档索引失败事件

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
            error: 错误信息
            metadata: 额外元数据
        """
        event = {
            "event_type": "document.failed",
            "document_id": document_id,
            "tenant_id": tenant_id,
            "error": error,
            "metadata": metadata or {},
            "timestamp": self._get_timestamp(),
        }

        await self._publish(self.topics["document_failed"], document_id, event)
        logger.warning(f"Published document_failed event for {document_id}: {error}")

    async def publish_chunks_created(
        self,
        document_id: str,
        tenant_id: str,
        chunk_count: int,
        chunks_info: list | None = None,
    ):
        """
        发布分块创建事件

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
            chunk_count: 分块数量
            chunks_info: 分块信息列表
        """
        event = {
            "event_type": "chunks.created",
            "document_id": document_id,
            "tenant_id": tenant_id,
            "chunk_count": chunk_count,
            "chunks_info": chunks_info or [],
            "timestamp": self._get_timestamp(),
        }

        await self._publish(self.topics["chunks_created"], document_id, event)
        logger.info(f"Published chunks_created event for {document_id}: {chunk_count} chunks")

    async def publish_vectors_stored(
        self,
        document_id: str,
        tenant_id: str,
        vector_count: int,
        collection_name: str,
    ):
        """
        发布向量存储事件

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
            vector_count: 向量数量
            collection_name: 向量集合名称
        """
        event = {
            "event_type": "vectors.stored",
            "document_id": document_id,
            "tenant_id": tenant_id,
            "vector_count": vector_count,
            "collection_name": collection_name,
            "timestamp": self._get_timestamp(),
        }

        await self._publish(self.topics["vectors_stored"], document_id, event)
        logger.info(f"Published vectors_stored event for {document_id}: {vector_count} vectors")

    async def _publish(self, topic: str, key: str, value: dict[str, Any]):
        """
        发布消息到Kafka

        Args:
            topic: 主题名称
            key: 消息键（用于分区）
            value: 消息内容
        """
        if not self.producer:
            raise RuntimeError("Kafka Producer not initialized")

        try:
            # 序列化为JSON
            value_bytes = json.dumps(value, ensure_ascii=False).encode("utf-8")
            key_bytes = key.encode("utf-8")

            # 发布消息
            self.producer.produce(
                topic=topic,
                key=key_bytes,
                value=value_bytes,
                callback=self._delivery_callback,
            )

            # 触发发送（非阻塞）
            self.producer.poll(0)

        except Exception as e:
            logger.error(f"Failed to publish message to {topic}: {e}", exc_info=True)
            raise

    def _delivery_callback(self, err, msg):
        """消息发送回调"""
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")

    async def flush(self, timeout: float = 10.0):
        """刷新所有待发送的消息"""
        if self.producer:
            remaining = self.producer.flush(timeout)
            if remaining > 0:
                logger.warning(f"{remaining} messages were not delivered")
            else:
                logger.debug("All messages delivered successfully")

    async def close(self):
        """关闭生产者"""
        if self.producer:
            logger.info("Flushing remaining messages...")
            await self.flush()
            logger.info("Kafka Producer closed")

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.utcnow().isoformat()


# 全局单例
_kafka_producer: KafkaProducer | None = None


async def get_kafka_producer() -> KafkaProducer:
    """获取Kafka生产者单例"""
    global _kafka_producer

    if _kafka_producer is None:
        _kafka_producer = KafkaProducer()
        await _kafka_producer.initialize()

    return _kafka_producer


async def close_kafka_producer():
    """关闭Kafka生产者"""
    global _kafka_producer

    if _kafka_producer:
        await _kafka_producer.close()
        _kafka_producer = None
