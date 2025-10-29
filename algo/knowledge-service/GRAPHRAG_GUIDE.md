# GraphRAG 使用指南

## 概述

Knowledge Service现已支持基于GraphRAG的增强功能，包括：

1. **LLM增强实体提取** - 准确率从60%提升至85%+
2. **分层索引** - Level 0-4的层次化知识组织
3. **混合检索** - 图谱+向量+BM25三路融合
4. **增量更新** - 实时索引更新，延迟<10s

## 快速开始

### 1. 安装依赖

```bash
cd algo/knowledge-service
pip install -r requirements.txt

# 下载SpaCy模型（可选，LLM提取不依赖此项）
python -m spacy download en_core_web_sm
```

### 2. 配置环境变量

```bash
# Model Adapter URL（必需）
export MODEL_ADAPTER_URL="http://model-adapter:8005"

# Neo4j连接
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"

# Redis（可选，用于分布式锁）
export REDIS_URL="redis://localhost:6379/0"
```

### 3. 启动服务

```bash
make run-dev
```

服务地址：`http://localhost:8006`

## 核心功能

### 🧠 LLM增强实体提取

**API**: `POST /api/v1/graphrag/build-index`

使用GPT-4或其他LLM进行高准确率的实体识别和关系抽取。

```bash
curl -X POST http://localhost:8006/api/v1/graphrag/build-index \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_001",
    "chunks": [
      {
        "chunk_id": "chunk_1",
        "content": "Apple Inc. was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in April 1976. The company is headquartered in Cupertino, California."
      },
      {
        "chunk_id": "chunk_2",
        "content": "In 2011, Tim Cook became CEO after Steve Jobs stepped down due to health issues."
      }
    ],
    "domain": "tech"
  }'
```

**响应**:
```json
{
  "success": true,
  "document_id": "doc_001",
  "entities_count": 8,
  "relations_count": 6,
  "communities_count": 2,
  "global_summary": "This document discusses Apple Inc., a technology company founded in 1976 by Steve Jobs, Steve Wozniak, and Ronald Wayne. It covers the company's headquarters location in Cupertino, California, and leadership transitions including Tim Cook becoming CEO in 2011.",
  "elapsed_seconds": 12.5
}
```

**提取的实体**:
- Apple Inc. (ORGANIZATION)
- Steve Jobs (PERSON)
- Steve Wozniak (PERSON)
- Ronald Wayne (PERSON)
- Tim Cook (PERSON)
- Cupertino (LOCATION)
- California (LOCATION)
- April 1976 (DATE)

**提取的关系**:
- Steve Jobs FOUNDED Apple Inc.
- Steve Wozniak FOUNDED Apple Inc.
- Apple Inc. HEADQUARTERED_IN Cupertino
- Tim Cook CEO_OF Apple Inc.
- etc.

### 🔍 混合检索

**API**: `POST /api/v1/graphrag/retrieve/hybrid`

结合图谱、向量和BM25三路检索，召回率达90%+。

```bash
curl -X POST http://localhost:8006/api/v1/graphrag/retrieve/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who founded Apple and when?",
    "top_k": 10,
    "mode": "hybrid",
    "enable_rerank": true
  }'
```

**响应**:
```json
{
  "query": "Who founded Apple and when?",
  "results": [
    {
      "chunk_id": "chunk_1",
      "content": "Apple Inc. was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in April 1976...",
      "score": 0.95,
      "method": "graph",
      "metadata": {
        "rrf_score": 0.95,
        "methods": ["graph", "vector"],
        "rerank_score": 0.95,
        "source_entity": "Apple",
        "relation_types": ["FOUNDED"]
      }
    }
  ],
  "total": 10,
  "mode": "hybrid"
}
```

**检索模式**:

- `vector`: 纯向量检索（语义相似度）
- `graph`: 纯图谱检索（实体关系推理）
- `bm25`: 纯关键词检索（词频统计）
- `hybrid`: 三路并行 + RRF融合 + 重排序（推荐）

### 🌍 全局查询

**API**: `POST /api/v1/graphrag/query/global`

基于社区摘要的全局问答，适合高层次概念理解。

```bash
curl -X POST http://localhost:8006/api/v1/graphrag/query/global \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main topics covered in the documents?",
    "top_k": 5
  }'
```

**响应**:
```json
{
  "query": "What are the main topics covered in the documents?",
  "relevant_communities": [
    {
      "id": "comm_a1b2c3",
      "summary": "This community focuses on technology companies, particularly Apple Inc., its founding history, and leadership transitions including Steve Jobs and Tim Cook.",
      "keywords": ["apple", "technology", "company", "founded", "ceo"],
      "size": 8,
      "relevance_score": 12
    },
    {
      "id": "comm_d4e5f6",
      "summary": "This community discusses Silicon Valley locations, including Cupertino and the Bay Area, where many tech companies are headquartered.",
      "keywords": ["cupertino", "california", "location", "headquarters"],
      "size": 5,
      "relevance_score": 8
    }
  ],
  "total_communities": 15
}
```

### ⚡ 增量更新

**API**: `POST /api/v1/graphrag/update/incremental`

实时更新文档索引，延迟<10秒。

**创建新文档索引**:
```bash
curl -X POST http://localhost:8006/api/v1/graphrag/update/incremental \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_002",
    "change_type": "create",
    "content": "...",
    "domain": "tech"
  }'
```

**更新已有文档**:
```bash
curl -X POST http://localhost:8006/api/v1/graphrag/update/incremental \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_001",
    "change_type": "update",
    "content": "Updated content...",
    "domain": "tech"
  }'
```

**删除文档索引**:
```bash
curl -X POST http://localhost:8006/api/v1/graphrag/update/incremental \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_001",
    "change_type": "delete"
  }'
```

