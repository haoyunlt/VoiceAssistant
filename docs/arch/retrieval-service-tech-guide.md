# Retrieval Service 技术实现指南

> **目标**: 为优化迭代提供技术参考，代码示例，配置模板
>
> **原则**: 代码优先，文档最小化，保持同步

---

## 架构演进

### 当前架构 (Baseline)

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                             │
│              (Auth, RateLimit, Idempotency)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────▼──────────────┐
           │  Retrieval Orchestrator  │
           │   (retrieval_service)    │
           └─────┬──────┬──────┬──────┘
                 │      │      │
        ┌────────▼┐  ┌─▼───┐ ┌▼──────────┐
        │ Vector  │  │BM25 │ │  Graph    │
        │ Service │  │Svc  │ │  Service  │
        └────┬────┘  └──┬──┘ └─────┬─────┘
             │          │          │
        ┌────▼──────────▼──────────▼─────┐
        │   RRF Fusion (hybrid_service)  │
        └────────────┬────────────────────┘
                     │
              ┌──────▼────────┐
              │  Rerank Svc   │
              │ (Cross-Enc)   │
              └───────────────┘
```

### 目标架构 (After Phase 4)

```
┌────────────────────────────────────────────────────────────────┐
│                  API Gateway (Enhanced)                         │
│      Auth | RateLimit (Strategy-based) | Cost Tracking         │
└──────────────────────┬─────────────────────────────────────────┘
                       │
         ┌─────────────▼───────────────┐
         │  Intent Classifier          │  ← NEW
         │  (Query Complexity)         │
         └─────────────┬───────────────┘
                       │
         ┌─────────────▼───────────────┐
         │ Adaptive Retrieval Router   │  ← NEW
         │  (Dynamic Strategy Selection)│
         └──┬──────────┬────────────┬───┘
            │          │            │
    ┌───────▼─┐   ┌───▼────┐   ┌──▼─────────┐
    │ Simple  │   │Medium  │   │  Complex   │
    │ Path    │   │Path    │   │  Path      │
    │(Vector) │   │(Hybrid)│   │(Agent)     │
    └───┬─────┘   └───┬────┘   └──┬─────────┘
        │             │            │
        │     ┌───────▼────────┐   │
        │     │  Query Rewriter│◄──┤  ← ENHANCED
        │     │  Multi-Query   │   │
        │     │  HyDE          │   │
        │     └───────┬────────┘   │
        │             │            │
        │   ┌─────────▼──────────┐ │
        │   │ Parallel Retrieval │ │
        │   │ Vector|BM25|Graph  │ │  ← 3-way
        │   └─────────┬──────────┘ │
        │             │            │
        │   ┌─────────▼──────────┐ │
        │   │ Dynamic Fusion     │ │  ← NEW (Learnable)
        │   │  (Adaptive Weights)│ │
        │   └─────────┬──────────┘ │
        │             │            │
        │   ┌─────────▼──────────┐ │
        │   │ Multi-stage Rerank │ │  ← NEW (2-stage)
        │   │  Stage 1: Fast     │ │
        │   │  Stage 2: Precise  │ │
        │   └─────────┬──────────┘ │
        │             │            │
        │   ┌─────────▼──────────┐ │
        │   │ Compression        │ │  ← NEW
        │   │ (Context Pruning)  │ │
        │   └─────────┬──────────┘ │
        │             │            │
        └─────────────┼────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Semantic Cache (L1+L2)   │  ← ENHANCED
        │   + Cache Warming          │
        └────────────────────────────┘
```

---

## 核心技术实现

### 1. Query Expansion & Rewriting

**技术选型**:
- **同义词扩展**: WordNet, PPDB, 自建词典
- **拼写纠错**: SymSpell, BK-Tree
- **LLM改写**: 轻量级模型 (Qwen-7B, Llama-8B)

**实现示例**:

```python
# app/services/query_expansion_service.py

from typing import List, Dict, Optional
import httpx
from dataclasses import dataclass

@dataclass
class ExpandedQuery:
    original: str
    expanded: List[str]
    weights: List[float]
    method: str  # synonym, llm, spelling

