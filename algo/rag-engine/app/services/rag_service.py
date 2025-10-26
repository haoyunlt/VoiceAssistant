"""RAG服务 - 完整的RAG流程编排"""
import json
import logging
import time
from typing import AsyncIterator, Dict, List

from app.core.config import settings
from app.models.rag import RAGRequest, RAGResponse, RetrievedDocument
from app.services.context_service import ContextService
from app.services.generator_service import GeneratorService
from app.services.query_service import QueryService
from app.services.retrieval_client import RetrievalClient

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务"""

    def __init__(self):
        self.query_service = QueryService()
        self.retrieval_client = RetrievalClient()
        self.context_service = ContextService()
        self.generator_service = GeneratorService()

    async def generate(self, request: RAGRequest) -> RAGResponse:
        """
        完整RAG流程

        Args:
            request: RAG请求

        Returns:
            RAG响应
        """
        start_time = time.time()

        try:
            logger.info(f"Starting RAG for query: {request.query[:100]}")

            # 1. 查询理解和扩展（可选）
            if settings.ENABLE_QUERY_EXPANSION:
                expanded_result = await self.query_service.expand_query(request.query)
                queries = [request.query] + expanded_result.expanded_queries[:2]
                logger.info(f"Query expanded to {len(queries)} variants")
            else:
                queries = [request.query]

            # 2. 检索相关文档
            documents = await self.retrieval_client.retrieve(
                queries=queries,
                knowledge_base_id=request.knowledge_base_id,
                tenant_id=request.tenant_id,
                top_k=request.top_k * 2 if request.enable_rerank else request.top_k,
            )
            logger.info(f"Retrieved {len(documents)} documents")

            # 3. 重排序（可选）
            if request.enable_rerank and settings.ENABLE_RERANK:
                documents = await self._rerank_documents(
                    query=request.query,
                    documents=documents,
                    top_k=request.top_k,
                )
                logger.info(f"Reranked to top {len(documents)} documents")

            # 4. 组装上下文
            context = await self.context_service.build_context(
                documents=documents,
                max_length=settings.MAX_CONTEXT_LENGTH,
            )
            logger.info(f"Built context with {len(context)} characters")

            # 5. 生成答案
            answer = await self.generator_service.generate(
                query=request.query,
                context=context,
                history=request.history,
                model=request.model or settings.DEFAULT_LLM_MODEL,
                temperature=request.temperature,
            )
            logger.info("Answer generated")

            # 6. 提取引用
            sources = documents[: request.top_k]

            processing_time = time.time() - start_time

            return RAGResponse(
                query=request.query,
                answer=answer,
                sources=sources,
                metadata={
                    "retrieved_count": len(documents),
                    "context_length": len(context),
                    "model": request.model or settings.DEFAULT_LLM_MODEL,
                },
                processing_time=processing_time,
            )

        except Exception as e:
            logger.error(f"RAG failed: {e}", exc_info=True)
            raise

    async def generate_stream(self, request: RAGRequest) -> AsyncIterator[str]:
        """
        流式RAG

        Args:
            request: RAG请求

        Yields:
            SSE格式的流式数据
        """
        try:
            # 1. 检索阶段（非流式）
            documents = await self.retrieve(request)

            # 发送检索结果
            yield f"data: {json.dumps({'type': 'sources', 'data': [d.dict() for d in documents[:request.top_k]]})}\n\n"

            # 2. 组装上下文
            context = await self.context_service.build_context(
                documents=documents,
                max_length=settings.MAX_CONTEXT_LENGTH,
            )

            # 3. 流式生成
            async for chunk in self.generator_service.generate_stream(
                query=request.query,
                context=context,
                history=request.history,
                model=request.model or settings.DEFAULT_LLM_MODEL,
                temperature=request.temperature,
            ):
                yield chunk

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream RAG failed: {e}", exc_info=True)
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    async def retrieve(self, request: RAGRequest) -> List[RetrievedDocument]:
        """
        仅检索（不生成）

        Args:
            request: RAG请求

        Returns:
            检索到的文档列表
        """
        try:
            # 1. 查询扩展（可选）
            if settings.ENABLE_QUERY_EXPANSION:
                expanded_result = await self.query_service.expand_query(request.query)
                queries = [request.query] + expanded_result.expanded_queries[:2]
            else:
                queries = [request.query]

            # 2. 检索
            documents = await self.retrieval_client.retrieve(
                queries=queries,
                knowledge_base_id=request.knowledge_base_id,
                tenant_id=request.tenant_id,
                top_k=request.top_k * 2 if request.enable_rerank else request.top_k,
            )

            # 3. 重排序（可选）
            if request.enable_rerank and settings.ENABLE_RERANK:
                documents = await self._rerank_documents(
                    query=request.query,
                    documents=documents,
                    top_k=request.top_k,
                )

            return documents

        except Exception as e:
            logger.error(f"Retrieval failed: {e}", exc_info=True)
            raise

    async def _rerank_documents(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_k: int,
    ) -> List[RetrievedDocument]:
        """
        重排序文档

        Args:
            query: 查询
            documents: 文档列表
            top_k: 返回top-k

        Returns:
            重排序后的文档
        """
        # 实际应该使用Cross-Encoder或LLM Rerank
        # 这里简化实现：保持原有顺序，只截取top-k
        logger.info(f"Reranking {len(documents)} documents to top {top_k}")
        return documents[:top_k]
