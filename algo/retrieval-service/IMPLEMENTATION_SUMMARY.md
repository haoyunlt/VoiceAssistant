# Retrieval Service - 实现总结

## 📋 实现概述

本文档总结了 **Retrieval Service**（检索服务）的完整实现，这是一个基于 FastAPI 的 Python 微服务，提供混合检索（向量+BM25）和重排序功能。

## 🎯 核心功能

### 1. 向量检索 (Vector Search)

- **技术**: Milvus 2.3+
- **算法**: 内积 (Inner Product) - Cosine Similarity
- **索引**: HNSW (Hierarchical Navigable Small World)
- **特性**:
  - 语义相似度检索
  - 多租户隔离
  - 标量过滤 (tenant_id, metadata)
  - Top-K 检索

### 2. BM25 检索

- **技术**: Elasticsearch 8.12+
- **算法**: BM25 (Best Matching 25)
- **特性**:
  - 关键词匹配
  - 全文检索
  - 布尔查询
  - 过滤条件

### 3. 混合检索 (Hybrid Search)

- **融合算法**: RRF (Reciprocal Rank Fusion)
- **公式**: `RRF Score = sum(1 / (k + rank_i))`
- **流程**:
  1. 并行执行向量检索和 BM25 检索
  2. RRF 融合两种检索结果
  3. 可选重排序

### 4. 智能重排序

- **Cross-Encoder**:

  - 模型: `cross-encoder/ms-marco-MiniLM-L-12-v2`
  - 优点: 精度高，速度快
  - 适用: 大多数场景

- **LLM Rerank**:
  - 调用 Model Adapter 服务
  - 优点: 理解能力强
  - 适用: 复杂查询

## 📁 目录结构

```
algo/retrieval-service/
├── main.py                          # FastAPI 应用入口
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # 配置管理 (Pydantic Settings)
│   │   └── logging_config.py        # 日志配置
│   ├── models/
│   │   ├── __init__.py
│   │   └── retrieval.py             # 数据模型 (Request/Response)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py                # 健康检查
│   │   └── retrieval.py             # 检索 API
│   └── services/
│       ├── __init__.py
│       ├── retrieval_service.py     # 检索编排服务
│       ├── vector_service.py        # Milvus 向量检索
│       ├── bm25_service.py          # Elasticsearch BM25 检索
│       ├── hybrid_service.py        # RRF 融合
│       └── rerank_service.py        # 重排序服务
├── requirements.txt
├── Dockerfile
├── Makefile
├── README.md
└── IMPLEMENTATION_SUMMARY.md        # 本文件
```

## 🔧 核心实现

### 1. 配置管理 (`app/core/config.py`)

```python
class Settings(BaseSettings):
    # 向量数据库
    MILVUS_HOST: str
    MILVUS_PORT: int
    VECTOR_TOP_K: int = 50

    # BM25 检索
    ELASTICSEARCH_HOST: str
    ELASTICSEARCH_PORT: int
    BM25_TOP_K: int = 50

    # 混合检索
    HYBRID_TOP_K: int = 20
    RRF_K: int = 60

    # 重排序
    ENABLE_RERANK: bool = True
    RERANK_MODEL: str = "cross-encoder"
    RERANK_TOP_K: int = 10
```

### 2. 向量检索 (`app/services/vector_service.py`)

- Milvus Collection 管理
- HNSW 索引配置
- 标量过滤表达式构建
- 租户隔离

### 3. BM25 检索 (`app/services/bm25_service.py`)

- Elasticsearch 查询构建
- 多字段匹配
- 布尔过滤
- 分数归一化

### 4. RRF 融合 (`app/services/hybrid_service.py`)

```python
# RRF 算法实现
rrf_scores = {}
for rank, doc in enumerate(vector_docs, start=1):
    key = doc.chunk_id
    rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (rrf_k + rank))

for rank, doc in enumerate(bm25_docs, start=1):
    key = doc.chunk_id
    rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (rrf_k + rank))
```

### 5. 重排序 (`app/services/rerank_service.py`)

- Cross-Encoder 模型加载
- 异步推理
- LLM 重排序（可选）
- 降级策略

### 6. 检索编排 (`app/services/retrieval_service.py`)

```python
async def hybrid_search(self, request: HybridRequest):
    # 1. 并行检索
    vector_task = self.vector_service.search(...)
    bm25_task = self.bm25_service.search(...)
    vector_docs, bm25_docs = await asyncio.gather(vector_task, bm25_task)

    # 2. RRF 融合
    fused_docs = await self.hybrid_service.fuse_results(...)

    # 3. 重排序（可选）
    if enable_rerank:
        fused_docs = await self.rerank_service.rerank(...)

    return HybridResponse(documents=fused_docs, ...)
```

## 📡 API 接口

### 1. 向量检索

```
POST /api/v1/retrieval/vector
```

### 2. BM25 检索

```
POST /api/v1/retrieval/bm25
```

### 3. 混合检索

```
POST /api/v1/retrieval/hybrid
```

## 🎨 数据模型

### RetrievalDocument

