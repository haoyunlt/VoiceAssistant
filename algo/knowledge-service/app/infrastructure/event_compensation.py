"""
Event Compensation Mechanism

事件补偿机制 - 处理失败的事件发布
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventCompensationService:
    """事件补偿服务"""

    def __init__(self, redis_client, kafka_producer, max_retries: int = 3):
        """
        初始化事件补偿服务

        Args:
            redis_client: Redis客户端（用于存储失败事件）
            kafka_producer: Kafka生产者（用于重试发送）
            max_retries: 最大重试次数
        """
        self.redis = redis_client
        self.kafka = kafka_producer
        self.max_retries = max_retries
        self.failed_events_key = "knowledge:failed_events"
        self.compensation_lock_key = "knowledge:compensation_lock"

    async def record_failed_event(
        self, event_type: str, payload: Dict, error: str, metadata: Optional[Dict] = None
    ):
        """记录失败的事件"""
        failed_event = {
            "id": str(uuid4()),
            "event_type": event_type,
            "payload": payload,
            "metadata": metadata or {},
            "error": error,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "next_retry_at": (datetime.utcnow() + timedelta(minutes=1)).isoformat(),
        }

        try:
            # 将失败事件存入Redis列表
            await self.redis.rpush(
                self.failed_events_key, json.dumps(failed_event, ensure_ascii=False)
            )
            logger.info(
                f"Recorded failed event: {event_type} (id={failed_event['id']})"
            )
        except Exception as e:
            logger.error(f"Failed to record failed event: {e}")

    async def retry_failed_events(self):
        """重试失败的事件"""
        # 获取分布式锁，防止多实例同时重试
        lock_acquired = await self._acquire_lock(timeout=300)
        if not lock_acquired:
            logger.info("Compensation lock is held by another instance, skipping")
            return

        try:
            logger.info("Starting event compensation...")

            # 获取所有失败事件
            events_data = await self.redis.lrange(self.failed_events_key, 0, -1)
            if not events_data:
                logger.info("No failed events to compensate")
                return

            logger.info(f"Found {len(events_data)} failed events to process")

            success_count = 0
            failed_count = 0
            retry_later = []

            for event_data in events_data:
                try:
                    event = json.loads(event_data)

                    # 检查是否到重试时间
                    next_retry_at = datetime.fromisoformat(event["next_retry_at"])
                    if datetime.utcnow() < next_retry_at:
                        retry_later.append(event_data)
                        continue

                    # 检查重试次数
                    if event["retry_count"] >= self.max_retries:
                        logger.warning(
                            f"Event {event['id']} exceeded max retries, discarding"
                        )
                        failed_count += 1
                        continue

                    # 重试发送事件
                    try:
                        await self.kafka.publish_event(
                            event["event_type"], event["payload"], event["metadata"]
                        )
                        logger.info(f"Successfully resent event {event['id']}")
                        success_count += 1
                    except Exception as e:
                        # 更新重试信息
                        event["retry_count"] += 1
                        event["last_error"] = str(e)
                        event["last_retry_at"] = datetime.utcnow().isoformat()
                        # 指数退避
                        backoff_minutes = 2 ** event["retry_count"]
                        event["next_retry_at"] = (
                            datetime.utcnow() + timedelta(minutes=backoff_minutes)
                        ).isoformat()
                        retry_later.append(json.dumps(event, ensure_ascii=False))
                        logger.warning(
                            f"Failed to resend event {event['id']}: {e}, "
                            f"will retry in {backoff_minutes} minutes"
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse event data: {e}")
                    failed_count += 1

            # 更新Redis中的失败事件列表
            await self.redis.delete(self.failed_events_key)
            if retry_later:
                for event_data in retry_later:
                    await self.redis.rpush(self.failed_events_key, event_data)

            logger.info(
                f"Event compensation completed: {success_count} success, "
                f"{len(retry_later)} retry later, {failed_count} failed"
            )

        finally:
            await self._release_lock()

    async def _acquire_lock(self, timeout: int = 300) -> bool:
        """获取分布式锁"""
        try:
            # 使用SETNX获取锁，超时时间5分钟
            acquired = await self.redis.setnx(
                self.compensation_lock_key, datetime.utcnow().isoformat()
            )
            if acquired:
                await self.redis.expire(self.compensation_lock_key, timeout)
            return acquired
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False

    async def _release_lock(self):
        """释放分布式锁"""
        try:
            await self.redis.delete(self.compensation_lock_key)
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")

    async def get_failed_events_count(self) -> int:
        """获取失败事件数量"""
        try:
            return await self.redis.llen(self.failed_events_key)
        except Exception as e:
            logger.error(f"Failed to get failed events count: {e}")
            return 0

    async def get_failed_events(
        self, start: int = 0, end: int = 99
    ) -> List[Dict]:
        """获取失败事件列表"""
        try:
            events_data = await self.redis.lrange(
                self.failed_events_key, start, end
            )
            return [json.loads(data) for data in events_data]
        except Exception as e:
            logger.error(f"Failed to get failed events: {e}")
            return []
