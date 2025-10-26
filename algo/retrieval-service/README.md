# Retrieval Service

混合检索服务 - 提供向量检索、BM25 检索、混合检索（RRF 融合）和重排序功能。

## 🎯 核心功能

- **向量检索**: 基于 Milvus 的语义向量检索
- **BM25 检索**: 基于 Elasticsearch 的关键词检索
- **混合检索**: RRF (Reciprocal Rank Fusion) 融合向量和 BM25 结果
- **智能重排序**: 支持 Cross-Encoder 和 LLM 重排序
- **多租户支持**: 租户隔离和过滤
- **高性能**: 并行检索和异步处理

## 📋 技术栈

- **框架**: FastAPI 0.110+
- **向量数据库**: Milvus 2.3+
- **搜索引擎**: Elasticsearch 8.12+
- **重排模型**: Sentence-Transformers (Cross-Encoder)
- **Python**: 3.11+

## 🚀 快速开始

### 本地开发

```bash
# 安装依赖
make install

# 配置环境变量
export MILVUS_HOST=localhost
export MILVUS_PORT=19530
export ELASTICSEARCH_HOST=localhost
export ELASTICSEARCH_PORT=9200

# 运行服务
make run
```

服务将在 `http://localhost:8003` 启动。

### Docker 部署

```bash
# 构建镜像
make docker-build

# 运行容器
make docker-run

# 查看日志
make logs
```

## 📡 API 端点

### 1. 向量检索

```bash
POST /api/v1/retrieval/vector
```

**请求示例**:

```json
{
  "query": "什么是机器学习？",
  "query_embedding": [0.1, 0.2, ..., 0.9],
  "top_k": 10,
  "tenant_id": "tenant_123",
  "filters": {
    "category": "技术文档"
  }
}
```

**响应示例**:

```json
{
  "documents": [
    {
      "id": "doc_001",
      "chunk_id": "chunk_001",
      "content": "机器学习是人工智能的一个分支...",
      "score": 0.95,
      "metadata": { "category": "技术文档" },
      "source": "vector"
    }
  ],
  "query": "什么是机器学习？",
  "latency_ms": 15.2
}
```

### 2. BM25 检索

```bash
POST /api/v1/retrieval/bm25
```

**请求示例**:

```json
{
  "query": "机器学习 深度学习",
  "top_k": 10,
  "tenant_id": "tenant_123"
}
```

### 3. 混合检索

```bash
POST /api/v1/retrieval/hybrid
```

**请求示例**:

```json
{
  "query": "什么是机器学习？",
  "query_embedding": [0.1, 0.2, ..., 0.9],
  "top_k": 20,
  "tenant_id": "tenant_123",
  "enable_rerank": true,
  "rerank_top_k": 10
}
```

**响应示例**:

```json
{
  "documents": [
    {
      "id": "doc_001",
      "chunk_id": "chunk_001",
      "content": "机器学习是人工智能的一个分支...",
      "score": 0.92,
      "metadata": {},
      "source": "hybrid"
    }
  ],
  "query": "什么是机器学习？",
  "vector_count": 50,
  "bm25_count": 50,
  "reranked": true,
  "latency_ms": 125.3
}
```

## 配置说明

| 配置项                | 说明                   | 默认值                                |
| --------------------- | ---------------------- | ------------------------------------- |
| `MILVUS_HOST`         | Milvus 主机地址        | localhost                             |
| `MILVUS_PORT`         | Milvus 端口            | 19530                                 |
| `ELASTICSEARCH_HOST`  | Elasticsearch 主机地址 | localhost                             |
| `ELASTICSEARCH_PORT`  | Elasticsearch 端口     | 9200                                  |
| `VECTOR_TOP_K`        | 向量检索 top-k         | 50                                    |
| `BM25_TOP_K`          | BM25 检索 top-k        | 50                                    |
| `HYBRID_TOP_K`        | 混合检索 top-k         | 20                                    |
| `ENABLE_RERANK`       | 是否启用重排序         | true                                  |
| `RERANK_MODEL`        | 重排序模型类型         | cross-encoder                         |
| `CROSS_ENCODER_MODEL` | Cross-Encoder 模型名称 | cross-encoder/ms-marco-MiniLM-L-12-v2 |
| `RRF_K`               | RRF 参数               | 60                                    |

## 架构设计

### RRF 融合算法

```
RRF Score = sum(1 / (k + rank_i))

其中:
- k: RRF 参数（默认60）
- rank_i: 文档在第 i 个检索器中的排名
```

### 检索流程

```
Query
  |
  ├─> Vector Search (Milvus)  ──┐
  |                              |
  └─> BM25 Search (ES)       ──┤
                                 |
                                 v
                           RRF Fusion
                                 |
                                 v
                           Reranking (optional)
                                 |
                                 v
                              Results
```

### 重排序策略

1. **Cross-Encoder**: 使用 Sentence-Transformers 的 Cross-Encoder 模型

   - 优点: 精度高，速度快
   - 适用场景: 大多数场景

2. **LLM Rerank**: 使用大语言模型进行重排序
   - 优点: 理解能力强，适合复杂查询
   - 缺点: 延迟较高，成本较高
   - 适用场景: 高价值查询

## 性能优化

- **并行检索**: 向量和 BM25 检索并行执行
- **异步处理**: 所有 I/O 操作异步化
- **连接池**: Milvus 和 Elasticsearch 连接复用
- **缓存**: Redis 缓存热门查询结果

## 监控指标

- `retrieval_search_duration_seconds`: 检索延迟
- `retrieval_search_total`: 检索请求总数
- `retrieval_fusion_duration_seconds`: RRF 融合延迟
- `retrieval_rerank_duration_seconds`: 重排序延迟

## 故障排查

### Milvus 连接失败

```bash
# 检查 Milvus 状态
curl http://localhost:9091/healthz

# 检查配置
echo $MILVUS_HOST
echo $MILVUS_PORT
```

### Elasticsearch 连接失败

```bash
# 检查 Elasticsearch 状态
curl http://localhost:9200/_cluster/health

# 检查配置
echo $ELASTICSEARCH_HOST
echo $ELASTICSEARCH_PORT
```

### 重排序模型加载失败

```bash
# 检查模型是否下载
ls ~/.cache/huggingface/hub/

# 手动下载模型
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')"
```

## 开发指南

### 添加新的检索策略

1. 在 `app/services/` 创建新的服务类
2. 在 `RetrievalService` 中集成新策略
3. 在 `app/routers/retrieval.py` 添加新的 API 端点

### 添加新的重排序模型

1. 在 `RerankService` 中添加新的模型类型
2. 实现对应的重排序方法
3. 更新配置和文档

## 📚 相关文档

- [Milvus 文档](https://milvus.io/docs)
- [Elasticsearch 文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Sentence-Transformers](https://www.sbert.net/)
- [RRF 算法](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

## 📝 License

MIT License
