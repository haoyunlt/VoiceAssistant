# RAG Engine Iter 1 使用指南

> **快速上手 RAG Engine v2.0 新功能**

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/rag-engine

# 安装所有依赖
pip install -r requirements.txt

# 或者仅安装 Iter 1 新增依赖
pip install rank-bm25==0.2.2 faiss-cpu==1.7.4 sentence-transformers==2.5.1
```

### 2. 启动 Redis

```bash
# 使用 Docker 启动
docker run -d --name rag-redis -p 6379:6379 redis:7-alpine

# 或使用 docker-compose
docker-compose up -d redis
```

### 3. 启动 RAG Engine

```bash
# 开发模式
python main.py

# 或使用 make
make run
```

服务将在 `http://localhost:8006` 启动

---

## 📝 功能使用示例

### 1. 混合检索（Vector + BM25 + RRF）

```python
from app.retrieval.hybrid_retriever import get_hybrid_retriever

# 初始化混合检索器
hybrid_retriever = get_hybrid_retriever()

# 向量检索结果（来自向量数据库）
vector_results = [
    {"id": "doc1", "text": "...", "score": 0.85},
    {"id": "doc2", "text": "...", "score": 0.78},
]

# 执行混合检索（自动调用 BM25 并融合）
results = hybrid_retriever.retrieve(
    query="什么是检索增强生成？",
    vector_results=vector_results,
    top_k=10,
    fusion_method="rrf",  # 推荐使用 RRF
)

# 查看融合后的结果
for doc in results[:3]:
    print(f"ID: {doc['id']}, RRF Score: {doc['rrf_score']:.4f}")
```

**配置参数**（环境变量）：
```bash
export HYBRID_BM25_WEIGHT=0.3      # BM25 权重
export HYBRID_VECTOR_WEIGHT=0.7     # Vector 权重
export HYBRID_RRF_K=60              # RRF 参数 k
```

---

### 2. Cross-Encoder 重排

```python
from app.reranking.reranker import get_reranker

# 初始化重排器
reranker = get_reranker()

# 文档列表
documents = [
    {"id": "doc1", "text": "检索增强生成是一种结合检索与生成的技术...", "score": 0.85},
    {"id": "doc2", "text": "RAG 通过检索相关文档来增强LLM的回答...", "score": 0.78},
    {"id": "doc3", "text": "向量数据库用于存储文档的向量表示...", "score": 0.72},
]

# 重排序
reranked_docs = reranker.rerank(
    query="什么是RAG？",
    documents=documents,
)

# 查看重排后的结果
for doc in reranked_docs:
    print(f"ID: {doc['id']}")
    print(f"  Original Score: {doc['original_score']:.4f}")
    print(f"  Rerank Score: {doc['rerank_score']:.4f}")
```

**配置参数**：
```bash
export RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
export RERANK_TOP_K=10
export RERANK_DEVICE=cpu  # or cuda
```

---

### 3. FAISS 语义缓存

```python
from app.services.semantic_cache_service import SemanticCacheService

# 初始化缓存服务
cache_service = SemanticCacheService(
    redis_host="localhost",
    redis_port=6379,
    similarity_threshold=0.92,  # 提高阈值，更严格匹配
    use_faiss=True,              # 启用 FAISS 加速
)

# 查询缓存
query = "什么是RAG？"
cached_answer = await cache_service.get_cached_answer(query)

if cached_answer:
    print(f"✅ Cache HIT!")
    print(f"   Similarity: {cached_answer.similarity:.4f}")
    print(f"   Original Query: {cached_answer.original_query}")
    print(f"   Answer: {cached_answer.answer}")
else:
    print("❌ Cache MISS, proceeding with retrieval...")

    # 执行 RAG 查询...
    answer = "检索增强生成是..."
    sources = [...]

    # 缓存结果
    await cache_service.set_cached_answer(query, answer, sources)

# 查看统计
stats = await cache_service.get_cache_stats()
print(f"\n📊 Cache Stats:")
print(f"   Hit Rate: {stats['runtime_stats']['hit_rate']:.2f}%")
print(f"   Avg Latency: {stats['runtime_stats']['avg_latency_ms']:.2f}ms")
print(f"   FAISS Indexed: {stats['faiss_indexed_count']} vectors")
```

