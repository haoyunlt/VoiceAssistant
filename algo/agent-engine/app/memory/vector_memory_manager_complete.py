"""
Vector Memory Manager - 完整实现
基于向量的记忆管理系统
"""

import logging
import os
import time
import uuid

import httpx
import numpy as np

logger = logging.getLogger(__name__)

try:
    from pymilvus import DataType, MilvusClient

    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    logger.warning("Milvus not available. Vector memory will not work.")


class Memory:
    """记忆对象"""

    def __init__(
        self, id: str, conversation_id: str, content: str, timestamp: int, metadata: dict = None
    ):
        self.id = id
        self.conversation_id = conversation_id
        self.content = content
        self.timestamp = timestamp
        self.metadata = metadata or {}


class VectorMemoryManager:
    """基于向量的记忆管理"""

    def __init__(
        self, milvus_host: str = None, milvus_port: str = None, model_adapter_url: str = None
    ):
        self.milvus_host = milvus_host or os.getenv("MILVUS_HOST", "localhost")
        self.milvus_port = milvus_port or os.getenv("MILVUS_PORT", "19530")
        self.model_adapter_url = model_adapter_url or os.getenv(
            "MODEL_ADAPTER_URL", "http://model-adapter:8005"
        )

        self.collection_name = "agent_memory"
        self.dim = 1536  # OpenAI embedding dimension

        if MILVUS_AVAILABLE:
            self.client = MilvusClient(uri=f"http://{self.milvus_host}:{self.milvus_port}")
            self._init_collection()
        else:
            self.client = None
            logger.warning("Milvus client not initialized")

    def _init_collection(self) -> None:
        """初始化 Milvus collection"""
        if not self.client:
            return

        # 检查 collection 是否存在
        if self.client.has_collection(self.collection_name):
            logger.info(f"Collection {self.collection_name} already exists")
            return

        # 创建 collection
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)

        schema.add_field(
            field_name="memory_id", datatype=DataType.VARCHAR, max_length=64, is_primary=True
        )
        schema.add_field(field_name="conversation_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=2000)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self.dim)
        schema.add_field(field_name="timestamp", datatype=DataType.INT64)

        # 创建索引参数
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="IP",  # Inner Product (cosine similarity for normalized vectors)
            params={"nlist": 1024},
        )

        # 创建 collection
        self.client.create_collection(
            collection_name=self.collection_name, schema=schema, index_params=index_params
        )

        logger.info(f"Created collection: {self.collection_name}")

    async def store_memory(
        self, conversation_id: str, content: str, metadata: dict = None
    ) -> Memory:
        """
        存储记忆（向量化）

        Args:
            conversation_id: 对话 ID
            content: 记忆内容
            metadata: 元数据

        Returns:
            Memory: 存储的记忆对象
        """
        if not self.client:
            logger.warning("Milvus client not available")
            return None

        try:
            # 生成记忆 ID
            memory_id = f"mem_{uuid.uuid4().hex[:16]}"

            # 1. 生成向量
            embedding = await self._get_embedding(content)

            # 2. 插入 Milvus
            data = [
                {
                    "memory_id": memory_id,
                    "conversation_id": conversation_id,
                    "content": content,
                    "embedding": embedding,
                    "timestamp": int(time.time()),
                }
            ]

            # 添加元数据字段
            if metadata:
                data[0].update(metadata)

            self.client.insert(collection_name=self.collection_name, data=data)

            logger.info(f"Stored memory: {memory_id}")

            return Memory(
                id=memory_id,
                conversation_id=conversation_id,
                content=content,
                timestamp=int(time.time()),
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return None

    async def search_memory(
        self, query: str, conversation_id: str | None = None, top_k: int = 5
    ) -> list[Memory]:
        """
        向量检索相关记忆

        Args:
            query: 查询文本
            conversation_id: 可选的对话 ID 过滤
            top_k: 返回数量

        Returns:
            List[Memory]: 检索到的记忆列表
        """
        if not self.client:
            logger.warning("Milvus client not available")
            return []

        try:
            # 1. 查询向量化
            query_embedding = await self._get_embedding(query)

            # 2. 构建过滤表达式
            filter_expr = ""
            if conversation_id:
                filter_expr = f'conversation_id == "{conversation_id}"'

            # 3. 向量搜索
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=top_k,
                filter=filter_expr,
                output_fields=["memory_id", "conversation_id", "content", "timestamp"],
            )

            # 4. 转换为 Memory 对象
            memories = []
            for hits in results:
                for hit in hits:
                    memories.append(
                        Memory(
                            id=hit.get("memory_id", ""),
                            conversation_id=hit.get("conversation_id", ""),
                            content=hit.get("content", ""),
                            timestamp=hit.get("timestamp", 0),
                            metadata={"score": hit.get("distance", 0.0)},
                        )
                    )

            logger.info(f"Found {len(memories)} memories for query: {query}")
            return memories

        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return []

    async def get_conversation_memories(
        self, conversation_id: str, limit: int = 10
    ) -> list[Memory]:
        """
        获取指定对话的所有记忆

        Args:
            conversation_id: 对话 ID
            limit: 最大数量

        Returns:
            List[Memory]: 记忆列表
        """
        if not self.client:
            return []

        try:
            # 查询该对话的所有记忆
            results = self.client.query(
                collection_name=self.collection_name,
                filter=f'conversation_id == "{conversation_id}"',
                output_fields=["memory_id", "conversation_id", "content", "timestamp"],
                limit=limit,
            )

            memories = []
            for item in results:
                memories.append(
                    Memory(
                        id=item.get("memory_id", ""),
                        conversation_id=item.get("conversation_id", ""),
                        content=item.get("content", ""),
                        timestamp=item.get("timestamp", 0),
                    )
                )

            # 按时间排序
            memories.sort(key=lambda m: m.timestamp)

            return memories

        except Exception as e:
            logger.error(f"Failed to get conversation memories: {e}")
            return []

    async def delete_conversation_memories(self, conversation_id: str):
        """删除指定对话的所有记忆"""
        if not self.client:
            return

        try:
            self.client.delete(
                collection_name=self.collection_name,
                filter=f'conversation_id == "{conversation_id}"',
            )
            logger.info(f"Deleted memories for conversation: {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to delete memories: {e}")

    async def _get_embedding(self, text: str) -> list[float]:
        """
        获取文本向量

        Args:
            text: 文本内容

        Returns:
            List[float]: 向量
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.model_adapter_url}/api/v1/embedding/create",
                    json={"input": text, "model": "text-embedding-3-small"},
                )
                response.raise_for_status()

                data = response.json()
                embedding = data["data"][0]["embedding"]

                # 归一化向量（用于 IP 距离度量）
                embedding_np = np.array(embedding)
                normalized = embedding_np / np.linalg.norm(embedding_np)

                return normalized.tolist()

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            # 返回零向量作为降级
            return [0.0] * self.dim

    def get_stats(self) -> dict:
        """获取记忆统计信息"""
        if not self.client:
            return {"error": "Milvus not available"}

        try:
            stats = self.client.get_collection_stats(self.collection_name)
            return {
                "total_memories": stats.get("row_count", 0),
                "collection_name": self.collection_name,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
