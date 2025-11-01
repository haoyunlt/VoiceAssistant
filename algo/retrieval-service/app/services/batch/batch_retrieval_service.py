"""
Batch Retrieval Service - 批量检索服务

功能:
- 动态批处理
- Embedding批量编码
- 向量检索批量查询
- Rerank批量处理

目标:
- QPS提升≥2x
- 单请求延迟增加≤20ms
"""

import asyncio
import time

from app.core.dynamic_batcher import DynamicBatcher
from app.models.retrieval import HybridRequest, HybridResponse, RetrievalDocument
from app.observability.logging import logger


class BatchRetrievalService:
    """批量检索服务"""

    def __init__(
        self,
        max_batch_size: int = 32,
        max_wait_ms: float = 50.0,
    ):
        """
        初始化批量检索服务

        Args:
            max_batch_size: 最大批大小
            max_wait_ms: 最大等待时间（毫秒）
        """
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms

        # 创建各类batcher
        self.embedding_batcher = DynamicBatcher(
            batch_func=self._batch_embed,
            max_batch_size=max_batch_size,
            max_wait_ms=max_wait_ms,
            name="embedding",
        )

        self.vector_search_batcher = DynamicBatcher(
            batch_func=self._batch_vector_search,
            max_batch_size=max_batch_size // 2,  # 向量搜索批次小一些
            max_wait_ms=max_wait_ms,
            name="vector_search",
        )

        self.rerank_batcher = DynamicBatcher(
            batch_func=self._batch_rerank,
            max_batch_size=max_batch_size,
            max_wait_ms=max_wait_ms * 2,  # Rerank可以等久一点
            name="rerank",
        )

        logger.info(
            f"Batch retrieval service initialized: "
            f"max_batch_size={max_batch_size}, max_wait_ms={max_wait_ms}"
        )

    async def start(self):
        """启动所有batcher"""
        await asyncio.gather(
            self.embedding_batcher.start(),
            self.vector_search_batcher.start(),
            self.rerank_batcher.start(),
        )
        logger.info("Batch retrieval service started")

    async def stop(self):
        """停止所有batcher"""
        await asyncio.gather(
            self.embedding_batcher.stop(),
            self.vector_search_batcher.stop(),
            self.rerank_batcher.stop(),
        )
        logger.info("Batch retrieval service stopped")

    async def batch_hybrid_search(self, requests: list[HybridRequest]) -> list[HybridResponse]:
        """
        批量混合检索

        Args:
            requests: 检索请求列表

        Returns:
            检索响应列表
        """
        start_time = time.time()

        try:
            # 1. 批量embedding
            embeddings = await self._get_embeddings_batch([req.query for req in requests])

            # 2. 批量向量检索
            vector_results_batch = await self._search_vectors_batch(embeddings, requests)

            # 3. 批量BM25检索（可以并行）
            bm25_results_batch = await self._search_bm25_batch(requests)

            # 4. 对每个请求融合结果
            responses = []
            for i, req in enumerate(requests):
                # 融合vector和bm25
                fused_docs = self._fuse_results(vector_results_batch[i], bm25_results_batch[i])

                # 构建响应
                response = HybridResponse(
                    documents=fused_docs,
                    query=req.query,
                    vector_count=len(vector_results_batch[i]),
                    bm25_count=len(bm25_results_batch[i]),
                    reranked=False,
                    latency_ms=(time.time() - start_time) * 1000,
                )
                responses.append(response)

            # 5. 批量rerank（如果需要）
            if any(req.enable_rerank for req in requests):
                responses = await self._rerank_batch(responses, requests)

            logger.info(
                f"Batch hybrid search completed: {len(requests)} requests "
                f"in {(time.time() - start_time) * 1000:.1f}ms"
            )

            return responses

        except Exception as e:
            logger.error(f"Batch hybrid search failed: {e}", exc_info=True)
            # 返回空结果
            return [
                HybridResponse(
                    documents=[],
                    query=req.query,
                    vector_count=0,
                    bm25_count=0,
                    reranked=False,
                    latency_ms=0,
                )
                for req in requests
            ]

    async def _get_embeddings_batch(self, queries: list[str]) -> list[list[float]]:
        """批量获取embeddings"""
        # 使用embedding batcher
        tasks = [self.embedding_batcher.process(q) for q in queries]
        return await asyncio.gather(*tasks)

    async def _batch_embed(self, queries: list[str]) -> list[list[float]]:
        """批量embedding实现"""
        # 这里应该调用实际的embedding服务
        # 简化实现：返回mock embeddings
        await asyncio.sleep(0.02 * len(queries) / 32)  # 模拟批处理延迟

        import numpy as np

        return [np.random.randn(384).tolist() for _ in queries]

    async def _search_vectors_batch(
        self, _embeddings: list[list[float]], requests: list[HybridRequest]
    ) -> list[list[RetrievalDocument]]:
        """批量向量检索"""
        # 这里应该调用Milvus的批量搜索API
        # 简化实现：返回mock结果
        await asyncio.sleep(0.05)

        results = []
        for req in requests:
            docs = [
                RetrievalDocument(
                    id=f"doc_{i}",
                    chunk_id=f"chunk_{i}",
                    content=f"Vector doc {i} for: {req.query}",
                    score=0.9 - i * 0.05,
                    metadata={},
                )
                for i in range(10)
            ]
            results.append(docs)

        return results

    async def _search_bm25_batch(
        self, requests: list[HybridRequest]
    ) -> list[list[RetrievalDocument]]:
        """批量BM25检索"""
        # 这里应该调用ES的multi-search API
        # 简化实现：返回mock结果
        await asyncio.sleep(0.03)

        results = []
        for req in requests:
            docs = [
                RetrievalDocument(
                    id=f"bm25_doc_{i}",
                    chunk_id=f"bm25_chunk_{i}",
                    content=f"BM25 doc {i} for: {req.query}",
                    score=0.85 - i * 0.05,
                    metadata={},
                )
                for i in range(10)
            ]
            results.append(docs)

        return results

    def _fuse_results(
        self,
        vector_docs: list[RetrievalDocument],
        bm25_docs: list[RetrievalDocument],
        _k: int = 60,
    ) -> list[RetrievalDocument]:
        """RRF融合"""
        # 简化实现：直接合并并按分数排序
        all_docs = vector_docs + bm25_docs

        # 去重
        seen_ids = set()
        unique_docs = []
        for doc in all_docs:
            if doc.id not in seen_ids:
                unique_docs.append(doc)
                seen_ids.add(doc.id)

        # 排序
        unique_docs.sort(key=lambda d: d.score, reverse=True)
        return unique_docs[:20]

    async def _rerank_batch(
        self, responses: list[HybridResponse], requests: list[HybridRequest]
    ) -> list[HybridResponse]:
        """批量rerank"""
        # 收集需要rerank的
        to_rerank = []
        rerank_indices = []

        for i, (resp, req) in enumerate(zip(responses, requests, strict=False)):
            if req.enable_rerank and resp.documents:
                to_rerank.append((req.query, resp.documents))
                rerank_indices.append(i)

        if not to_rerank:
            return responses

        # 批量rerank
        reranked_docs_list = await self._batch_rerank(to_rerank)

        # 更新响应
        for idx, reranked_docs in zip(rerank_indices, reranked_docs_list, strict=False):
            responses[idx].documents = reranked_docs
            responses[idx].reranked = True

        return responses

    async def _batch_rerank(self, query_docs_pairs: list[tuple]) -> list[list[RetrievalDocument]]:
        """批量rerank实现"""
        # 这里应该调用cross-encoder的批量推理
        # 简化实现：返回原结果
        await asyncio.sleep(0.01 * len(query_docs_pairs) / 32)

        return [docs for _, docs in query_docs_pairs]

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "max_batch_size": self.max_batch_size,
            "max_wait_ms": self.max_wait_ms,
            "embedding_batcher": self.embedding_batcher.get_stats(),
            "vector_search_batcher": self.vector_search_batcher.get_stats(),
            "rerank_batcher": self.rerank_batcher.get_stats(),
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = BatchRetrievalService()
        await service.start()

        # 创建批量请求
        requests = [
            HybridRequest(query=f"Python tutorial {i}", top_k=10, enable_rerank=True)
            for i in range(50)
        ]

        start_time = time.time()
        await service.batch_hybrid_search(requests)
        elapsed = time.time() - start_time

        print("\nBatch retrieval completed:")
        print(f"  Requests: {len(requests)}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  QPS: {len(requests) / elapsed:.1f}")
        print(f"  Avg latency: {elapsed / len(requests) * 1000:.1f}ms")
        print(f"\nStats: {service.get_stats()}")

        await service.stop()

    asyncio.run(test())