class QueryExpansionService:
    """查询扩展服务"""

    def __init__(
        self,
        methods: List[str] = ["synonym", "spelling"],
        llm_endpoint: Optional[str] = None,
    ):
        self.methods = methods
        self.llm_endpoint = llm_endpoint
        self.synonym_dict = self._load_synonyms()

    async def expand(
        self,
        query: str,
        max_expansions: int = 3
    ) -> ExpandedQuery:
        """
        扩展查询

        Args:
            query: 原始查询
            max_expansions: 最大扩展数量

        Returns:
            扩展后的查询对象
        """
        expanded = [query]  # 包含原查询
        weights = [1.0]

        # 1. 拼写纠错
        if "spelling" in self.methods:
            corrected = await self._correct_spelling(query)
            if corrected != query:
                expanded.append(corrected)
                weights.append(0.9)

        # 2. 同义词扩展
        if "synonym" in self.methods:
            synonyms = await self._expand_synonyms(query)
            expanded.extend(synonyms[:max_expansions-len(expanded)])
            weights.extend([0.8] * len(synonyms))

        # 3. LLM改写 (可选，成本高)
        if "llm" in self.methods and self.llm_endpoint:
            rewrites = await self._llm_rewrite(query)
            expanded.extend(rewrites[:max_expansions-len(expanded)])
            weights.extend([0.7] * len(rewrites))

        return ExpandedQuery(
            original=query,
            expanded=expanded[:max_expansions],
            weights=weights[:max_expansions],
            method="+".join(self.methods)
        )

    async def _correct_spelling(self, query: str) -> str:
        """拼写纠错 (示例: 使用SymSpell或自定义逻辑)"""
        # TODO: 集成SymSpell或其他拼写纠错库
        return query

    async def _expand_synonyms(self, query: str) -> List[str]:
        """同义词扩展"""
        # 简单示例: 基于词典的替换
        words = query.split()
        expansions = []

        for i, word in enumerate(words):
            if word in self.synonym_dict:
                synonyms = self.synonym_dict[word]
                for syn in synonyms[:2]:  # 每个词最多2个同义词
                    new_words = words.copy()
                    new_words[i] = syn
                    expansions.append(" ".join(new_words))

        return expansions

    async def _llm_rewrite(self, query: str) -> List[str]:
        """LLM改写查询"""
        prompt = f"""Rewrite the following query in 2 different ways while keeping the original meaning:

Query: {query}

Rewrites (one per line):
1."""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.llm_endpoint}/api/v1/chat/completions",
                json={
                    "model": "qwen-7b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 100,
                },
                timeout=3.0,
            )
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 解析结果
            rewrites = [line.split(".", 1)[1].strip()
                       for line in content.split("\n")
                       if line.strip() and line[0].isdigit()]

            return rewrites

    def _load_synonyms(self) -> Dict[str, List[str]]:
        """加载同义词词典"""
        # TODO: 从文件或数据库加载
        return {
            "购买": ["买", "下单", "采购"],
            "问题": ["疑问", "困惑", "难题"],
            "如何": ["怎么", "怎样", "如何才能"],
        }
```

**配置示例** (`configs/retrieval.yaml`):

```yaml
query_expansion:
  enabled: true
  methods:
    - synonym
    - spelling
    # - llm  # 可选，成本高
  max_expansions: 3
  llm_endpoint: "http://model-adapter:8000"
  llm_model: "qwen-7b"
  llm_timeout_ms: 3000
  synonym_dict_path: "data/synonyms.json"
```

---

### 2. HyDE (Hypothetical Document Embeddings)

**原理**: 用LLM生成"假设性答案文档"，用答案的embedding检索，而非query的embedding

**优势**:
- 提升知识密集型查询的召回
- 缩小query-doc的语义gap

**实现示例**:

```python
# app/services/hyde_service.py

from typing import List
import httpx

