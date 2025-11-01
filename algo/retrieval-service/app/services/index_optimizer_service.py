"""向量索引优化服务"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class IndexOptimizerService:
    """
    向量索引优化服务

    优化Milvus HNSW索引参数以提升性能：
    1. M参数：控制图的连接度（默认16，范围4-64）
    2. efConstruction：构建索引时的候选数（默认200，范围8-512）
    3. ef：搜索时的候选数（默认影响召回率和性能）
    """

    def __init__(self, milvus_client):
        """
        初始化索引优化器

        Args:
            milvus_client: Milvus客户端
        """
        self.milvus_client = milvus_client

        # 预定义的优化配置
        self.optimization_profiles = {
            "balanced": {
                "M": 16,
                "efConstruction": 200,
                "ef": 64,
                "description": "平衡性能和召回率",
            },
            "high_performance": {
                "M": 8,
                "efConstruction": 100,
                "ef": 32,
                "description": "优化查询性能，稍微牺牲召回率",
            },
            "high_recall": {
                "M": 32,
                "efConstruction": 400,
                "ef": 128,
                "description": "优化召回率，稍微牺牲性能",
            },
            "large_scale": {
                "M": 12,
                "efConstruction": 150,
                "ef": 48,
                "description": "适合大规模数据集",
            },
        }

    async def optimize_collection(
        self,
        collection_name: str,
        profile: str = "balanced",
        custom_params: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """
        优化集合的索引参数

        Args:
            collection_name: 集合名称
            profile: 优化配置（balanced/high_performance/high_recall/large_scale）
            custom_params: 自定义参数

        Returns:
            优化结果
        """
        logger.info(f"Optimizing collection '{collection_name}' with profile '{profile}'")

        # 获取优化参数
        if custom_params:
            params = custom_params
        elif profile in self.optimization_profiles:
            params = self.optimization_profiles[profile].copy()
            params.pop("description", None)
        else:
            params = self.optimization_profiles["balanced"].copy()
            params.pop("description", None)

        try:
            # 1. 检查集合是否存在
            collection_exists = await self._check_collection_exists(collection_name)
            if not collection_exists:
                return {"success": False, "error": f"Collection '{collection_name}' does not exist"}

            # 2. 获取当前索引信息
            current_index = await self._get_current_index(collection_name)

            # 3. 删除旧索引
            if current_index:
                await self._drop_index(collection_name)

            # 4. 创建优化后的索引
            await self._create_optimized_index(collection_name, params)

            # 5. 验证新索引
            new_index = await self._get_current_index(collection_name)

            return {
                "success": True,
                "collection": collection_name,
                "profile": profile,
                "old_params": current_index.get("params", {}) if current_index else {},
                "new_params": params,
                "new_index": new_index,
            }

        except Exception as e:
            logger.error(f"Failed to optimize collection: {e}")
            return {"success": False, "collection": collection_name, "error": str(e)}

    async def benchmark_configurations(
        self, collection_name: str, test_queries: list[str], profiles: list[str] | None = None
    ) -> dict[str, Any]:
        """
        基准测试不同配置

        Args:
            collection_name: 集合名称
            test_queries: 测试查询列表
            profiles: 要测试的配置列表

        Returns:
            基准测试结果
        """
        if not profiles:
            profiles = ["balanced", "high_performance", "high_recall"]

        logger.info(f"Benchmarking {len(profiles)} profiles on collection '{collection_name}'")

        results = []

        for profile in profiles:
            logger.info(f"Testing profile: {profile}")

            # 应用配置
            opt_result = await self.optimize_collection(collection_name, profile)

            if not opt_result["success"]:
                results.append({"profile": profile, "error": opt_result["error"]})
                continue

            # 运行测试查询
            query_results = []
            total_time = 0.0

            for query in test_queries:
                import time

                start_time = time.time()

                # 执行搜索
                search_results = await self._execute_search(collection_name, query)

                end_time = time.time()
                query_time = (end_time - start_time) * 1000  # 转换为毫秒
                total_time += query_time

                query_results.append(
                    {"query": query, "time_ms": query_time, "results_count": len(search_results)}
                )

            avg_time = total_time / len(test_queries) if test_queries else 0

            results.append(
                {
                    "profile": profile,
                    "params": opt_result["new_params"],
                    "avg_query_time_ms": avg_time,
                    "query_results": query_results,
                }
            )

        # 找出最优配置
        best_profile = min(results, key=lambda x: x.get("avg_query_time_ms", float("inf")))

        return {
            "collection": collection_name,
            "profiles_tested": profiles,
            "results": results,
            "best_profile": best_profile["profile"],
            "best_avg_time_ms": best_profile.get("avg_query_time_ms", 0),
        }

    async def _check_collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        try:
            # 使用Milvus客户端检查
            # 这里是伪代码，实际实现依赖具体的Milvus客户端
            collections = await self.milvus_client.list_collections()
            return collection_name in collections
        except Exception as e:
            logger.error(f"Error checking collection: {e}")
            return False

    async def _get_current_index(self, collection_name: str) -> dict[str, Any] | None:
        """获取当前索引信息"""
        try:
            # 获取索引描述
            index_info = await self.milvus_client.describe_index(collection_name)
            return index_info
        except Exception as e:
            logger.warning(f"No index found for collection '{collection_name}': {e}")
            return None

    async def _drop_index(self, collection_name: str):
        """删除索引"""
        try:
            await self.milvus_client.drop_index(collection_name)
            logger.info(f"Dropped index for collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Error dropping index: {e}")
            raise

    async def _create_optimized_index(self, collection_name: str, params: dict[str, int]):
        """创建优化的索引"""
        try:
            # HNSW索引参数
            index_params = {
                "metric_type": "L2",  # 或 "IP" (内积)
                "index_type": "HNSW",
                "params": {"M": params["M"], "efConstruction": params["efConstruction"]},
            }

            # 创建索引
            await self.milvus_client.create_index(
                collection_name=collection_name,
                field_name="embedding",  # 向量字段名
                index_params=index_params,
            )

            # 设置搜索参数
            {"metric_type": "L2", "params": {"ef": params["ef"]}}

            logger.info(f"Created optimized index for collection '{collection_name}'")

        except Exception as e:
            logger.error(f"Error creating index: {e}")
            raise

    async def _execute_search(self, _collection_name: str, _query: str) -> list[dict[str, Any]]:
        """执行搜索（用于基准测试）"""
        try:
            # 这里需要先将query向量化
            # query_vector = await self.embed_query(query)

            # 执行搜索
            # results = await self.milvus_client.search(
            #     collection_name=collection_name,
            #     data=[query_vector],
            #     limit=10
            # )

            # 临时返回模拟结果
            return []

        except Exception as e:
            logger.error(f"Error executing search: {e}")
            return []

    def get_profile_recommendations(self, data_size: int, query_pattern: str) -> str:
        """
        根据数据规模和查询模式推荐配置

        Args:
            data_size: 数据集大小
            query_pattern: 查询模式（'batch'/'realtime'/'mixed'）

        Returns:
            推荐的profile名称
        """
        if data_size > 10_000_000:  # 1000万以上
            return "large_scale"
        elif query_pattern == "realtime":
            return "high_performance"
        elif query_pattern == "batch":
            return "high_recall"
        else:
            return "balanced"

    def calculate_memory_requirements(
        self, data_size: int, vector_dim: int, M: int
    ) -> dict[str, float]:
        """
        估算内存需求

        Args:
            data_size: 数据集大小
            vector_dim: 向量维度
            M: HNSW的M参数

        Returns:
            内存估算（MB）
        """
        # HNSW内存估算公式（近似）
        # Memory ≈ data_size * (vector_dim * 4 + M * 2 * 4) bytes

        vector_memory_mb = (data_size * vector_dim * 4) / (1024 * 1024)
        graph_memory_mb = (data_size * M * 2 * 4) / (1024 * 1024)
        total_memory_mb = vector_memory_mb + graph_memory_mb

        return {
            "vector_memory_mb": round(vector_memory_mb, 2),
            "graph_memory_mb": round(graph_memory_mb, 2),
            "total_memory_mb": round(total_memory_mb, 2),
            "total_memory_gb": round(total_memory_mb / 1024, 2),
        }
