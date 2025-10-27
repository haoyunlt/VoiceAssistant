"""
RAG Engine Core - 检索增强生成核心引擎
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from app.core.context_builder import ContextBuilder
from app.core.prompt_generator import PromptGenerator
from app.core.query_rewriter import QueryRewriter
from app.infrastructure.retrieval_client import RetrievalClient

# 使用统一LLM客户端
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

from llm_client import UnifiedLLMClient

logger = logging.getLogger(__name__)


class RAGEngine:
    """RAG 引擎"""

    def __init__(self):
        """初始化 RAG 引擎"""
        # 核心组件
        self.query_rewriter = None
        self.retrieval_client = None
        self.context_builder = None
        self.prompt_generator = None
        self.llm_client = None

        # 统计信息
        self.stats = {
            "total_queries": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "total_tokens_used": 0,
            "avg_generation_time": 0,
            "total_generation_time": 0,
        }

        logger.info("RAG Engine created")

    async def initialize(self):
        """初始化所有组件"""
        logger.info("Initializing RAG Engine components...")

        # 初始化查询改写器
        self.query_rewriter = QueryRewriter()
        await self.query_rewriter.initialize()

        # 初始化检索客户端
        self.retrieval_client = RetrievalClient()
        await self.retrieval_client.initialize()

        # 初始化上下文构建器
        self.context_builder = ContextBuilder()

        # 初始化 Prompt 生成器
        self.prompt_generator = PromptGenerator()

        # 初始化统一LLM客户端
        self.llm_client = UnifiedLLMClient()

        logger.info("RAG Engine initialized successfully")

    async def generate(
        self,
        query: str,
        conversation_id: str = None,
        tenant_id: str = None,
        mode: str = "simple",
        top_k: int = 5,
        temperature: float = 0.7,
        include_sources: bool = True,
    ) -> Dict:
        """
        生成答案（非流式）

        Args:
            query: 用户查询
            conversation_id: 会话 ID
            tenant_id: 租户 ID
            mode: 模式 (simple/advanced/precise)
            top_k: 检索结果数
            temperature: 生成温度
            include_sources: 是否包含来源

        Returns:
            生成结果字典
        """
        start_time = time.time()
        self.stats["total_queries"] += 1

        try:
            # 1. 查询改写
            logger.info(f"Original query: {query}")
            rewritten_query = await self._rewrite_query(query, conversation_id)
            logger.info(f"Rewritten query: {rewritten_query}")

            # 2. 检索相关文档
            retrieved_docs = await self._retrieve_documents(
                rewritten_query, tenant_id, top_k, mode
            )
            logger.info(f"Retrieved {len(retrieved_docs)} documents")

            # 3. 构建上下文
            context = await self._build_context(retrieved_docs, query)
            logger.info(f"Built context: {len(context)} chars")

            # 4. 生成 Prompt
            prompt = await self._generate_prompt(query, context, mode)

            # 5. 调用 LLM 生成答案
            answer = await self.llm_client.generate(
                prompt=prompt,
                temperature=temperature,
                max_tokens=2000,
            )

            # 6. 后处理：提取引用来源
            if include_sources:
                sources = self._extract_sources(retrieved_docs)
            else:
                sources = []

            # 更新统计
            generation_time = time.time() - start_time
            self.stats["successful_generations"] += 1
            self.stats["total_generation_time"] += generation_time
            self.stats["avg_generation_time"] = (
                self.stats["total_generation_time"] / self.stats["successful_generations"]
            )

            logger.info(f"Generation completed in {generation_time:.2f}s")

            return {
                "answer": answer,
                "sources": sources,
                "query": query,
                "rewritten_query": rewritten_query,
                "retrieved_count": len(retrieved_docs),
                "generation_time": generation_time,
                "mode": mode,
            }

        except Exception as e:
            self.stats["failed_generations"] += 1
            logger.error(f"Error generating answer: {e}", exc_info=True)
            raise

    async def generate_stream(
        self,
        query: str,
        conversation_id: str = None,
        tenant_id: str = None,
        mode: str = "simple",
        top_k: int = 5,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        生成答案（流式）

        Args:
            query: 用户查询
            conversation_id: 会话 ID
            tenant_id: 租户 ID
            mode: 模式
            top_k: 检索结果数
            temperature: 生成温度

        Yields:
            JSON 格式的流式数据块
        """
        start_time = time.time()
        self.stats["total_queries"] += 1

        try:
            # 1. 查询改写
            rewritten_query = await self._rewrite_query(query, conversation_id)

            # 发送改写结果
            yield json.dumps({
                "type": "rewritten_query",
                "content": rewritten_query,
            })

            # 2. 检索相关文档
            retrieved_docs = await self._retrieve_documents(
                rewritten_query, tenant_id, top_k, mode
            )

            # 发送检索结果数量
            yield json.dumps({
                "type": "retrieved_count",
                "content": len(retrieved_docs),
            })

            # 3. 构建上下文
            context = await self._build_context(retrieved_docs, query)

            # 4. 生成 Prompt
            prompt = await self._generate_prompt(query, context, mode)

            # 5. 流式生成答案
            async for chunk in self.llm_client.generate_stream(
                prompt=prompt,
                temperature=temperature,
                max_tokens=2000,
            ):
                yield json.dumps({
                    "type": "answer_chunk",
                    "content": chunk,
                })

            # 6. 发送来源信息
            sources = self._extract_sources(retrieved_docs)
            yield json.dumps({
                "type": "sources",
                "content": sources,
            })

            # 发送完成信号
            generation_time = time.time() - start_time
            yield json.dumps({
                "type": "done",
                "generation_time": generation_time,
            })

            self.stats["successful_generations"] += 1

        except Exception as e:
            self.stats["failed_generations"] += 1
            logger.error(f"Error in streaming generation: {e}", exc_info=True)

            yield json.dumps({
                "type": "error",
                "content": str(e),
            })

    async def _rewrite_query(self, query: str, conversation_id: str = None) -> str:
        """查询改写"""
        # 获取对话历史（如果有）
        conversation_history = []
        if conversation_id:
            # TODO: 从 Conversation Service 获取历史
            pass

        # 执行查询改写
        rewritten = await self.query_rewriter.rewrite(query, conversation_history)

        return rewritten

    async def _retrieve_documents(
        self, query: str, tenant_id: str, top_k: int, mode: str
    ) -> List[Dict]:
        """检索相关文档"""
        # 根据模式选择检索策略
        retrieval_mode = self._get_retrieval_mode(mode)

        # 调用检索服务
        results = await self.retrieval_client.retrieve(
            query=query,
            top_k=top_k,
            mode=retrieval_mode,
            tenant_id=tenant_id,
            rerank=True,
        )

        return results

    def _get_retrieval_mode(self, rag_mode: str) -> str:
        """根据 RAG 模式映射检索模式"""
        mapping = {
            "simple": "vector",
            "advanced": "hybrid",
            "precise": "hybrid",
        }
        return mapping.get(rag_mode, "vector")

    async def _build_context(self, documents: List[Dict], query: str) -> str:
        """构建上下文"""
        context = await self.context_builder.build(documents, query)
        return context

    async def _generate_prompt(self, query: str, context: str, mode: str) -> str:
        """生成 Prompt"""
        prompt = await self.prompt_generator.generate(
            query=query,
            context=context,
            mode=mode,
        )
        return prompt

    def _extract_sources(self, documents: List[Dict]) -> List[Dict]:
        """提取引用来源"""
        sources = []
        for doc in documents:
            sources.append({
                "document_id": doc.get("document_id"),
                "chunk_id": doc.get("chunk_id"),
                "content": doc.get("content", "")[:200],  # 截取前 200 字符
                "score": doc.get("rerank_score") or doc.get("score"),
            })
        return sources

    async def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_generations"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0
                else 0
            ),
        }

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up RAG Engine...")

        if self.retrieval_client:
            await self.retrieval_client.cleanup()

        if self.llm_client:
            await self.llm_client.cleanup()

        logger.info("RAG Engine cleanup complete")