class HyDEService:
    """HyDE检索服务"""

    def __init__(
        self,
        llm_endpoint: str,
        embedding_service,
        vector_service,
        llm_model: str = "qwen-7b",
    ):
        self.llm_endpoint = llm_endpoint
        self.embedding_service = embedding_service
        self.vector_service = vector_service
        self.llm_model = llm_model

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        num_hypotheses: int = 3,
        fusion_method: str = "avg",
    ) -> List[Dict]:
        """
        HyDE检索

        Args:
            query: 用户查询
            top_k: 返回数量
            num_hypotheses: 生成假设答案数量
            fusion_method: 融合方法 (avg, max, concat)

        Returns:
            检索结果列表
        """
        # 1. 生成假设答案文档
        hypotheses = await self._generate_hypotheses(
            query, num=num_hypotheses
        )

        # 2. 对每个假设答案embedding
        embeddings = []
        for hyp in hypotheses:
            emb = await self.embedding_service.embed_query(hyp)
            embeddings.append(emb)

        # 3. 融合embeddings (平均/最大/拼接)
        if fusion_method == "avg":
            fused_emb = self._average_embeddings(embeddings)
        elif fusion_method == "max":
            fused_emb = self._max_embeddings(embeddings)
        elif fusion_method == "concat":
            fused_emb = self._concat_embeddings(embeddings)
        else:
            fused_emb = embeddings[0]

        # 4. 用融合的embedding检索
        results = await self.vector_service.search(
            query_embedding=fused_emb,
            top_k=top_k,
        )

        return results

    async def _generate_hypotheses(
        self,
        query: str,
        num: int = 3
    ) -> List[str]:
        """生成假设答案文档"""
        prompt = f"""Given the question, write a detailed answer (2-3 sentences).

Question: {query}

Answer:"""

        hypotheses = []
        async with httpx.AsyncClient() as client:
            for _ in range(num):
                response = await client.post(
                    f"{self.llm_endpoint}/api/v1/chat/completions",
                    json={
                        "model": self.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,  # 多样性
                        "max_tokens": 150,
                    },
                    timeout=5.0,
                )
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                hypotheses.append(answer.strip())

        return hypotheses

    def _average_embeddings(self, embeddings: List[List[float]]) -> List[float]:
        """平均融合"""
        import numpy as np
        return np.mean(embeddings, axis=0).tolist()

    def _max_embeddings(self, embeddings: List[List[float]]) -> List[float]:
        """最大值融合"""
        import numpy as np
        return np.max(embeddings, axis=0).tolist()

    def _concat_embeddings(self, embeddings: List[List[float]]) -> List[float]:
        """拼接融合 (需要模型支持更长的向量)"""
        import numpy as np
        return np.concatenate(embeddings).tolist()
```

**使用场景**:
- 知识密集型问答 (医疗、法律、技术文档)
- 用户query短而模糊，但期望详细答案
- 避免使用在: 导航型查询、已知答案查询

---

### 3. Multi-stage Reranking

**架构**:

```
候选文档 (top 100)
    │
    ├─► Stage 1: Fast Rerank (轻量级模型)
    │        Model: bge-reranker-base (100ms)
    │        Output: top 20
    │
    └─► Stage 2: Precise Rerank (重模型/LLM)
             Model: bge-reranker-large or LLM (500ms)
             Output: top 10
```

**成本对比**:

| 方案 | 模型 | 延迟 | 成本/query |
|------|------|------|------------|
| 单阶段重LLM | GPT-4 | 2000ms | $0.05 |
| 单阶段轻模型 | bge-base | 150ms | $0.001 |
| **两阶段** | base→large | 300ms | $0.005 |

**实现示例**:

```python
# app/services/multi_stage_rerank_service.py

from typing import List
from sentence_transformers import CrossEncoder
import httpx

