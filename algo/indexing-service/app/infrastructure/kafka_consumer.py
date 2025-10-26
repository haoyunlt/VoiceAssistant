"""
Kafka Consumer - 订阅文档事件
"""

import asyncio
import json
import logging
from typing import Callable, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

logger = logging.getLogger(__name__)


class DocumentEventConsumer:
    """文档事件消费者"""

    def __init__(self, config: Optional[dict] = None):
        """初始化消费者"""
        # 默认配置
        self.config = config or {
            "bootstrap.servers": "kafka:9092",
            "group.id": "indexing-service",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            "max.poll.interval.ms": 300000,  # 5分钟
        }

        # 主题
        self.topic = "document.events"

        # 消费者实例
        self.consumer = None

        # 运行状态
        self._running = False

        # 消息处理器
        self.handlers = {
            "document.uploaded": [],
            "document.updated": [],
            "document.deleted": [],
        }

        logger.info("Kafka consumer initialized")

    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type}")

    async def start(self):
        """启动消费者"""
        logger.info("Starting Kafka consumer...")

        try:
            # 创建消费者
            self.consumer = Consumer(self.config)

            # 订阅主题
            self.consumer.subscribe([self.topic])

            self._running = True
            logger.info(f"Subscribed to topic: {self.topic}")

            # 消费消息循环
            await self._consume_loop()

        except KafkaException as e:
            logger.error(f"Kafka exception: {e}")
            raise
        finally:
            if self.consumer:
                self.consumer.close()
                logger.info("Kafka consumer closed")

    async def stop(self):
        """停止消费者"""
        logger.info("Stopping Kafka consumer...")
        self._running = False

        if self.consumer:
            self.consumer.close()

        logger.info("Kafka consumer stopped")

    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._running

    async def _consume_loop(self):
        """消费消息循环"""
        while self._running:
            try:
                # 拉取消息（超时1秒）
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    # 没有新消息
                    await asyncio.sleep(0.1)
                    continue

                if msg.error():
                    # 错误处理
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"Reached end of partition: {msg.topic()} [{msg.partition()}]")
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                    continue

                # 处理消息
                await self._handle_message(msg)

            except Exception as e:
                logger.error(f"Error in consume loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _handle_message(self, msg):
        """处理单条消息"""
        try:
            # 解析消息
            value = msg.value().decode("utf-8")
            event = json.loads(value)

            event_type = event.get("event_type")
            payload = event.get("payload", {})

            logger.info(f"Received event: {event_type}, payload: {payload}")

            # 分发到处理器
            handlers = self.handlers.get(event_type, [])
            if not handlers:
                logger.warning(f"No handlers registered for event type: {event_type}")
                return

            # 调用所有处理器
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(payload)
                    else:
                        handler(payload)
                except Exception as e:
                    logger.error(f"Error in handler: {e}", exc_info=True)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)


# ========================================
# 事件 Schema
# ========================================

class DocumentEvent:
    """文档事件基类"""

    def __init__(self, event_id: str, event_type: str, payload: dict, metadata: dict = None):
        self.event_id = event_id
        self.event_type = event_type
        self.payload = payload
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "metadata": self.metadata,
        }


class DocumentUploadedEvent(DocumentEvent):
    """文档上传事件"""

    def __init__(self, document_id: str, tenant_id: str, user_id: str,
                 filename: str, file_path: str, file_size: int, content_type: str):
        super().__init__(
            event_id=f"doc-upload-{document_id}",
            event_type="document.uploaded",
            payload={
                "document_id": document_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "filename": filename,
                "file_path": file_path,
                "file_size": file_size,
                "content_type": content_type,
            },
        )


class DocumentUpdatedEvent(DocumentEvent):
    """文档更新事件"""

    def __init__(self, document_id: str, tenant_id: str, user_id: str, changes: dict):
        super().__init__(
            event_id=f"doc-update-{document_id}",
            event_type="document.updated",
            payload={
                "document_id": document_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "changes": changes,
            },
        )


class DocumentDeletedEvent(DocumentEvent):
    """文档删除事件"""

    def __init__(self, document_id: str, tenant_id: str, user_id: str):
        super().__init__(
            event_id=f"doc-delete-{document_id}",
            event_type="document.deleted",
            payload={
                "document_id": document_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )
