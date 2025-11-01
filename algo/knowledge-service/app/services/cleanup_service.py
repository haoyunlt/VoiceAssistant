"""
Cleanup Service for Knowledge Service

知识图谱服务清理任务
"""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CleanupService:
    """清理服务 - 定期清理过期数据"""

    def __init__(self, neo4j_client, redis_client):
        """
        初始化清理服务

        Args:
            neo4j_client: Neo4j客户端
            redis_client: Redis客户端
        """
        self.neo4j = neo4j_client
        self.redis = redis_client
        self.is_running = False
        self.cleanup_task = None

    async def start_cleanup_task(self, interval_hours: int = 24):
        """启动定期清理任务"""
        if self.is_running:
            logger.warning("Cleanup task is already running")
            return

        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop(interval_hours))
        logger.info(f"Cleanup task started with interval: {interval_hours} hours")

    async def stop_cleanup_task(self):
        """停止清理任务"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.is_running = False
            self.cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.cleanup_task
            logger.info("Cleanup task stopped")

    async def _cleanup_loop(self, interval_hours: int):
        """清理循环"""
        while self.is_running:
            try:
                await self.run_cleanup()
                # 等待下次清理
                await asyncio.sleep(interval_hours * 3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)
                # 出错后等待1小时再重试
                await asyncio.sleep(3600)

    async def run_cleanup(self) -> dict[str, int]:
        """运行一次完整的清理"""
        logger.info("Starting cleanup tasks...")
        start_time = datetime.utcnow()

        results = {
            "orphan_entities_removed": 0,
            "orphan_relations_removed": 0,
            "expired_cache_cleared": 0,
            "old_communities_removed": 0,
        }

        try:
            # 1. 清理孤立实体（没有任何关系的实体）
            results["orphan_entities_removed"] = await self._cleanup_orphan_entities()

            # 2. 清理孤立关系（源或目标实体不存在）
            results["orphan_relations_removed"] = await self._cleanup_orphan_relations()

            # 3. 清理过期缓存
            results["expired_cache_cleared"] = await self._cleanup_expired_cache()

            # 4. 清理旧的社区检测结果
            results["old_communities_removed"] = await self._cleanup_old_communities()

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Cleanup completed in {elapsed:.2f}s: "
                f"orphan_entities={results['orphan_entities_removed']}, "
                f"orphan_relations={results['orphan_relations_removed']}, "
                f"expired_cache={results['expired_cache_cleared']}, "
                f"old_communities={results['old_communities_removed']}"
            )

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)

        return results

    async def _cleanup_orphan_entities(self, days_threshold: int = 30) -> int:
        """
        清理孤立实体

        删除创建超过N天且没有任何关系的实体
        """
        try:
            threshold_timestamp = int(
                (datetime.utcnow() - timedelta(days=days_threshold)).timestamp() * 1000
            )

            cypher = """
            MATCH (e:Entity)
            WHERE e.created_at < $threshold
            AND NOT (e)-[]-()
            WITH e
            LIMIT 1000
            DELETE e
            RETURN COUNT(e) as count
            """

            result = await self.neo4j.query(cypher, {"threshold": threshold_timestamp})
            count = result[0]["count"] if result else 0

            if count > 0:
                logger.info(f"Removed {count} orphan entities")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup orphan entities: {e}")
            return 0

    async def _cleanup_orphan_relations(self) -> int:
        """清理孤立关系（源或目标实体不存在）"""
        try:
            # Neo4j会自动删除连接到已删除节点的关系
            # 这里主要处理数据不一致的情况
            cypher = """
            MATCH ()-[r:RELATES]->()
            WHERE NOT exists((r)-[:FROM]->(:Entity))
            OR NOT exists((r)-[:TO]->(:Entity))
            WITH r
            LIMIT 1000
            DELETE r
            RETURN COUNT(r) as count
            """

            result = await self.neo4j.query(cypher)
            count = result[0]["count"] if result else 0

            if count > 0:
                logger.info(f"Removed {count} orphan relations")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup orphan relations: {e}")
            return 0

    async def _cleanup_expired_cache(self) -> int:
        """清理过期缓存"""
        try:
            count = 0

            # 清理实体缓存（过期时间24小时）
            entity_cache_pattern = "knowledge:entity:*"
            entity_keys = await self._scan_keys(entity_cache_pattern)

            for key in entity_keys:
                ttl = await self.redis.ttl(key)
                if ttl == -1:  # 没有设置过期时间
                    await self.redis.expire(key, 86400)  # 设置24小时
                elif ttl == -2:  # 已过期
                    await self.redis.delete(key)
                    count += 1

            # 清理查询缓存（过期时间1小时）
            query_cache_pattern = "knowledge:query:*"
            query_keys = await self._scan_keys(query_cache_pattern)

            for key in query_keys:
                ttl = await self.redis.ttl(key)
                if ttl == -1:
                    await self.redis.expire(key, 3600)  # 设置1小时
                elif ttl == -2:
                    await self.redis.delete(key)
                    count += 1

            if count > 0:
                logger.info(f"Cleared {count} expired cache entries")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0

    async def _cleanup_old_communities(self, days_threshold: int = 7) -> int:
        """清理旧的社区检测结果"""
        try:
            count = 0

            # 清理Redis中的社区检测结果
            community_pattern = "knowledge:community:*"
            community_keys = await self._scan_keys(community_pattern)

            threshold_timestamp = (datetime.utcnow() - timedelta(days=days_threshold)).timestamp()

            for key in community_keys:
                # 获取社区数据
                data = await self.redis.get(key)
                if data:
                    import json

                    try:
                        community_data = json.loads(data)
                        created_at = datetime.fromisoformat(
                            community_data.get("created_at", "")
                        ).timestamp()

                        if created_at < threshold_timestamp:
                            await self.redis.delete(key)
                            count += 1
                    except (json.JSONDecodeError, ValueError):
                        # 无效数据，直接删除
                        await self.redis.delete(key)
                        count += 1

            # 清理Neo4j中的Community节点
            threshold_ms = int(threshold_timestamp * 1000)
            cypher = """
            MATCH (c:Community)
            WHERE c.created_at < $threshold
            WITH c
            LIMIT 1000
            DETACH DELETE c
            RETURN COUNT(c) as count
            """

            result = await self.neo4j.query(cypher, {"threshold": threshold_ms})
            neo4j_count = result[0]["count"] if result else 0
            count += neo4j_count

            if count > 0:
                logger.info(f"Removed {count} old community detection results")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup old communities: {e}")
            return 0

    async def _scan_keys(self, pattern: str, count: int = 100) -> list[str]:
        """扫描Redis键"""
        try:
            keys = []
            cursor = 0

            while True:
                cursor, batch = await self.redis.scan(cursor, match=pattern, count=count)
                keys.extend(batch)

                if cursor == 0:
                    break

            return keys

        except Exception as e:
            logger.error(f"Failed to scan keys: {e}")
            return []

    async def cleanup_tenant_data(self, tenant_id: str) -> dict[str, int]:
        """清理指定租户的所有数据"""
        logger.info(f"Cleaning up data for tenant: {tenant_id}")

        results = {
            "entities_removed": 0,
            "relations_removed": 0,
            "cache_cleared": 0,
        }

        try:
            # 1. 删除Neo4j中的租户数据
            cypher = """
            MATCH (e:Entity {tenant_id: $tenant_id})
            WITH e
            LIMIT 10000
            DETACH DELETE e
            RETURN COUNT(e) as count
            """

            result = await self.neo4j.query(cypher, {"tenant_id": tenant_id})
            results["entities_removed"] = result[0]["count"] if result else 0

            # 2. 清理Redis缓存
            tenant_cache_pattern = f"knowledge:*:{tenant_id}:*"
            tenant_keys = await self._scan_keys(tenant_cache_pattern)

            for key in tenant_keys:
                await self.redis.delete(key)
                results["cache_cleared"] += 1

            logger.info(
                f"Tenant {tenant_id} cleanup completed: "
                f"entities={results['entities_removed']}, "
                f"cache={results['cache_cleared']}"
            )

        except Exception as e:
            logger.error(f"Failed to cleanup tenant data: {e}")

        return results