class MultiStageRerankService:
    """两阶段重排服务"""

    def __init__(
        self,
        stage1_model: str = "BAAI/bge-reranker-base",
        stage2_model: str = "BAAI/bge-reranker-large",
        stage1_top_k: int = 20,
        use_llm_stage2: bool = False,
        llm_endpoint: str = None,
    ):
        self.stage1_encoder = CrossEncoder(stage1_model, max_length=512)

        if use_llm_stage2:
            self.stage2_encoder = None
            self.llm_endpoint = llm_endpoint
        else:
            self.stage2_encoder = CrossEncoder(stage2_model, max_length=512)

        self.stage1_top_k = stage1_top_k
        self.use_llm_stage2 = use_llm_stage2

    async def rerank(
        self,
        query: str,
        documents: List[Dict],
        final_top_k: int = 10,
    ) -> List[Dict]:
        """
        两阶段重排

        Args:
            query: 查询
            documents: 候选文档
            final_top_k: 最终返回数量

        Returns:
            重排后的文档
        """
        if len(documents) <= final_top_k:
            # 文档少，直接用Stage 2
            return await self._stage2_rerank(query, documents, final_top_k)

        # Stage 1: Fast rerank (筛选到top 20)
        stage1_results = await self._stage1_rerank(
            query, documents, self.stage1_top_k
        )

        # Stage 2: Precise rerank (精排到top 10)
        stage2_results = await self._stage2_rerank(
            query, stage1_results, final_top_k
        )

        return stage2_results

    async def _stage1_rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """Stage 1: 轻量级快速重排"""
        import asyncio

        pairs = [[query, doc["content"]] for doc in documents]

        # 在线程池中运行 (避免阻塞)
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None, self.stage1_encoder.predict, pairs
        )

        # 排序
        for doc, score in zip(documents, scores):
            doc["rerank_score_stage1"] = float(score)

        sorted_docs = sorted(
            documents,
            key=lambda x: x["rerank_score_stage1"],
            reverse=True
        )

        return sorted_docs[:top_k]

    async def _stage2_rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """Stage 2: 精确重排"""
        if self.use_llm_stage2:
            return await self._llm_rerank(query, documents, top_k)
        else:
            return await self._model_rerank(query, documents, top_k)

    async def _model_rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """使用重模型重排"""
        import asyncio

        pairs = [[query, doc["content"]] for doc in documents]

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None, self.stage2_encoder.predict, pairs
        )

        for doc, score in zip(documents, scores):
            doc["rerank_score_stage2"] = float(score)
            doc["score"] = float(score)  # 更新最终分数

        sorted_docs = sorted(
            documents,
            key=lambda x: x["score"],
            reverse=True
        )

        return sorted_docs[:top_k]

    async def _llm_rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """使用LLM重排"""
        # 构建prompt
        docs_text = "\n\n".join([
            f"[{i}] {doc['content'][:300]}..."
            for i, doc in enumerate(documents)
        ])

        prompt = f"""Rank the following documents by relevance to the query. Return comma-separated indices in descending order.

Query: {query}

Documents:
{docs_text}

Ranking:"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.llm_endpoint}/api/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 50,
                },
                timeout=10.0,
            )
            result = response.json()
            content = result["choices"][0]["message"]["content"]

        # 解析排序结果
        try:
            indices = [int(idx.strip()) for idx in content.split(",")]
            reranked = [documents[i] for i in indices if i < len(documents)]

            # 添加剩余文档
            ranked_set = set(indices)
            for i, doc in enumerate(documents):
                if i not in ranked_set:
                    reranked.append(doc)

            return reranked[:top_k]
        except:
            # 解析失败，返回原顺序
            return documents[:top_k]
```

---

### 4. Semantic Cache (L1 + L2)

**架构**:

```
Request
  │
  ├─► L1 Cache (Exact Match)
  │     Key: hash(query + filters)
  │     TTL: 1 hour
  │     Hit: 返回结果 (< 5ms)
  │
  └─► L2 Cache (Semantic Match)
        Key: embedding_hash
        Match: cosine_similarity > 0.95
        TTL: 6 hours
        Hit: 返回结果 (< 20ms)
        Miss: 执行检索 → 写入L1+L2
```

**实现示例**:

```python
# app/infrastructure/semantic_cache.py

from typing import Optional, List, Dict
import hashlib
import json
import redis
import numpy as np

class SemanticCache:
    """两级语义缓存"""

    def __init__(
        self,
        redis_client: redis.Redis,
        embedding_service,
        l1_ttl: int = 3600,       # 1 hour
        l2_ttl: int = 21600,      # 6 hours
        similarity_threshold: float = 0.95,
    ):
        self.redis = redis_client
        self.embedding_service = embedding_service
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        self.similarity_threshold = similarity_threshold

    async def get(
        self,
        query: str,
        filters: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        从缓存获取结果

        Returns:
            缓存的结果，或None (miss)
        """
        # L1: Exact match
        l1_key = self._l1_key(query, filters)
        l1_result = self.redis.get(l1_key)
        if l1_result:
            return json.loads(l1_result)

        # L2: Semantic match
        query_emb = await self.embedding_service.embed_query(query)
        l2_result = await self._l2_get(query_emb, filters)

        if l2_result:
            # L2命中，同时写入L1 (下次更快)
            await self.set(query, filters, l2_result)

        return l2_result

    async def set(
        self,
        query: str,
        filters: Optional[Dict],
        result: Dict,
    ):
        """写入缓存 (L1 + L2)"""
        # L1: Exact
        l1_key = self._l1_key(query, filters)
        self.redis.setex(
            l1_key,
            self.l1_ttl,
            json.dumps(result)
        )

        # L2: Semantic
        query_emb = await self.embedding_service.embed_query(query)
        await self._l2_set(query_emb, filters, result)

    def _l1_key(self, query: str, filters: Optional[Dict]) -> str:
        """L1缓存键 (精确匹配)"""
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        key_str = f"{query}|{filter_str}"
        return f"cache:l1:{hashlib.md5(key_str.encode()).hexdigest()}"

    async def _l2_get(
        self,
        query_emb: List[float],
        filters: Optional[Dict],
    ) -> Optional[Dict]:
        """L2缓存获取 (语义匹配)"""
        # 存储结构: sorted set
        # score: embedding hash (用于过滤)
        # member: json({"query_emb": [...], "result": {...}})

        filter_key = self._l2_filter_key(filters)
        cached_items = self.redis.zrange(filter_key, 0, -1)

        # 遍历缓存项，计算相似度
        for item_json in cached_items:
            item = json.loads(item_json)
            cached_emb = item["query_emb"]
            similarity = self._cosine_similarity(query_emb, cached_emb)

            if similarity >= self.similarity_threshold:
                return item["result"]

        return None

    async def _l2_set(
        self,
        query_emb: List[float],
        filters: Optional[Dict],
        result: Dict,
    ):
        """L2缓存写入"""
        filter_key = self._l2_filter_key(filters)

        cache_item = {
            "query_emb": query_emb,
            "result": result,
        }

        # 写入sorted set (score为timestamp，用于淘汰)
        import time
        score = time.time()

        self.redis.zadd(
            filter_key,
            {json.dumps(cache_item): score}
        )

        # 设置过期
        self.redis.expire(filter_key, self.l2_ttl)

        # 限制缓存大小 (保留最新1000条)
        self.redis.zremrangebyrank(filter_key, 0, -1001)

    def _l2_filter_key(self, filters: Optional[Dict]) -> str:
        """L2缓存键 (按filter分组)"""
        filter_str = json.dumps(filters, sort_keys=True) if filters else "default"
        return f"cache:l2:{hashlib.md5(filter_str.encode()).hexdigest()}"

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """余弦相似度"""
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

