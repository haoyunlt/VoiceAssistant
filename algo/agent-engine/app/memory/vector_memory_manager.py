"""
向量记忆管理器

基于 Milvus 的长期记忆管理，实现：
- 向量化存储和检索
- Ebbinghaus 遗忘曲线衰减
- 访问频率增强
- 重要性评分
"""

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from app.core.logging_config import get_logger
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

logger = get_logger(__name__)


class VectorMemoryManager:
    """基于向量数据库的长期记忆管理"""

    def __init__(
        self,
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        embedding_service_url: str = "http://localhost:8002",
        collection_name: str = "agent_memory",
        time_decay_half_life_days: int = 30,
    ):
        """
        初始化向量记忆管理器

        Args:
            milvus_host: Milvus 主机
            milvus_port: Milvus 端口
            embedding_service_url: Embedding 服务 URL
            collection_name: Collection 名称
            time_decay_half_life_days: 时间衰减半衰期（天）
        """
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.embedding_service_url = embedding_service_url
        self.collection_name = collection_name
        self.time_decay_half_life_days = time_decay_half_life_days

        # 连接 Milvus
        self._connect_milvus()

        # 初始化 Collection
        self._init_collection()

        logger.info(
            f"VectorMemoryManager initialized: collection={collection_name}, "
            f"decay_half_life={time_decay_half_life_days} days"
        )

    def _connect_milvus(self):
        """连接 Milvus"""
        try:
            connections.connect(
                alias="default", host=self.milvus_host, port=self.milvus_port
            )
            logger.info(f"Connected to Milvus: {self.milvus_host}:{self.milvus_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}", exc_info=True)
            raise

    def _init_collection(self):
        """初始化 Milvus Collection"""
        try:
            # 检查 Collection 是否存在
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                self.collection.load()
                logger.info(f"Loaded existing collection: {self.collection_name}")
                return

            # 创建 Collection
            fields = [
                FieldSchema(
                    name="memory_id",
                    dtype=DataType.VARCHAR,
                    max_length=64,
                    is_primary=True,
                ),
                FieldSchema(
                    name="user_id", dtype=DataType.VARCHAR, max_length=64
                ),
                FieldSchema(
                    name="content", dtype=DataType.VARCHAR, max_length=2048
                ),
                FieldSchema(
                    name="memory_type", dtype=DataType.VARCHAR, max_length=32
                ),
                FieldSchema(
                    name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536
                ),
                FieldSchema(name="created_at", dtype=DataType.INT64),
                FieldSchema(name="importance", dtype=DataType.FLOAT),
                FieldSchema(name="access_count", dtype=DataType.INT32),
                FieldSchema(name="last_accessed", dtype=DataType.INT64),
            ]

            schema = CollectionSchema(
                fields=fields, description="Agent Long-term Memory"
            )
            self.collection = Collection(name=self.collection_name, schema=schema)

            # 创建索引
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            }
            self.collection.create_index(
                field_name="embedding", index_params=index_params
            )
            self.collection.load()

            logger.info(f"Created and indexed collection: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}", exc_info=True)
            raise

    async def store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "conversation",
        importance: Optional[float] = None,
        auto_evaluate_importance: bool = True,
    ) -> str:
        """
        存储记忆

        Args:
            user_id: 用户 ID
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性 (0.0-1.0)，如果为 None 则自动评估
            auto_evaluate_importance: 是否自动评估重要性

        Returns:
            memory_id: 记忆 ID
        """
        try:
            # 生成 embedding
            embedding = await self._get_embedding(content)

            # 评估重要性
            if importance is None and auto_evaluate_importance:
                importance = await self._evaluate_importance(content)
            elif importance is None:
                importance = 0.5  # 默认值

            # 生成 memory_id
            memory_id = str(uuid.uuid4())
            current_timestamp = int(datetime.now().timestamp())

            # 准备数据
            memory_data = [
                {
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "content": content,
                    "memory_type": memory_type,
                    "embedding": embedding,
                    "created_at": current_timestamp,
                    "importance": float(importance),
                    "access_count": 0,
                    "last_accessed": current_timestamp,
                }
            ]

            # 插入数据
            self.collection.insert(memory_data)
            self.collection.flush()

            logger.info(
                f"Memory stored: memory_id={memory_id}, user_id={user_id}, "
                f"importance={importance:.2f}"
            )

            return memory_id

        except Exception as e:
            logger.error(f"Failed to store memory: {e}", exc_info=True)
            raise

    async def retrieve_memory(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        time_decay_enabled: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        检索相关记忆（带 Ebbinghaus 遗忘曲线衰减）

        Args:
            user_id: 用户 ID
            query: 查询文本
            top_k: 返回数量
            time_decay_enabled: 是否启用时间衰减

        Returns:
            记忆列表，按综合得分排序
        """
        try:
            # 生成查询向量
            query_embedding = await self._get_embedding(query)

            # 向量检索 (过采样)
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k * 3,  # 过采样，后续重排序
                expr=f'user_id == "{user_id}"',
                output_fields=[
                    "memory_id",
                    "content",
                    "memory_type",
                    "importance",
                    "created_at",
                    "access_count",
                    "last_accessed",
                ],
            )

            # 后处理: 综合打分
            memories = []
            current_time = datetime.now().timestamp()

            for hits in results:
                for hit in hits:
                    entity = hit.entity

                    # 1. 向量相似度分数 (L2 距离，越小越好)
                    vector_score = 1.0 / (1.0 + hit.distance)

                    # 2. Ebbinghaus 遗忘曲线衰减
                    if time_decay_enabled:
                        time_diff_days = (
                            current_time - entity.get("created_at", current_time)
                        ) / 86400
                        # 指数衰减: decay = e^(-t/τ), τ = half_life / ln(2)
                        tau = self.time_decay_half_life_days / np.log(2)
                        decay_factor = np.exp(-time_diff_days / tau)
                    else:
                        decay_factor = 1.0

                    # 3. 访问频率增强
                    access_count = entity.get("access_count", 0)
                    access_boost = min(access_count * 0.05, 0.3)  # 最多提升 30%

                    # 4. 重要性权重
                    importance = entity.get("importance", 0.5)

                    # 综合得分
                    composite_score = (
                        vector_score * 0.5  # 向量相似度权重 50%
                        + importance * 0.2  # 重要性权重 20%
                        + decay_factor * 0.2  # 时间衰减权重 20%
                        + access_boost * 0.1  # 访问频率权重 10%
                    )

                    memories.append(
                        {
                            "memory_id": entity.get("memory_id"),
                            "content": entity.get("content"),
                            "memory_type": entity.get("memory_type"),
                            "importance": entity.get("importance"),
                            "created_at": entity.get("created_at"),
                            "access_count": access_count,
                            "score": composite_score,
                            "vector_score": vector_score,
                            "decay_factor": decay_factor,
                            "access_boost": access_boost,
                            "days_ago": (current_time - entity.get("created_at", current_time))
                            / 86400,
                        }
                    )

            # 按综合得分排序
            memories.sort(key=lambda x: x["score"], reverse=True)

            # 返回 top_k
            top_memories = memories[:top_k]

            # 更新访问统计 (异步，不阻塞)
            for memory in top_memories:
                try:
                    await self._update_memory_access(memory["memory_id"])
                except Exception as e:
                    logger.warning(f"Failed to update access count: {e}")

            logger.info(
                f"Retrieved {len(top_memories)} memories for user {user_id}, "
                f"query: {query[:50]}..."
            )

            return top_memories

        except Exception as e:
            logger.error(f"Failed to retrieve memory: {e}", exc_info=True)
            return []

    async def _update_memory_access(self, memory_id: str):
        """
        更新记忆访问统计

        注意: Milvus 不支持原地更新，需要先查询再重新插入
        """
        try:
            # 1. 查询当前记录
            expr = f'memory_id == "{memory_id}"'
            results = self.collection.query(
                expr=expr,
                output_fields=[
                    "memory_id",
                    "user_id",
                    "content",
                    "memory_type",
                    "embedding",
                    "created_at",
                    "importance",
                    "access_count",
                    "last_accessed",
                ],
                limit=1,
            )

            if not results:
                logger.warning(f"Memory not found for update: {memory_id}")
                return

            entity = results[0]

            # 2. 更新访问统计
            current_timestamp = int(datetime.now().timestamp())
            entity["access_count"] = entity.get("access_count", 0) + 1
            entity["last_accessed"] = current_timestamp

            # 3. 删除旧记录
            self.collection.delete(expr=expr)

            # 4. 插入更新后的记录
            self.collection.insert([entity])
            self.collection.flush()

            logger.debug(
                f"Memory access updated: {memory_id}, access_count={entity['access_count']}"
            )

        except Exception as e:
            logger.error(f"Failed to update memory access: {e}", exc_info=True)

    async def delete_memory(self, memory_id: str):
        """
        删除记忆

        Args:
            memory_id: 记忆 ID
        """
        try:
            expr = f'memory_id == "{memory_id}"'
            self.collection.delete(expr=expr)
            self.collection.flush()

            logger.info(f"Memory deleted: {memory_id}")

        except Exception as e:
            logger.error(f"Failed to delete memory: {e}", exc_info=True)
            raise

    async def list_user_memories(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出用户的所有记忆

        Args:
            user_id: 用户 ID
            limit: 返回数量
            offset: 偏移量

        Returns:
            记忆列表
        """
        try:
            expr = f'user_id == "{user_id}"'
            results = self.collection.query(
                expr=expr,
                output_fields=[
                    "memory_id",
                    "content",
                    "memory_type",
                    "importance",
                    "created_at",
                    "access_count",
                ],
                limit=limit,
                offset=offset,
            )

            memories = []
            current_time = datetime.now().timestamp()

            for entity in results:
                memories.append(
                    {
                        "memory_id": entity.get("memory_id"),
                        "content": entity.get("content"),
                        "memory_type": entity.get("memory_type"),
                        "importance": entity.get("importance"),
                        "created_at": entity.get("created_at"),
                        "access_count": entity.get("access_count"),
                        "days_ago": (current_time - entity.get("created_at", current_time))
                        / 86400,
                    }
                )

            logger.info(f"Listed {len(memories)} memories for user {user_id}")

            return memories

        except Exception as e:
            logger.error(f"Failed to list memories: {e}", exc_info=True)
            return []

    async def _get_embedding(self, text: str) -> List[float]:
        """
        调用 Model Adapter 获取 embedding

        Args:
            text: 文本

        Returns:
            embedding 向量
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.embedding_service_url}/api/v1/embeddings",
                    json={"input": text, "model": "text-embedding-ada-002"},
                )

                if response.status_code != 200:
                    raise Exception(
                        f"Embedding service error: {response.status_code}, {response.text}"
                    )

                data = response.json()
                embedding = data["data"][0]["embedding"]

                return embedding

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}", exc_info=True)
            raise

    async def _evaluate_importance(
        self, content: str, context: Optional[Dict] = None
    ) -> float:
        """
        评估记忆重要性

        使用规则+关键词的方式（简化版）
        生产环境应使用 LLM 评估

        Args:
            content: 记忆内容
            context: 上下文（可选）

        Returns:
            重要性分数 (0.0-1.0)
        """
        score = 0.5  # 基础分

        # 重要关键词
        important_keywords = [
            "重要",
            "记住",
            "关键",
            "必须",
            "务必",
            "一定",
            "千万",
            "注意",
            "警告",
            "紧急",
            "名字",
            "生日",
            "地址",
            "电话",
            "邮箱",
            "喜欢",
            "讨厌",
            "爱好",
            "兴趣",
        ]

        for keyword in important_keywords:
            if keyword in content:
                score += 0.05

        # 问句通常不太重要
        if "?" in content or "？" in content or "吗" in content:
            score -= 0.1

        # 长句通常更重要
        if len(content) > 50:
            score += 0.05
        if len(content) > 100:
            score += 0.05

        # 短句通常不太重要
        if len(content) < 10:
            score -= 0.1

        # 限制范围
        score = max(0.0, min(1.0, score))

        return score

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        try:
            stats = {
                "collection_name": self.collection_name,
                "num_entities": self.collection.num_entities,
                "time_decay_half_life_days": self.time_decay_half_life_days,
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            return {}

    async def merge_similar_memories(
        self, user_id: str, similarity_threshold: float = 0.95, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        合并相似的记忆

        Args:
            user_id: 用户ID
            similarity_threshold: 相似度阈值（0-1），越高越严格
            dry_run: 是否仅预览，不实际合并

        Returns:
            合并统计信息
        """
        try:
            # 获取用户的所有记忆
            all_memories = await self.list_user_memories(user_id, limit=1000)

            if len(all_memories) < 2:
                return {"merged_count": 0, "groups": []}

            # 计算所有记忆对之间的相似度
            merged_count = 0
            merged_groups = []

            for i, mem1 in enumerate(all_memories):
                if mem1.get("merged"):
                    continue

                similar_group = [mem1]

                for j, mem2 in enumerate(all_memories[i + 1 :], start=i + 1):
                    if mem2.get("merged"):
                        continue

                    # 计算相似度（使用向量检索）
                    query_embedding = await self._get_embedding(mem1["content"])
                    search_results = self.collection.search(
                        data=[query_embedding],
                        anns_field="embedding",
                        param={"metric_type": "L2", "params": {"nprobe": 10}},
                        limit=1,
                        expr=f'memory_id == "{mem2["memory_id"]}"',
                        output_fields=["memory_id"],
                    )

                    if search_results and len(search_results[0]) > 0:
                        distance = search_results[0][0].distance
                        similarity = 1.0 / (1.0 + distance)

                        if similarity >= similarity_threshold:
                            similar_group.append(mem2)
                            mem2["merged"] = True

                if len(similar_group) > 1:
                    merged_groups.append(similar_group)

                    if not dry_run:
                        # 合并: 保留重要性最高的，删除其他
                        best_memory = max(similar_group, key=lambda x: x.get("importance", 0))

                        for mem in similar_group:
                            if mem["memory_id"] != best_memory["memory_id"]:
                                await self.delete_memory(mem["memory_id"])
                                merged_count += 1

            logger.info(
                f"Memory merge completed: user={user_id}, "
                f"merged_count={merged_count}, groups={len(merged_groups)}, "
                f"dry_run={dry_run}"
            )

            return {"merged_count": merged_count, "groups": merged_groups}

        except Exception as e:
            logger.error(f"Failed to merge memories: {e}", exc_info=True)
            return {"merged_count": 0, "groups": [], "error": str(e)}

    async def cleanup_old_memories(
        self, user_id: str, days_threshold: int = 90, importance_threshold: float = 0.3
    ) -> int:
        """
        清理旧的低重要性记忆

        Args:
            user_id: 用户ID
            days_threshold: 天数阈值，超过此天数的记忆才考虑清理
            importance_threshold: 重要性阈值，低于此值才考虑清理

        Returns:
            清理的记忆数量
        """
        try:
            current_timestamp = int(datetime.now().timestamp())
            cutoff_timestamp = current_timestamp - (days_threshold * 86400)

            # 查询符合条件的记忆
            expr = f'user_id == "{user_id}" and created_at < {cutoff_timestamp} and importance < {importance_threshold}'

            results = self.collection.query(
                expr=expr, output_fields=["memory_id"], limit=10000
            )

            deleted_count = 0
            for entity in results:
                memory_id = entity.get("memory_id")
                await self.delete_memory(memory_id)
                deleted_count += 1

            logger.info(
                f"Cleaned up {deleted_count} old memories for user {user_id}, "
                f"threshold: {days_threshold} days, importance < {importance_threshold}"
            )

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup memories: {e}", exc_info=True)
            return 0

    async def summarize_memories(
        self, user_id: str, start_date: Optional[int] = None, end_date: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        总结用户的记忆

        Args:
            user_id: 用户ID
            start_date: 开始时间戳（可选）
            end_date: 结束时间戳（可选）

        Returns:
            记忆总结
        """
        try:
            # 构建查询表达式
            expr = f'user_id == "{user_id}"'
            if start_date:
                expr += f" and created_at >= {start_date}"
            if end_date:
                expr += f" and created_at <= {end_date}"

            # 查询记忆
            results = self.collection.query(
                expr=expr,
                output_fields=[
                    "content",
                    "memory_type",
                    "importance",
                    "created_at",
                    "access_count",
                ],
                limit=10000,
            )

            if not results:
                return {
                    "total_memories": 0,
                    "by_type": {},
                    "avg_importance": 0.0,
                    "most_accessed": [],
                    "most_important": [],
                }

            # 统计分析
            total_memories = len(results)
            by_type = {}
            importances = []
            accessed_memories = []

            for entity in results:
                # 按类型统计
                memory_type = entity.get("memory_type", "unknown")
                by_type[memory_type] = by_type.get(memory_type, 0) + 1

                # 收集重要性
                importance = entity.get("importance", 0)
                importances.append(importance)

                # 收集访问统计
                accessed_memories.append(
                    {
                        "content": entity.get("content", "")[:100],
                        "access_count": entity.get("access_count", 0),
                        "importance": importance,
                    }
                )

            # 排序
            accessed_memories.sort(key=lambda x: x["access_count"], reverse=True)
            most_accessed = accessed_memories[:5]

            accessed_memories.sort(key=lambda x: x["importance"], reverse=True)
            most_important = accessed_memories[:5]

            avg_importance = sum(importances) / len(importances) if importances else 0.0

            summary = {
                "user_id": user_id,
                "total_memories": total_memories,
                "by_type": by_type,
                "avg_importance": round(avg_importance, 3),
                "most_accessed": most_accessed,
                "most_important": most_important,
                "date_range": {
                    "start": start_date,
                    "end": end_date,
                },
            }

            logger.info(f"Summarized {total_memories} memories for user {user_id}")

            return summary

        except Exception as e:
            logger.error(f"Failed to summarize memories: {e}", exc_info=True)
            return {
                "total_memories": 0,
                "error": str(e),
            }

    async def get_memory_timeline(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取用户的记忆时间线（按时间倒序）

        Args:
            user_id: 用户ID
            limit: 返回数量

        Returns:
            记忆时间线
        """
        try:
            expr = f'user_id == "{user_id}"'
            results = self.collection.query(
                expr=expr,
                output_fields=[
                    "memory_id",
                    "content",
                    "memory_type",
                    "importance",
                    "created_at",
                    "access_count",
                ],
                limit=limit,
            )

            # 按创建时间排序（倒序）
            memories = sorted(
                results, key=lambda x: x.get("created_at", 0), reverse=True
            )

            timeline = []
            for entity in memories:
                created_at = entity.get("created_at", 0)
                timeline.append(
                    {
                        "memory_id": entity.get("memory_id"),
                        "content": entity.get("content"),
                        "memory_type": entity.get("memory_type"),
                        "importance": entity.get("importance"),
                        "created_at": created_at,
                        "created_date": datetime.fromtimestamp(created_at).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "access_count": entity.get("access_count"),
                    }
                )

            logger.info(f"Retrieved timeline of {len(timeline)} memories for user {user_id}")

            return timeline

        except Exception as e:
            logger.error(f"Failed to get memory timeline: {e}", exc_info=True)
            return []