```python
class RetrievalDocument(BaseModel):
    id: str                    # 文档ID
    chunk_id: str              # 分块ID
    content: str               # 内容
    score: float               # 分数
    metadata: Dict[str, Any]   # 元数据
    source: Optional[str]      # 来源 (vector/bm25/hybrid)
```

### HybridRequest

```python
class HybridRequest(BaseModel):
    query: str
    query_embedding: Optional[List[float]]
    top_k: Optional[int]
    tenant_id: Optional[str]
    filters: Optional[Dict[str, Any]]
    enable_rerank: Optional[bool]
    rerank_top_k: Optional[int]
```

### HybridResponse

```python
class HybridResponse(BaseModel):
    documents: List[RetrievalDocument]
    query: str
    vector_count: int          # 向量检索结果数
    bm25_count: int            # BM25 检索结果数
    reranked: bool             # 是否重排序
    latency_ms: float          # 总延迟
```

## 🚀 性能优化

### 1. 并行检索

```python
# 向量和 BM25 检索并行执行
vector_task = self.vector_service.search(...)
bm25_task = self.bm25_service.search(...)
vector_docs, bm25_docs = await asyncio.gather(vector_task, bm25_task)
```

### 2. 异步处理

- 所有 I/O 操作异步化
- 重排序使用线程池避免阻塞

### 3. 连接池

- Milvus 连接复用
- Elasticsearch 连接池

### 4. 缓存（可选）

- Redis 缓存热门查询
- TTL 1 小时

## 📊 监控指标

### 延迟指标

- `retrieval_search_duration_seconds`: 检索延迟
- `retrieval_fusion_duration_seconds`: 融合延迟
- `retrieval_rerank_duration_seconds`: 重排序延迟

### 业务指标

- `retrieval_search_total`: 检索请求总数
- `retrieval_documents_returned`: 返回文档数
- `retrieval_fusion_ratio`: 融合比例

## 🔄 集成关系

### 上游服务

- **RAG Engine**: 调用混合检索 API
- **AI Orchestrator**: 检索任务编排

### 下游服务

- **Milvus**: 向量检索
- **Elasticsearch**: BM25 检索
- **Model Adapter**: LLM 重排序（可选）

## 🧪 测试要点

### 单元测试

- [ ] RRF 融合算法正确性
- [ ] 重排序逻辑
- [ ] 配置加载

### 集成测试

- [ ] Milvus 连接和查询
- [ ] Elasticsearch 连接和查询
- [ ] 混合检索端到端流程

### 性能测试

- [ ] 向量检索延迟 < 10ms
- [ ] BM25 检索延迟 < 20ms
- [ ] 混合检索延迟 < 50ms (不含重排序)
- [ ] 重排序延迟 < 100ms

## 🔐 安全考虑

- **租户隔离**: 所有查询强制 tenant_id 过滤
- **输入验证**: Pydantic 模型验证
- **SQL 注入防护**: 使用 ORM 参数化查询
- **DoS 防护**: 限制 top_k 最大值

## 📝 配置示例

### 生产环境配置

```yaml
MILVUS_HOST: milvus.voiceassistant.svc.cluster.local
MILVUS_PORT: 19530
ELASTICSEARCH_HOST: elasticsearch.voiceassistant.svc.cluster.local
ELASTICSEARCH_PORT: 9200

VECTOR_TOP_K: 50
BM25_TOP_K: 50
HYBRID_TOP_K: 20
RRF_K: 60

ENABLE_RERANK: true
RERANK_MODEL: cross-encoder
RERANK_TOP_K: 10

LOG_LEVEL: INFO
```

## 🐛 已知问题与限制

1. **Embedding 依赖**: 当前需要调用方提供 query_embedding，未来应集成 embedding 服务
2. **缓存**: Redis 缓存尚未实现
3. **监控**: Prometheus 指标尚未完整集成
4. **重排序**: LLM 重排序实现简化，需要更精细的提示工程

## 🔮 后续优化

1. **集成 Embedding 服务**: 自动获取查询向量
2. **实现语义缓存**: 基于查询相似度的缓存
3. **多模态检索**: 支持图像、音频等多模态检索
4. **查询改写**: 自动查询扩展和改写
5. **个性化检索**: 基于用户历史的个性化排序
6. **成本优化**: 动态调整检索策略以平衡成本和质量

## ✅ 验收清单

- [x] 向量检索实现（Milvus）
- [x] BM25 检索实现（Elasticsearch）
- [x] RRF 融合算法实现
- [x] Cross-Encoder 重排序实现
- [x] LLM 重排序框架实现
- [x] 混合检索编排实现
- [x] 多租户支持
- [x] 健康检查 API
- [x] 配置管理（Pydantic）
- [x] 日志配置
- [x] Dockerfile 和 Makefile
- [x] API 文档（README）
- [x] 实现总结（本文档）

## 📚 参考资料

- [Milvus 官方文档](https://milvus.io/docs)
- [Elasticsearch 官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [RRF 论文](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [Sentence-Transformers](https://www.sbert.net/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)

---

**实现完成日期**: 2025-10-26
**版本**: v1.0.0
**实现者**: AI Assistant