**预热策略** (`app/services/cache_warming_service.py`):

```python
class CacheWarmingService:
    """缓存预热服务"""

    def __init__(self, semantic_cache, retrieval_service):
        self.cache = semantic_cache
        self.retrieval = retrieval_service

    async def warm_top_queries(self, queries: List[str]):
        """预热高频查询"""
        for query in queries:
            # 执行检索
            result = await self.retrieval.hybrid_search(
                HybridRequest(query=query, top_k=10)
            )

            # 写入缓存
            await self.cache.set(query, None, result.dict())

    async def warm_from_analytics(self, days: int = 7, top_n: int = 1000):
        """从分析数据预热"""
        # TODO: 从analytics-service获取高频query
        # top_queries = await analytics_client.get_top_queries(days, top_n)
        # await self.warm_top_queries(top_queries)
        pass
```

---

### 5. Adaptive Retrieval Strategy

**策略映射表**:

| Query Complexity | 特征 | 策略 | 延迟目标 | 成本 |
|------------------|------|------|----------|------|
| **Simple** | 长度<10词, 无实体, 单意图 | Vector only | <150ms | $0.001 |
| **Medium** | 长度10-30词, 1-2实体 | Hybrid (V+B+RRF) | <300ms | $0.005 |
| **Complex** | 长度>30词, 多实体, 多意图 | Agent + Multi-query + Rerank | <2s | $0.02 |

**实现示例**:

