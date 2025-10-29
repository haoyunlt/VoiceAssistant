"""
Hybrid Retrieval Service - 混合检索增强服务

图谱检索 + 向量检索 + BM25检索 + RRF融合
"""

import asyncio
import hashlib
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RetrievalResult:
    """检索结果"""

    def __init__(
        self,
        chunk_id: str,
        content: str,
        score: float,
        method: str,
        metadata: dict | None = None,
    ):
        self.chunk_id = chunk_id
        self.content = content
        self.score = score
        self.method = method  # "vector", "graph", "bm25"
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "method": self.method,
            "metadata": self.metadata,
        }


class HybridRetrievalService:
    """混合检索服务"""

    def __init__(
        self,
        neo4j_client,
        llm_entity_extractor,
        vector_service_url: str = "http://vector-store-adapter:8003",
        retrieval_service_url: str = "http://retrieval-service:8012",
        rerank_model: str = "bge-reranker-v2-m3",
    ):
        """
        初始化混合检索服务

        Args:
            neo4j_client: Neo4j客户端
            llm_entity_extractor: LLM实体提取器
            vector_service_url: 向量服务URL
            retrieval_service_url: 检索服务URL
            rerank_model: 重排模型
        """
        self.neo4j = neo4j_client
        self.extractor = llm_entity_extractor
        self.vector_service_url = vector_service_url
        self.retrieval_service_url = retrieval_service_url
        self.rerank_model = rerank_model
        self.client = httpx.AsyncClient(timeout=30.0)

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: str | None = None,
        knowledge_base_id: str | None = None,
        mode: str = "hybrid",
        enable_rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """
        混合检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            mode: 检索模式 (vector/graph/bm25/hybrid)
            enable_rerank: 是否启用重排

        Returns:
            检索结果列表
        """
        logger.info(f"Hybrid retrieval: query='{query[:50]}...', mode={mode}, top_k={top_k}")

        try:
            if mode == "vector":
                results = await self._vector_retrieve(query, top_k * 2, tenant_id)
            elif mode == "graph":
                results = await self._graph_retrieve(query, top_k * 2, tenant_id)
            elif mode == "bm25":
                results = await self._bm25_retrieve(query, top_k * 2, tenant_id)
            elif mode == "hybrid":
                results = await self._hybrid_retrieve(query, top_k * 2, tenant_id)
            else:
                raise ValueError(f"Unknown mode: {mode}")

            # 重排序
            if enable_rerank and len(results) > 0:
                results = await self._rerank(query, results, top_k)
            else:
                results = results[:top_k]

            logger.info(f"Retrieved {len(results)} results (mode={mode})")
            return [r.to_dict() for r in results]

        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}", exc_info=True)
            return []

    async def _hybrid_retrieve(
        self, query: str, top_k: int, tenant_id: str | None
    ) -> list[RetrievalResult]:
        """混合检索：并行三路检索 + RRF融合"""
        # 并行执行三路检索
        results = await asyncio.gather(
            self._vector_retrieve(query, top_k, tenant_id),
            self._graph_retrieve(query, top_k, tenant_id),
            self._bm25_retrieve(query, top_k, tenant_id),
            return_exceptions=True,
        )

        vector_results = results[0] if not isinstance(results[0], Exception) else []
        graph_results = results[1] if not isinstance(results[1], Exception) else []
        bm25_results = results[2] if not isinstance(results[2], Exception) else []

        # 记录异常
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                method = ["vector", "graph", "bm25"][i]
                logger.error(f"{method} retrieval failed: {result}")

        # RRF融合
        fused_results = self._rrf_fusion([vector_results, graph_results, bm25_results], k=60)

        logger.info(
            f"Fusion: vector={len(vector_results)}, graph={len(graph_results)}, "
            f"bm25={len(bm25_results)} -> {len(fused_results)}"
        )

        return fused_results[:top_k]

    async def _vector_retrieve(
        self, query: str, top_k: int, tenant_id: str | None
    ) -> list[RetrievalResult]:
        """向量检索"""
        try:
            response = await self.client.post(
                f"{self.vector_service_url}/api/v1/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "tenant_id": tenant_id,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    RetrievalResult(
                        chunk_id=item.get("chunk_id", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                        method="vector",
                        metadata=item.get("metadata", {}),
                    )
                )

            return results

        except httpx.HTTPError as e:
            logger.error(f"Vector retrieval HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            return []

    async def _graph_retrieve(
        self, query: str, top_k: int, tenant_id: str | None
    ) -> list[RetrievalResult]:
        """图谱检索：实体识别 + 多跳邻居 + 路径查找"""
        try:
            # Step 1: 从查询中提取实体
            query_entities = await self._extract_query_entities(query)

            if not query_entities:
                logger.info("No entities found in query for graph retrieval")
                return []

            logger.info(f"Query entities: {[e['text'] for e in query_entities]}")

            # Step 2: 对每个实体进行图检索
            all_results = []

            for entity in query_entities[:5]:  # 最多5个实体
                entity_text = entity["text"]

                # 2.1 获取1-2跳邻居
                neighbors = await self._get_entity_neighbors(entity_text, max_depth=2, limit=20)
                all_results.extend(neighbors)

                # 2.2 如果有多个实体，查找路径
                if len(query_entities) > 1:
                    for other_entity in query_entities[:5]:
                        if other_entity["text"] != entity_text:
                            paths = await self._find_entity_paths(
                                entity_text, other_entity["text"], max_depth=3
                            )
                            all_results.extend(paths)

            # Step 3: 去重和排序
            unique_results = self._deduplicate_results(all_results)

            return unique_results[:top_k]

        except Exception as e:
            logger.error(f"Graph retrieval failed: {e}", exc_info=True)
            return []

    async def _extract_query_entities(self, query: str) -> list[dict[str, Any]]:
        """从查询中提取实体"""
        try:
            entities = await self.extractor.extract_entities(query, domain="general")
            return entities
        except Exception as e:
            logger.error(f"Query entity extraction failed: {e}")
            return []

    async def _get_entity_neighbors(
        self, entity_text: str, max_depth: int = 2, limit: int = 20
    ) -> list[RetrievalResult]:
        """获取实体的邻居节点"""
        try:
            query = f"""
            MATCH path = (start)-[*1..{max_depth}]-(neighbor)
            WHERE start.text =~ '(?i).*' + $entity_text + '.*'
            WITH neighbor, length(path) as depth, path
            ORDER BY depth ASC
            LIMIT {limit}
            RETURN DISTINCT neighbor.text as text,
                   neighbor.label as label,
                   neighbor.chunk_id as chunk_id,
                   depth,
                   [rel in relationships(path) | type(rel)] as relation_types
            """

            results = await self.neo4j.execute_query(query, {"entity_text": entity_text})

            retrieval_results = []
            for record in results:
                # 构造结果文本
                content = self._format_graph_result(
                    entity_text,
                    record["text"],
                    record["relation_types"],
                    record["depth"],
                )

                # 计算得分（距离越近得分越高）
                score = 1.0 / (1 + record["depth"])

                retrieval_results.append(
                    RetrievalResult(
                        chunk_id=record.get("chunk_id", ""),
                        content=content,
                        score=score,
                        method="graph",
                        metadata={
                            "source_entity": entity_text,
                            "target_entity": record["text"],
                            "depth": record["depth"],
                            "relation_types": record["relation_types"],
                        },
                    )
                )

            return retrieval_results

        except Exception as e:
            logger.error(f"Get entity neighbors failed: {e}")
            return []

    async def _find_entity_paths(
        self, start_entity: str, end_entity: str, max_depth: int = 3
    ) -> list[RetrievalResult]:
        """查找两个实体之间的路径"""
        try:
            query = f"""
            MATCH path = shortestPath((start)-[*1..{max_depth}]-(end))
            WHERE start.text =~ '(?i).*' + $start_entity + '.*'
              AND end.text =~ '(?i).*' + $end_entity + '.*'
            RETURN [node in nodes(path) | node.text] as node_texts,
                   [rel in relationships(path) | type(rel)] as relation_types,
                   length(path) as path_length
            LIMIT 5
            """

            results = await self.neo4j.execute_query(
                query, {"start_entity": start_entity, "end_entity": end_entity}
            )

            retrieval_results = []
            for record in results:
                # 构造路径描述
                content = self._format_path_result(record["node_texts"], record["relation_types"])

                # 路径越短得分越高
                score = 1.0 / (1 + record["path_length"])

                retrieval_results.append(
                    RetrievalResult(
                        chunk_id="",  # 路径可能跨多个chunk
                        content=content,
                        score=score,
                        method="graph",
                        metadata={
                            "path_type": "entity_path",
                            "start_entity": start_entity,
                            "end_entity": end_entity,
                            "path_length": record["path_length"],
                            "node_texts": record["node_texts"],
                            "relation_types": record["relation_types"],
                        },
                    )
                )

            return retrieval_results

        except Exception as e:
            logger.error(f"Find entity paths failed: {e}")
            return []

    def _format_graph_result(
        self, source: str, target: str, relations: list[str], depth: int
    ) -> str:
        """格式化图检索结果"""
        if depth == 1:
            rel = relations[0] if relations else "RELATED_TO"
            return f"{source} {rel} {target}"
        else:
            rel_chain = " -> ".join(relations)
            return f"{source} is connected to {target} through: {rel_chain}"

    def _format_path_result(self, nodes: list[str], relations: list[str]) -> str:
        """格式化路径结果"""
        path_parts = []
        for i in range(len(nodes) - 1):
            path_parts.append(f"{nodes[i]} {relations[i]} {nodes[i + 1]}")
        return " | ".join(path_parts)

    async def _bm25_retrieve(
        self, query: str, top_k: int, tenant_id: str | None
    ) -> list[RetrievalResult]:
        """BM25关键词检索（通过retrieval-service）"""
        try:
            response = await self.client.post(
                f"{self.retrieval_service_url}/api/v1/search/bm25",
                json={
                    "query": query,
                    "top_k": top_k,
                    "tenant_id": tenant_id,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    RetrievalResult(
                        chunk_id=item.get("chunk_id", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                        method="bm25",
                        metadata=item.get("metadata", {}),
                    )
                )

            return results

        except httpx.HTTPError as e:
            logger.error(f"BM25 retrieval HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"BM25 retrieval failed: {e}")
            return []

    def _rrf_fusion(
        self, result_lists: list[list[RetrievalResult]], k: int = 60
    ) -> list[RetrievalResult]:
        """
        Reciprocal Rank Fusion (RRF)融合多路检索结果

        Args:
            result_lists: 多个检索结果列表
            k: RRF参数（默认60）

        Returns:
            融合后的结果列表
        """
        scores: dict[str, dict[str, Any]] = {}

        for result_list in result_lists:
            for rank, result in enumerate(result_list, start=1):
                # 使用content hash作为唯一标识
                result_key = self._get_result_key(result)

                if result_key not in scores:
                    scores[result_key] = {
                        "result": result,
                        "rrf_score": 0.0,
                        "methods": set(),
                    }

                # RRF公式: score += 1 / (k + rank)
                scores[result_key]["rrf_score"] += 1.0 / (k + rank)
                scores[result_key]["methods"].add(result.method)

        # 按RRF分数排序
        sorted_results = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)

        # 更新结果对象的分数
        fused_results = []
        for item in sorted_results:
            result = item["result"]
            result.score = item["rrf_score"]
            result.metadata["rrf_score"] = item["rrf_score"]
            result.metadata["methods"] = list(item["methods"])
            fused_results.append(result)

        return fused_results

    def _get_result_key(self, result: RetrievalResult) -> str:
        """获取结果的唯一标识"""
        if result.chunk_id:
            return result.chunk_id
        # 如果没有chunk_id（如图谱路径），使用内容hash
        return hashlib.md5(result.content.encode()).hexdigest()

    def _deduplicate_results(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """去重结果"""
        seen = set()
        unique_results = []

        for result in results:
            key = self._get_result_key(result)
            if key not in seen:
                seen.add(key)
                unique_results.append(result)

        return unique_results

    async def _rerank(
        self, query: str, results: list[RetrievalResult], top_k: int
    ) -> list[RetrievalResult]:
        """
        重排序

        Args:
            query: 查询文本
            results: 检索结果
            top_k: 返回结果数

        Returns:
            重排后的结果
        """
        if not results:
            return []

        try:
            # 准备重排请求
            [[query, result.content] for result in results]

            response = await self.client.post(
                f"{self.retrieval_service_url}/api/v1/rerank",
                json={"query": query, "documents": [r.content for r in results], "top_k": top_k},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

            # 更新结果分数
            reranked_indices = data.get("indices", [])
            reranked_scores = data.get("scores", [])

            reranked_results = []
            for idx, score in zip(reranked_indices, reranked_scores, strict=False):
                if idx < len(results):
                    result = results[idx]
                    result.score = score
                    result.metadata["rerank_score"] = score
                    reranked_results.append(result)

            logger.info(f"Reranked {len(results)} -> {len(reranked_results)} results")
            return reranked_results[:top_k]

        except Exception as e:
            logger.error(f"Rerank failed: {e}, returning original order")
            return results[:top_k]

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# 全局实例
_hybrid_retrieval_service: HybridRetrievalService | None = None


def get_hybrid_retrieval_service(neo4j_client, llm_entity_extractor) -> HybridRetrievalService:
    """获取混合检索服务实例（单例）"""
    global _hybrid_retrieval_service

    if _hybrid_retrieval_service is None:
        _hybrid_retrieval_service = HybridRetrievalService(neo4j_client, llm_entity_extractor)

    return _hybrid_retrieval_service
