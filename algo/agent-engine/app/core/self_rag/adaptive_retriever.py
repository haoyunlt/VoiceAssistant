"""
自适应检索策略模块

根据查询特征和上下文,动态选择最优的检索策略。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RetrievalStrategy(Enum):
    """检索策略"""

    DENSE = "dense"  # 密集向量检索（语义相似度）
    SPARSE = "sparse"  # 稀疏检索（关键词匹配，BM25）
    HYBRID = "hybrid"  # 混合检索（dense + sparse）
    CACHE = "cache"  # 缓存命中
    SKIP = "skip"  # 跳过检索（常识问题）


class QueryComplexity(Enum):
    """查询复杂度"""

    SIMPLE = "simple"  # 简单查询（事实性、单一概念）
    MODERATE = "moderate"  # 中等查询（需要理解和推理）
    COMPLEX = "complex"  # 复杂查询（多步推理、综合信息）


@dataclass
class RetrievalConfig:
    """检索配置"""

    strategy: RetrievalStrategy
    top_k: int
    rerank: bool
    reasoning: str


class AdaptiveRetriever:
    """
    自适应检索器

    根据查询特征动态选择检索策略和参数。

    用法:
        retriever = AdaptiveRetriever(knowledge_base, cache)

        # 自适应检索
        results = await retriever.retrieve(
            query="What is machine learning?",
            context={"conversation_history": [...]}
        )
    """

    def __init__(
        self,
        knowledge_base: Any,  # 知识库客户端
        cache: Any | None = None,  # 缓存客户端（Redis）
        llm_client: Any | None = None,  # 用于分析查询复杂度
        enable_cache: bool = True,
        cache_ttl: int = 3600,  # 1 hour
    ):
        """
        初始化自适应检索器

        Args:
            knowledge_base: 知识库客户端
            cache: 缓存客户端
            llm_client: LLM 客户端（用于高级分析）
            enable_cache: 是否启用缓存
            cache_ttl: 缓存 TTL（秒）
        """
        self.knowledge_base = knowledge_base
        self.cache = cache
        self.llm_client = llm_client
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl

        # 统计信息
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "strategy_usage": {
                "dense": 0,
                "sparse": 0,
                "hybrid": 0,
                "cache": 0,
                "skip": 0,
            },
        }

        logger.info(
            f"AdaptiveRetriever initialized (cache_enabled={enable_cache}, "
            f"cache_ttl={cache_ttl}s)"
        )

    async def retrieve(
        self, query: str, context: dict | None = None
    ) -> dict[str, Any]:
        """
        自适应检索

        Args:
            query: 查询文本
            context: 上下文信息（对话历史、用户偏好等）

        Returns:
            检索结果字典，包含:
            - documents: 检索到的文档列表
            - strategy: 使用的策略
            - config: 检索配置
            - from_cache: 是否来自缓存
        """
        self.stats["total_queries"] += 1

        # 1. 检查缓存
        if self.enable_cache and self.cache:
            cached_result = await self._check_cache(query)
            if cached_result:
                self.stats["cache_hits"] += 1
                self.stats["strategy_usage"]["cache"] += 1
                logger.info(f"Cache hit for query: {query[:50]}...")
                return {
                    "documents": cached_result,
                    "strategy": RetrievalStrategy.CACHE.value,
                    "config": RetrievalConfig(
                        strategy=RetrievalStrategy.CACHE,
                        top_k=len(cached_result),
                        rerank=False,
                        reasoning="Retrieved from cache",
                    ),
                    "from_cache": True,
                }
            else:
                self.stats["cache_misses"] += 1

        # 2. 决策：是否需要检索
        if self._is_common_knowledge(query):
            logger.info(f"Common knowledge query, skip retrieval: {query[:50]}...")
            self.stats["strategy_usage"]["skip"] += 1
            return {
                "documents": [],
                "strategy": RetrievalStrategy.SKIP.value,
                "config": RetrievalConfig(
                    strategy=RetrievalStrategy.SKIP,
                    top_k=0,
                    rerank=False,
                    reasoning="Common knowledge, no retrieval needed",
                ),
                "from_cache": False,
            }

        # 3. 分析查询复杂度
        complexity = self._analyze_query_complexity(query, context)

        # 4. 选择检索策略和参数
        config = self._select_strategy(query, complexity, context)

        # 5. 执行检索
        documents = await self._execute_retrieval(query, config)

        # 6. 缓存结果
        if self.enable_cache and self.cache and documents:
            await self._cache_result(query, documents)

        # 7. 更新统计
        self.stats["strategy_usage"][config.strategy.value] += 1

        logger.info(
            f"Retrieved {len(documents)} docs using {config.strategy.value} strategy"
        )

        return {
            "documents": documents,
            "strategy": config.strategy.value,
            "config": config,
            "from_cache": False,
        }

    def _analyze_query_complexity(
        self, query: str, context: dict | None
    ) -> QueryComplexity:
        """
        分析查询复杂度

        启发式规则:
        - 简单: 单个名词、事实性问题（What is X?, When did X happen?）
        - 中等: 需要理解和简单推理（How does X work?, Why X?）
        - 复杂: 多步推理、比较、综合（Compare X and Y, Explain the relationship...）
        """
        query_lower = query.lower()
        word_count = len(query.split())

        # 简单查询特征
        simple_patterns = ["what is", "who is", "when did", "where is", "define"]
        if any(pattern in query_lower for pattern in simple_patterns) and word_count <= 10:
            return QueryComplexity.SIMPLE

        # 复杂查询特征
        complex_patterns = [
            "compare",
            "contrast",
            "relationship",
            "analyze",
            "explain why",
            "how and why",
        ]
        if any(pattern in query_lower for pattern in complex_patterns) or word_count > 20:
            return QueryComplexity.COMPLEX

        # 默认中等复杂度
        return QueryComplexity.MODERATE

    def _select_strategy(
        self, query: str, complexity: QueryComplexity, context: dict | None
    ) -> RetrievalConfig:
        """
        选择检索策略和参数

        决策规则:
        - 简单查询: dense 向量检索, top_k=5, 不重排
        - 中等查询: hybrid 检索, top_k=10, 重排
        - 复杂查询: hybrid 检索, top_k=15, 重排
        """
        if complexity == QueryComplexity.SIMPLE:
            return RetrievalConfig(
                strategy=RetrievalStrategy.DENSE,
                top_k=5,
                rerank=False,
                reasoning="Simple query, use dense vector retrieval",
            )
        elif complexity == QueryComplexity.MODERATE:
            return RetrievalConfig(
                strategy=RetrievalStrategy.HYBRID,
                top_k=10,
                rerank=True,
                reasoning="Moderate query, use hybrid retrieval with reranking",
            )
        else:  # COMPLEX
            return RetrievalConfig(
                strategy=RetrievalStrategy.HYBRID,
                top_k=15,
                rerank=True,
                reasoning="Complex query, use hybrid retrieval with more candidates",
            )

    async def _execute_retrieval(
        self, query: str, config: RetrievalConfig
    ) -> list[str]:
        """执行检索"""
        try:
            if config.strategy == RetrievalStrategy.DENSE:
                # 密集向量检索
                results = await self.knowledge_base.search(
                    query=query, top_k=config.top_k, method="dense"
                )
            elif config.strategy == RetrievalStrategy.SPARSE:
                # 稀疏检索（BM25）
                results = await self.knowledge_base.search(
                    query=query, top_k=config.top_k, method="sparse"
                )
            elif config.strategy == RetrievalStrategy.HYBRID:
                # 混合检索
                dense_results = await self.knowledge_base.search(
                    query=query, top_k=config.top_k, method="dense"
                )
                sparse_results = await self.knowledge_base.search(
                    query=query, top_k=config.top_k, method="sparse"
                )
                # 合并结果（简单去重）
                results = self._merge_results(dense_results, sparse_results, config.top_k)
            else:
                results = []

            # 重排（如果需要）
            if config.rerank and results:
                results = await self._rerank(query, results)

            return results

        except Exception as e:
            logger.error(f"Error in retrieval execution: {e}")
            return []

    def _merge_results(
        self, dense_results: list[str], sparse_results: list[str], top_k: int
    ) -> list[str]:
        """合并 dense 和 sparse 检索结果"""
        # 简单策略: 交替取结果
        merged = []
        max_len = max(len(dense_results), len(sparse_results))

        for i in range(max_len):
            if i < len(dense_results) and dense_results[i] not in merged:
                merged.append(dense_results[i])
            if i < len(sparse_results) and sparse_results[i] not in merged:
                merged.append(sparse_results[i])
            if len(merged) >= top_k:
                break

        return merged[:top_k]

    async def _rerank(self, query: str, documents: list[str]) -> list[str]:
        """重排序检索结果"""
        # 简单实现: 按文档与查询的相似度重排
        # 实际项目中可以使用专门的 reranker 模型
        scored_docs = []

        for doc in documents:
            score = self._compute_relevance_score(query, doc)
            scored_docs.append((score, doc))

        # 按分数降序排序
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        return [doc for _, doc in scored_docs]

    def _compute_relevance_score(self, query: str, document: str) -> float:
        """计算相关性分数（简化版）"""
        query_terms = set(query.lower().split())
        doc_terms = set(document.lower().split())

        # Jaccard 相似度
        intersection = query_terms & doc_terms
        union = query_terms | doc_terms

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _is_common_knowledge(self, query: str) -> bool:
        """判断是否为常识问题（不需要检索）"""
        # 简单启发式规则
        common_patterns = [
            "what is 1+1",
            "what is 2+2",
            "what day is today",
            "what time is it",
        ]

        query_lower = query.lower()
        return any(pattern in query_lower for pattern in common_patterns)

    async def _check_cache(self, query: str) -> list[str] | None:
        """检查缓存"""
        if not self.cache:
            return None

        try:
            cache_key = f"retrieval:{hash(query)}"
            cached = await self.cache.get(cache_key)
            return cached if cached else None
        except Exception as e:
            logger.error(f"Error checking cache: {e}")
            return None

    async def _cache_result(self, query: str, documents: list[str]):
        """缓存检索结果"""
        if not self.cache:
            return

        try:
            cache_key = f"retrieval:{hash(query)}"
            await self.cache.set(cache_key, documents, ex=self.cache_ttl)
        except Exception as e:
            logger.error(f"Error caching result: {e}")

    def get_stats(self) -> dict:
        """获取统计信息"""
        cache_hit_rate = (
            self.stats["cache_hits"] / self.stats["total_queries"]
            if self.stats["total_queries"] > 0
            else 0.0
        )

        return {
            **self.stats,
            "cache_hit_rate": cache_hit_rate,
        }