```python
# app/services/adaptive_retrieval_service.py

from enum import Enum
from typing import Dict

class QueryComplexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"

class AdaptiveRetrievalService:
    """自适应检索服务"""

    def __init__(
        self,
        retrieval_service,
        intent_classifier,
        complexity_evaluator,
    ):
        self.retrieval = retrieval_service
        self.intent_classifier = intent_classifier
        self.complexity_evaluator = complexity_evaluator

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
    ) -> Dict:
        """
        自适应检索

        根据查询复杂度自动选择最优策略
        """
        # 1. 评估查询复杂度
        complexity = await self.complexity_evaluator.evaluate(query)

        # 2. 根据复杂度路由
        if complexity == QueryComplexity.SIMPLE:
            return await self._simple_retrieval(query, top_k)
        elif complexity == QueryComplexity.MEDIUM:
            return await self._medium_retrieval(query, top_k)
        else:
            return await self._complex_retrieval(query, top_k)

    async def _simple_retrieval(self, query: str, top_k: int) -> Dict:
        """简单查询: Vector only"""
        return await self.retrieval.vector_search(
            VectorRequest(query=query, top_k=top_k)
        )

    async def _medium_retrieval(self, query: str, top_k: int) -> Dict:
        """中等查询: Hybrid (V+B+RRF)"""
        return await self.retrieval.hybrid_search(
            HybridRequest(query=query, top_k=top_k, enable_rerank=False)
        )

    async def _complex_retrieval(self, query: str, top_k: int) -> Dict:
        """复杂查询: Full pipeline (Multi-query + Rerank)"""
        # 生成多个子查询
        multi_queries = await self.multi_query_service.generate(query)

        # 并行检索
        results_list = await asyncio.gather(*[
            self.retrieval.hybrid_search(
                HybridRequest(query=q, top_k=top_k*2)
            )
            for q in multi_queries
        ])

        # 融合去重
        fused_docs = self._fuse_multi_results(results_list)

        # 重排
        reranked_docs = await self.rerank_service.rerank(
            query, fused_docs, top_k
        )

        return {"documents": reranked_docs, "strategy": "complex"}

# app/services/complexity_evaluator.py

class ComplexityEvaluator:
    """查询复杂度评估器"""

    async def evaluate(self, query: str) -> QueryComplexity:
        """
        评估查询复杂度

        特征:
        - 长度 (词数)
        - 实体密度
        - 子句数量
        - 歧义性
        """
        # 1. 基础特征
        words = query.split()
        word_count = len(words)

        # 2. 简单规则判断
        if word_count <= 10:
            return QueryComplexity.SIMPLE
        elif word_count <= 30:
            return QueryComplexity.MEDIUM
        else:
            return QueryComplexity.COMPLEX

        # TODO: 更精细的分类
        # - NER识别实体数量
        # - 依存句法分析子句
        # - 语义消歧
```

---

## 配置模板集合

### 主配置 (`configs/retrieval.yaml`)

```yaml
# Retrieval Service Configuration

app:
  name: "retrieval-service"
  version: "2.0.0"
  environment: "production"

# 基础检索配置
retrieval:
  vector:
    top_k: 20
    index_type: "HNSW"
    metric_type: "cosine"

  bm25:
    top_k: 20
    k1: 1.5
    b: 0.75

  graph:
    enabled: true
    top_k: 10
    depth: 2
    max_hops: 3

  hybrid:
    fusion_method: "rrf"  # rrf, weighted, max
    rrf_k: 60
    dynamic_weights: true  # Phase 4特性

# 查询优化
query_optimization:
  expansion:
    enabled: true
    methods: ["synonym", "spelling"]
    max_expansions: 3

  multi_query:
    enabled: false  # Phase 1启用
    num_queries: 3
    llm_model: "qwen-7b"

  hyde:
    enabled: false  # Phase 1启用
    num_hypotheses: 3
    fusion_method: "avg"

# 重排配置
reranking:
  enabled: true
  strategy: "multi_stage"  # single, multi_stage

  stage1:
    model: "BAAI/bge-reranker-base"
    top_k: 20
    batch_size: 32

  stage2:
    model: "BAAI/bge-reranker-large"
    top_k: 10
    use_llm: false
    llm_model: "gpt-4"

# 压缩
compression:
  enabled: false  # Phase 2启用
  method: "extractive"  # extractive, llm
  target_ratio: 0.5  # 压缩到50%

# 缓存
cache:
  enabled: true
  strategy: "two_level"  # single, two_level

  l1:
    ttl_seconds: 3600
    max_size_mb: 512

  l2:
    enabled: true
    ttl_seconds: 21600
    similarity_threshold: 0.95
    max_items: 10000

  warming:
    enabled: false  # Phase 2启用
    schedule: "0 */6 * * *"  # 每6小时
    top_n: 1000

# 自适应检索
adaptive:
  enabled: false  # Phase 4启用
  complexity_model: "rule_based"  # rule_based, ml
  strategies:
    simple:
      method: "vector_only"
      timeout_ms: 200
    medium:
      method: "hybrid"
      timeout_ms: 500
    complex:
      method: "agent"
      timeout_ms: 3000

# 成本控制
cost:
  tracking_enabled: true
  budget_alerts:
    enabled: true
    daily_limit_usd: 100
    warning_threshold: 0.8

  pricing:
    embedding_per_1k_tokens: 0.0001
    llm_per_1k_tokens: 0.002
    rerank_per_doc: 0.00001

# 性能
performance:
  timeout_ms: 5000
  max_concurrent_requests: 100
  batch_size: 32

# 可观测性
observability:
  metrics_enabled: true
  tracing_enabled: true
  logging_level: "INFO"
```

