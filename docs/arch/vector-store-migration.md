# 向量库迁移指南

## 迁移概述

本文档描述了从直接调用 Milvus 客户端到使用向量库适配服务（Vector Store Adapter）的迁移过程。

## 迁移动机

### 为什么需要适配层？

1. **解耦**：上层服务不需要关心底层使用哪个向量数据库
2. **灵活性**：可以随时切换向量数据库而不影响上层服务
3. **统一管理**：集中管理向量数据库连接和配置
4. **性能优化**：统一的缓存和连接池管理
5. **可观测性**：集中的监控和日志

### 架构对比

#### 迁移前

```
indexing-service  →  MilvusClient  →  Milvus
retrieval-service →  MilvusClient  →  Milvus
```

#### 迁移后

```
indexing-service  →  VectorStoreClient  →  Vector Store Adapter  →  Milvus/pgvector
retrieval-service →  VectorStoreClient  →  Vector Store Adapter  →  Milvus/pgvector
```

## 迁移步骤

### 1. 部署 Vector Store Adapter 服务

```bash
cd deployments/docker
docker-compose -f docker-compose.vector-store-adapter.yml up -d
```

验证服务运行：

```bash
curl http://localhost:8003/health
curl http://localhost:8003/ready
```

### 2. 修改 indexing-service

#### 2.1 添加 VectorStoreClient

创建 `app/infrastructure/vector_store_client.py`：

```python
from app.infrastructure.vector_store_client import VectorStoreClient
```

#### 2.2 修改 document_processor.py

```python
# 迁移前
from app.infrastructure.milvus_client import MilvusClient
self.milvus_client = MilvusClient()
await self.milvus_client.insert_batch(data)

# 迁移后
from app.infrastructure.vector_store_client import VectorStoreClient
self.vector_store_client = VectorStoreClient()
await self.vector_store_client.insert_batch(data)
```

#### 2.3 更新依赖

```diff
# requirements.txt
- pymilvus==2.3.6
+ # pymilvus==2.3.6  # 已迁移到 vector-store-adapter
+ httpx==0.26.0  # 用于调用 vector-store-adapter
```

### 3. 修改 retrieval-service

#### 3.1 添加 VectorStoreClient

创建 `app/infrastructure/vector_store_client.py`

#### 3.2 修改 vector_retriever.py

```python
# 迁移前
from app.infrastructure.milvus_client import MilvusClient
self.milvus_client = MilvusClient()
results = await self.milvus_client.search(...)

# 迁移后
from app.infrastructure.vector_store_client import VectorStoreClient
self.vector_store_client = VectorStoreClient()
results = await self.vector_store_client.search(...)
```

#### 3.3 更新依赖

```diff
# requirements.txt
- pymilvus==2.3.6
+ # pymilvus==2.3.6  # 已迁移到 vector-store-adapter
+ httpx==0.26.0  # 用于调用 vector-store-adapter
```

### 4. 更新配置

#### indexing-service

```yaml
# configs/app/indexing-service.yaml
vector_store:
  adapter_url: http://vector-store-adapter:8003
  backend: milvus
  collection_name: document_chunks
  timeout: 30.0
```

#### retrieval-service

```yaml
# configs/app/retrieval-service.yaml
vector_store:
  adapter_url: http://vector-store-adapter:8003
  backend: milvus
  collection_name: document_chunks
  timeout: 30.0
```

### 5. 更新 docker-compose

```yaml
services:
  indexing-service:
    environment:
      # 移除直接 Milvus 配置
      # - MILVUS_HOST=milvus
      # - MILVUS_PORT=19530

      # 添加适配服务配置
      - VECTOR_STORE_ADAPTER_URL=http://vector-store-adapter:8003
      - VECTOR_STORE_BACKEND=milvus
    depends_on:
      # 移除直接依赖
      # - milvus

      # 添加适配服务依赖
      - vector-store-adapter

  retrieval-service:
    environment:
      - VECTOR_STORE_ADAPTER_URL=http://vector-store-adapter:8003
      - VECTOR_STORE_BACKEND=milvus
    depends_on:
      - vector-store-adapter
```

## 代码变更对比

### indexing-service

#### document_processor.py

```diff
- from app.infrastructure.milvus_client import MilvusClient
+ from app.infrastructure.vector_store_client import VectorStoreClient

  class DocumentProcessor:
      def __init__(self):
-         self.milvus_client = MilvusClient()
+         self.vector_store_client = VectorStoreClient()

      async def _store_vectors(self, ...):
-         await self.milvus_client.insert_batch(data)
+         await self.vector_store_client.insert_batch(data)

      async def get_stats(self):
          return {
-             "milvus_count": await self.milvus_client.count(),
+             "vector_store_count": await self.vector_store_client.count(),
          }

      async def cleanup(self):
-         await self.milvus_client.close()
+         await self.vector_store_client.close()
```