---

### 4. Prometheus 指标收集

```python
from app.observability.metrics import RAGMetrics, record_cache_hit, record_cache_miss

# 方式 1: 使用上下文管理器（推荐）
with RAGMetrics(mode="advanced", tenant_id="tenant_001") as metrics:
    # 执行 RAG 流程

    # 记录检索
    metrics.record_retrieval(
        strategy="hybrid",
        latency_ms=450.5,
        doc_count=20
    )

    # 记录重排
    metrics.record_rerank(
        model="cross-encoder",
        latency_ms=150.2,
        avg_score=0.85
    )

    # 记录 LLM
    metrics.record_llm(
        model="gpt-4-turbo",
        latency_ms=1200.3,
        tokens_used=1500
    )

    # 记录答案
    metrics.record_answer("这是生成的答案...")

    # 自动记录 E2E 延迟和请求状态

# 方式 2: 手动记录特定指标
from app.observability.metrics import record_retrieval_latency

record_retrieval_latency("hybrid", "tenant_001", 450.5)
record_cache_hit("tenant_001")
```

**查看指标**：
```bash
# 访问 Prometheus metrics 端点
curl http://localhost:8006/metrics

# 筛选 RAG 相关指标
curl http://localhost:8006/metrics | grep rag_

# 示例输出：
# rag_retrieval_latency_ms_bucket{strategy="hybrid",tenant_id="tenant_001",le="500.0"} 8
# rag_cache_operations_total{operation="hit",tenant_id="tenant_001"} 15
# rag_token_usage_total{phase="generation",model="gpt-4",tenant_id="tenant_001"} 12500
```

---

### 5. 整合使用（Enhanced RAG Service）

```python
from app.services.enhanced_rag_service import get_enhanced_rag_service

# 初始化（需要提供 retrieval_client 和 llm_client）
rag_service = get_enhanced_rag_service(
    retrieval_client=your_retrieval_client,
    llm_client=your_llm_client,
    enable_hybrid=True,    # 启用混合检索
    enable_rerank=True,    # 启用重排
    enable_cache=True,     # 启用语义缓存
)

# 执行查询（自动完成所有优化流程）
result = await rag_service.query(
    query="解释一下RAG技术的工作原理",
    tenant_id="tenant_001",
    mode="advanced",
    top_k=5,
    temperature=0.7,
)

# 查看结果
print(f"Answer: {result['answer']}")
print(f"From Cache: {result['from_cache']}")
print(f"Retrieved Docs: {result['retrieved_count']}")
print(f"\nMetrics:")
print(f"  Retrieval: {result['metrics']['retrieval_latency_ms']:.2f}ms")
print(f"  Rerank: {result['metrics']['rerank_latency_ms']:.2f}ms")
print(f"  LLM: {result['metrics']['llm_latency_ms']:.2f}ms")

# 查看服务统计
stats = await rag_service.get_stats()
print(f"\n📈 Service Stats:")
print(f"Enabled Features: {stats['enabled_features']}")
print(f"Cache Hit Rate: {stats['cache_stats']['runtime_stats']['hit_rate']}%")
```

---

## 🔧 配置参数

### 环境变量

```bash
# RAG Engine 基础配置
export RAG_SERVICE_PORT=8006
export RAG_LOG_LEVEL=INFO

# 混合检索
export HYBRID_BM25_WEIGHT=0.3
export HYBRID_VECTOR_WEIGHT=0.7
export HYBRID_RRF_K=60

# 重排器
export RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
export RERANK_TOP_K=10
export RERANK_DEVICE=cpu

# 语义缓存
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export CACHE_SIMILARITY_THRESHOLD=0.92
export CACHE_TTL=3600
export CACHE_MAX_QUERIES=10000
export CACHE_USE_FAISS=true

# 可观测性
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export PROMETHEUS_METRICS_PORT=8006
```