---

## 评测配置

### 评测套件配置 (`tests/eval/retrieval/config.yaml`)

```yaml
# Retrieval Evaluation Configuration

datasets:
  - name: "ms_marco_dev"
    path: "data/eval/ms_marco_dev_small.jsonl"
    format: "jsonl"
    fields:
      query: "query"
      doc_id: "doc_id"
      relevance: "label"

  - name: "internal_test_set"
    path: "data/eval/internal_queries.jsonl"
    format: "jsonl"

metrics:
  - "mrr@10"
  - "ndcg@10"
  - "recall@5"
  - "recall@10"
  - "precision@5"
  - "map@10"

strategies_to_eval:
  - name: "vector_only"
    config:
      method: "vector"
      top_k: 10

  - name: "hybrid_rrf"
    config:
      method: "hybrid"
      fusion: "rrf"
      top_k: 10
      rerank: false

  - name: "hybrid_rerank"
    config:
      method: "hybrid"
      fusion: "rrf"
      top_k: 10
      rerank: true

baseline:
  name: "vector_only"
  metrics:
    mrr@10: 0.65
    ndcg@10: 0.70
    recall@10: 0.75

output:
  report_path: "reports/eval_{timestamp}.html"
  detailed_results: true
  save_per_query: false
```

### 运行评测脚本 (`tests/eval/retrieval/run_evaluation.py`)

```python
#!/usr/bin/env python3
"""
检索质量评测脚本

Usage:
    python run_evaluation.py --config config.yaml --baseline
    python run_evaluation.py --strategy hybrid_rerank --dataset ms_marco_dev
"""

import asyncio
import argparse
from typing import List, Dict
import json
from pathlib import Path

# 评测指标
def calculate_mrr(results: List[Dict], k: int = 10) -> float:
    """Mean Reciprocal Rank"""
    reciprocal_ranks = []
    for result in results:
        for i, doc in enumerate(result["retrieved"][:k], 1):
            if doc["id"] in result["relevant_ids"]:
                reciprocal_ranks.append(1.0 / i)
                break
        else:
            reciprocal_ranks.append(0.0)
    return sum(reciprocal_ranks) / len(reciprocal_ranks)

def calculate_ndcg(results: List[Dict], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain"""
    # TODO: 实现NDCG计算
    pass

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--strategy", help="Single strategy to evaluate")
    parser.add_argument("--dataset", help="Dataset to use")
    parser.add_argument("--baseline", action="store_true", help="Compare with baseline")
    args = parser.parse_args()

    # 加载配置
    # 加载数据集
    # 运行评测
    # 生成报告

    print("Evaluation completed. Report saved to reports/")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 下一步

1. **Phase 1启动**: 实现Query Expansion (Task 1.1)
2. **搭建评测**: 准备测试数据，建立baseline
3. **Feature Flags**: 所有新特性通过配置开关控制
4. **创建PR模板**: 确保每个PR包含成本/性能影响说明

**相关文档**:
- [迭代计划](./retrieval-service-optimization.md)
- [任务清单](./retrieval-optimization-tasks.md)
- [Runbook](../runbook/index.md)