### retrieval-service

#### vector_retriever.py

```diff
- from app.infrastructure.milvus_client import MilvusClient
+ from app.infrastructure.vector_store_client import VectorStoreClient

  class VectorRetriever:
      def __init__(self):
-         self.milvus_client = None
+         self.vector_store_client = None

      async def initialize(self):
-         self.milvus_client = MilvusClient()
+         self.vector_store_client = VectorStoreClient()

      async def retrieve(self, ...):
-         results = await self.milvus_client.search(...)
+         results = await self.vector_store_client.search(...)

      async def count(self):
-         return await self.milvus_client.count()
+         return await self.vector_store_client.count()

      async def cleanup(self):
-         await self.milvus_client.close()
+         await self.vector_store_client.close()
```

## 测试验证

### 1. 单元测试

```python
import pytest
from app.infrastructure.vector_store_client import VectorStoreClient

@pytest.mark.asyncio
async def test_vector_store_client():
    client = VectorStoreClient(
        base_url="http://localhost:8003",
        backend="milvus",
    )

    # 测试插入
    await client.insert_batch([{
        "chunk_id": "test_001",
        "document_id": "doc_001",
        "content": "test content",
        "embedding": [0.1] * 1024,
        "tenant_id": "test",
    }])

    # 测试检索
    results = await client.search(
        query_vector=[0.1] * 1024,
        top_k=10,
        tenant_id="test",
    )
    assert len(results) > 0

    # 测试数量
    count = await client.count()
    assert count > 0

    await client.close()
```

### 2. 集成测试

```bash
# 启动所有服务
docker-compose up -d

# 测试 indexing-service
curl -X POST http://localhost:8000/trigger?document_id=test_doc

# 测试 retrieval-service
curl -X POST http://localhost:8001/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 10}'
```

### 3. 性能测试

```bash
# 使用 k6 进行压力测试
k6 run tests/load/k6/vector-store-adapter.js
```

## 回滚计划

如果迁移出现问题，可以快速回滚：

### 1. 代码回滚

```bash
git revert <migration-commit>
```

### 2. 配置回滚

恢复直接调用 Milvus 的配置：

```yaml
environment:
  - MILVUS_HOST=milvus
  - MILVUS_PORT=19530
```

### 3. 服务回滚

```bash
# 停止适配服务
docker-compose stop vector-store-adapter

# 重启其他服务
docker-compose restart indexing-service retrieval-service
```

## 监控与观察

### 关键指标

1. **成功率**：`vector_operations_total{status="success"} / vector_operations_total`
2. **延迟**：`vector_operation_duration_seconds`
3. **错误率**：`vector_operations_total{status="error"} / vector_operations_total`

### Grafana 看板

创建监控看板，包含：

- 请求 QPS
- P50/P95/P99 延迟
- 错误率
- 后端健康状态

## 常见问题

### Q1: 迁移后性能下降？

**A**: 适配层会引入额外的网络开销（约 1-2ms），但通过以下方式可以优化：

- 使用连接池
- 批量操作
- 启用缓存

### Q2: 如何切换到 pgvector？

**A**: 只需修改配置：

```yaml
vector_store:
  backend: pgvector # 从 milvus 改为 pgvector
```

### Q3: 原有 Milvus 数据如何迁移？

**A**: 适配服务访问的是同一个 Milvus 实例，无需迁移数据。

### Q4: 如何支持多个 Milvus 实例？

**A**: 可以通过 collection_name 区分，或扩展 VectorStoreManager 支持多实例。

## 最佳实践

1. **渐进式迁移**：先迁移非关键服务，验证后再迁移核心服务
2. **保留回滚路径**：保持代码可快速回滚
3. **充分测试**：单元测试、集成测试、性能测试
4. **监控告警**：及时发现问题
5. **文档更新**：更新所有相关文档

## 时间线

- **Week 1**: 开发和测试适配服务
- **Week 2**: 迁移 indexing-service
- **Week 3**: 迁移 retrieval-service
- **Week 4**: 验证和优化

## 检查清单

- [ ] Vector Store Adapter 服务部署成功
- [ ] indexing-service 迁移完成
- [ ] retrieval-service 迁移完成
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 性能测试通过
- [ ] 监控配置完成
- [ ] 文档更新完成
- [ ] 团队培训完成