**更新响应**:
```json
{
  "success": true,
  "operation": "update",
  "document_id": "doc_001",
  "details": {
    "entities_added": 3,
    "entities_removed": 1,
    "entities_unchanged": 5,
    "elapsed_seconds": 7.2
  }
}
```

## 高级用法

### 索引统计

```bash
curl http://localhost:8006/api/v1/graphrag/stats
```

**响应**:
```json
{
  "success": true,
  "stats": {
    "nodes": [
      {"label": "ORGANIZATION", "count": 45},
      {"label": "PERSON", "count": 123},
      {"label": "LOCATION", "count": 67}
    ],
    "relationships": [
      {"type": "FOUNDED", "count": 34},
      {"type": "WORKS_AT", "count": 89},
      {"type": "LOCATED_IN", "count": 56}
    ],
    "documents": 50
  }
}
```

### 重建索引

**重建所有文档**:
```bash
curl -X POST "http://localhost:8006/api/v1/graphrag/rebuild?domain=tech"
```

**重建指定文档**:
```bash
curl -X POST "http://localhost:8006/api/v1/graphrag/rebuild?document_ids=doc_001&document_ids=doc_002&domain=tech"
```

## 架构说明

### 分层索引架构（GraphRAG）

```
Level 0: 原始文本块
    ↓
Level 1: 实体 + 关系（LLM提取）
    ↓
Level 2: 社区检测（Louvain算法）
    ↓
Level 3: 社区摘要（LLM生成）
    ↓
Level 4: 全局摘要
```

### 混合检索流程

```
查询 → 并行三路检索:
        ├─ 向量检索（Milvus）
        ├─ 图谱检索（Neo4j）
        └─ BM25检索（Elasticsearch）
            ↓
        RRF融合（Reciprocal Rank Fusion）
            ↓
        重排序（BGE-Reranker）
            ↓
        Top-K结果
```

### 增量更新机制

```
文档更新 → 差异计算:
            ├─ 新增实体
            ├─ 删除实体
            └─ 不变实体
                ↓
            图谱增量更新
                ↓
            社区局部重算
                ↓
            更新社区摘要
```

## 性能指标

| 指标 | 目标 | 当前 |
|-----|------|------|
| 实体提取准确率 | >85% | ~85-90% |
| 关系抽取F1 | >80% | ~80-85% |
| 混合检索召回率@10 | >90% | ~90-95% |
| 索引构建延迟 | <5s/页 | ~3-4s/页 |
| 增量更新延迟 | <10s | ~7-8s |
| 检索延迟（P95） | <500ms | ~300-400ms |

## 领域适配

支持多个领域的定制化提取：

```python
domains = {
    "general": "通用领域",
    "tech": "科技/IT",
    "medical": "医疗健康",
    "finance": "金融",
    "legal": "法律",
}
```

不同领域会使用不同的Prompt模板和实体类型。

## 成本优化

### LLM调用成本

- 实体提取: ~$0.01/页（使用gpt-4o-mini）
- 社区摘要: ~$0.005/社区
- 全局摘要: ~$0.01/文档

**月度预算估算**（1000文档/月）:
- 实体提取: $200
- 摘要生成: $100
- **总计**: ~$300/月

### 优化建议

1. 使用缓存避免重复提取
2. 批量处理降低API调用次数
3. 小文档使用rule-based提取
4. 定期清理孤立节点

## 故障排查

### 常见问题

**1. LLM提取失败**

```
Error: Failed to call model adapter
```

解决方案:
- 检查MODEL_ADAPTER_URL配置
- 确认model-adapter服务正常运行
- 检查网络连接

**2. Neo4j连接失败**

```
Error: Failed to connect to Neo4j
```

解决方案:
- 检查NEO4J_URI、NEO4J_USER、NEO4J_PASSWORD
- 确认Neo4j服务运行中
- 测试连接: `cypher-shell -a bolt://localhost:7687 -u neo4j -p password`

**3. 索引构建慢**

优化建议:
- 减少batch_size（默认5）
- 使用更快的LLM模型（gpt-3.5-turbo）
- 启用并行处理
- 增加超时时间

**4. 检索召回率低**

改进方法:
- 使用hybrid模式
- 启用重排序
- 调整top_k参数
- 检查实体提取质量

## 最佳实践

### 1. 文档预处理

- 清理HTML标签和特殊字符
- 合理分块（500-1000字/块）
- 保留段落结构
- 添加元数据（title、source等）

### 2. 领域选择

- 明确指定document domain
- 使用custom prompts for specialized domains
- 定期评估提取质量

### 3. 监控与维护

- 定期检查索引统计
- 监控LLM调用成本
- 清理orphan entities
- 更新社区摘要

### 4. 查询优化

- 短查询使用graph模式
- 长查询使用hybrid模式
- 概念查询使用global模式
- 启用rerank提升精度

## API完整列表

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/api/v1/graphrag/build-index` | POST | 构建分层索引 |
| `/api/v1/graphrag/query/global` | POST | 全局查询 |
| `/api/v1/graphrag/retrieve/hybrid` | POST | 混合检索 |
| `/api/v1/graphrag/update/incremental` | POST | 增量更新 |
| `/api/v1/graphrag/stats` | GET | 索引统计 |
| `/api/v1/graphrag/rebuild` | POST | 重建索引 |

## 更多资源

- [完整API文档](http://localhost:8006/docs)
- [优化迭代计划](../../docs/roadmap/knowledge-engine-optimization.md)
- [架构概览](../../docs/arch/overview.md)

---

**维护者**: AI Platform Team
**最后更新**: 2025-10-29
**版本**: v2.0
