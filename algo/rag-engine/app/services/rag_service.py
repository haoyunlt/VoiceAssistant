"""RAG服务 - 整合检索、生成、引用."""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.core.answer_generator import AnswerGenerator
from app.core.citation_generator import CitationGenerator
from app.core.context_builder import ContextBuilder
from app.core.query_rewriter import QueryRewriter
from app.infrastructure.retrieval_client import RetrievalClient

logger = logging.getLogger(__name__)


class RAGService:
    """RAG检索增强生成服务."""

    def __init__(
        self,
        retrieval_client: RetrievalClient,
        llm_client: AsyncOpenAI,
        model: str = "gpt-3.5-turbo",
    ):
        """
        初始化RAG服务.

        Args:
            retrieval_client: 检索服务客户端
            llm_client: LLM客户端
            model: 使用的模型
        """
        self.retrieval_client = retrieval_client
        self.query_rewriter = QueryRewriter(llm_client, model)
        self.context_builder = ContextBuilder(model)
        self.answer_generator = AnswerGenerator(llm_client, model)
        self.citation_generator = CitationGenerator()

    async def generate(
        self,
        query: str,
        tenant_id: str | None = None,
        rewrite_method: str = "multi",
        top_k: int = 10,
        stream: bool = False,
        include_citations: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        完整的RAG生成流程.

        Args:
            query: 用户查询
            tenant_id: 租户ID
            rewrite_method: 查询改写方法 (multi/hyde/none)
            top_k: 检索结果数量
            stream: 是否流式返回
            include_citations: 是否包含引用
            **kwargs: 其他参数

        Returns:
            生成结果字典:
            - answer: 答案文本
            - citations: 引用列表 (如果include_citations=True)
            - metadata: 元数据 (耗时、token使用等)
        """
        start_time = time.time()

        try:
            # 1. 查询改写
            rewrite_start = time.time()
            queries = await self.query_rewriter.rewrite_query(
                query, method=rewrite_method
            )
            rewrite_time = time.time() - rewrite_start

            logger.info(f"Query rewriting: {len(queries)} queries, {rewrite_time:.3f}s")

            # 2. 多查询检索
            retrieve_start = time.time()
            all_chunks = []

            for q in queries:
                chunks = await self.retrieval_client.retrieve(
                    query=q,
                    top_k=top_k,
                    tenant_id=tenant_id,
                    rerank=True,
                )
                all_chunks.extend(chunks)

            # 去重 (基于chunk_id)
            unique_chunks = self._deduplicate_chunks(all_chunks)
            retrieve_time = time.time() - retrieve_start

            logger.info(
                f"Retrieval: {len(queries)} queries -> {len(unique_chunks)} unique chunks, {retrieve_time:.3f}s"
            )

            if not unique_chunks:
                return {
                    "answer": "I couldn't find relevant information to answer your question.",
                    "citations": [],
                    "metadata": {
                        "total_time": time.time() - start_time,
                        "chunks_found": 0,
                    },
                }

            # 3. 构建上下文
            context = self.context_builder.build_context(unique_chunks)
            messages = self.context_builder.build_prompt(query, context)

            # 4. 生成答案
            if stream:
                # 流式生成 - 返回生成器
                return {
                    "stream": self.answer_generator.generate_stream(messages),
                    "chunks": unique_chunks,
                }
            else:
                # 非流式生成
                generate_start = time.time()
                result = await self.answer_generator.generate(messages)
                generate_time = time.time() - generate_start

                answer = result["answer"]

                # 5. 生成引用
                citations = []
                if include_citations:
                    citation_result = self.citation_generator.generate_response_with_citations(
                        answer, unique_chunks
                    )
                    answer = citation_result["answer"]
                    citations = citation_result["citations"]

                total_time = time.time() - start_time

                return {
                    "answer": answer,
                    "citations": citations,
                    "metadata": {
                        "total_time": total_time,
                        "rewrite_time": rewrite_time,
                        "retrieve_time": retrieve_time,
                        "generate_time": generate_time,
                        "chunks_found": len(unique_chunks),
                        "model": result["model"],
                        "usage": result.get("usage", {}),
                    },
                }

        except Exception as e:
            logger.error(f"RAG generation failed: {e}", exc_info=True)
            raise RuntimeError(f"RAG generation failed: {e}")

    async def generate_stream(
        self,
        query: str,
        tenant_id: str | None = None,
        rewrite_method: str = "none",  # 流式模式通常不做复杂改写
        top_k: int = 10,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        流式RAG生成.

        Args:
            query: 用户查询
            tenant_id: 租户ID
            rewrite_method: 查询改写方法
            top_k: 检索结果数量
            **kwargs: 其他参数

        Yields:
            流式事件:
            - type: "context" - 上下文就绪
            - type: "chunk" - 答案片段
            - type: "citations" - 引用列表
            - type: "done" - 完成
        """
        try:
            # 1. 查询改写
            queries = await self.query_rewriter.rewrite_query(
                query, method=rewrite_method
            )

            # 2. 检索
            all_chunks = []
            for q in queries:
                chunks = await self.retrieval_client.retrieve(
                    query=q, top_k=top_k, tenant_id=tenant_id, rerank=True
                )
                all_chunks.extend(chunks)

            unique_chunks = self._deduplicate_chunks(all_chunks)

            # 发送上下文就绪事件
            yield {"type": "context", "chunks_count": len(unique_chunks)}

            if not unique_chunks:
                yield {"type": "chunk", "content": "No relevant information found."}
                yield {"type": "done"}
                return

            # 3. 构建上下文
            context = self.context_builder.build_context(unique_chunks)
            messages = self.context_builder.build_prompt(query, context)

            # 4. 流式生成
            async for chunk in self.answer_generator.generate_stream(messages):
                yield {"type": "chunk", "content": chunk}

            # 5. 发送引用
            citations = self.citation_generator.generate_citations(
                unique_chunks, "", include_all=True
            )
            yield {"type": "citations", "citations": citations}

            # 6. 完成
            yield {"type": "done"}

        except Exception as e:
            logger.error(f"Streaming RAG failed: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    def _deduplicate_chunks(
        self, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        去重分块.

        基于chunk_id去重，保留分数最高的。

        Args:
            chunks: 分块列表

        Returns:
            去重后的分块列表
        """
        seen = {}

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                continue

            score = chunk.get("score", 0)

            if chunk_id not in seen or score > seen[chunk_id].get("score", 0):
                seen[chunk_id] = chunk

        # 按分数排序
        result = list(seen.values())
        result.sort(key=lambda x: x.get("score", 0), reverse=True)

        return result

    async def batch_generate(
        self,
        queries: list[str],
        tenant_id: str | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        批量生成答案.

        Args:
            queries: 查询列表
            tenant_id: 租户ID
            **kwargs: 其他参数

        Returns:
            答案列表
        """
        results = []

        for query in queries:
            try:
                result = await self.generate(query, tenant_id=tenant_id, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch item failed: {e}")
                results.append({"answer": None, "error": str(e)})

        return results

    async def close(self):
        """关闭服务."""
        await self.retrieval_client.close()