### YAML 配置（推荐）

参考 `configs/rag-engine.yaml` 的配置结构（已创建）

---

## 📊 性能监控

### Grafana Dashboard

**访问**: `http://grafana.example.com/d/rag-engine`

**关键面板**:
1. **核心指标**
   - E2E 延迟 (P50/P95/P99)
   - QPS & 成功率
   - 缓存命中率
   - Token 使用趋势

2. **检索分析**
   - 检索策略分布（Vector/BM25/Hybrid）
   - 重排分数分布
   - 检索文档数分布

3. **成本分析**
   - 每请求成本（按租户）
   - Token 使用分解（检索/生成/验证）
   - Top 10 耗费查询

### PromQL 查询示例

```promql
# 检索延迟 P95
histogram_quantile(0.95, rate(rag_retrieval_latency_ms_bucket[5m]))

# 缓存命中率
rate(rag_cache_operations_total{operation="hit"}[5m]) /
rate(rag_cache_operations_total[5m]) * 100

# 每分钟 Token 消耗
rate(rag_token_usage_total[1m])
```

---

## 🧪 测试与验证

### 健康检查

```bash
# 服务健康
curl http://localhost:8006/health

# 预期输出
{
  "status": "healthy",
  "service": "rag-engine"
}
```

### 功能测试

```bash
# 测试混合检索
curl -X POST http://localhost:8006/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是RAG？",
    "mode": "advanced",
    "tenant_id": "test_tenant",
    "top_k": 5
  }'
```

### 运行评测

```bash
cd tests/eval

# 准备数据集（首次运行）
# python scripts/prepare_datasets.py

# 运行评测
python scripts/run_eval.py \
  --dataset datasets/general_qa.jsonl \
  --output results/iter1_$(date +%Y%m%d).json

# 查看结果
cat results/iter1_*.json | jq .summary
```

---

## 🐛 故障排查

### 常见问题

**Q1: FAISS 安装失败**

```bash
# 方法 1: 使用 conda
conda install -c conda-forge faiss-cpu

# 方法 2: 使用 pip（确保版本匹配）
pip install faiss-cpu==1.7.4

# 如果仍失败，可以禁用 FAISS
export CACHE_USE_FAISS=false
```

**Q2: Redis 连接失败**

```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 测试连接
redis-cli ping
# 应返回: PONG

# 检查配置
echo $REDIS_HOST
echo $REDIS_PORT
```

**Q3: Cross-Encoder 模型加载慢**

```bash
# 首次运行会下载模型，可以提前下载
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# 或使用本地模型
export RERANK_MODEL=/path/to/local/model
```

**Q4: 内存不足**

```bash
# 减少缓存大小
export CACHE_MAX_QUERIES=5000

# 使用更小的重排模型
export RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2  # 已是最小版本

# 禁用 FAISS（节省内存）
export CACHE_USE_FAISS=false
```

---

## 📖 更多资源

- [RAG Engine 优化迭代计划](../../../docs/RAG_ENGINE_ITERATION_PLAN.md)
- [Iter 1 完成总结](../../../docs/RAG_ITER1_COMPLETION.md)
- [评测指南](tests/eval/README.md)
- [配置文件](../../../configs/rag-engine.yaml)

---

## 🤝 反馈与贡献

遇到问题或有建议？

- **Issue**: [GitHub Issues](https://github.com/xxx/voicehelper/issues)
- **Slack**: #rag-optimization
- **Email**: team@example.com

---

**版本**: v2.0 (Iter 1)
**最后更新**: 2025-01-29
