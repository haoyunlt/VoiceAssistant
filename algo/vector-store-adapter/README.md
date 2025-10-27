# Vector Store Adapter Service

向量库适配服务 - 提供统一的向量数据库访问接口。

## 功能特性

- **多后端支持**：Milvus、pgvector（可扩展）
- **统一 API**：屏蔽不同向量数据库的差异
- **高性能**：异步 I/O，连接池管理
- **可观测性**：Prometheus 指标，健康检查
- **租户隔离**：支持多租户数据隔离

## 支持的向量数据库

### 1. Milvus

- 专业的向量数据库
- 支持 HNSW 索引
- 高性能向量检索

### 2. pgvector

- PostgreSQL 插件
- 统一数据管理
- 适合中小规模

## API 接口

### 插入向量

```bash
POST /collections/{collection_name}/insert
{
  "backend": "milvus",
  "data": [
    {
      "chunk_id": "chunk_001",
      "document_id": "doc_001",
      "content": "文本内容",
      "embedding": [0.1, 0.2, ...],
      "tenant_id": "tenant_123"
    }
  ]
}
```

### 检索向量

```bash
POST /collections/{collection_name}/search
{
  "backend": "milvus",
  "query_vector": [0.1, 0.2, ...],
  "top_k": 10,
  "tenant_id": "tenant_123"
}
```

### 删除向量

```bash
DELETE /collections/{collection_name}/documents/{document_id}?backend=milvus
```

### 获取数量

```bash
GET /collections/{collection_name}/count?backend=milvus
```

## 配置

### 环境变量

#### Milvus

- `MILVUS_HOST`: Milvus 主机（默认：localhost）
- `MILVUS_PORT`: Milvus 端口（默认：19530）
- `MILVUS_USER`: Milvus 用户（可选）
- `MILVUS_PASSWORD`: Milvus 密码（可选）

#### pgvector

- `PGVECTOR_HOST`: PostgreSQL 主机（默认：localhost）
- `PGVECTOR_PORT`: PostgreSQL 端口（默认：5432）
- `PGVECTOR_DATABASE`: 数据库名称（默认：voiceassistant）
- `PGVECTOR_USER`: PostgreSQL 用户（默认：postgres）
- `PGVECTOR_PASSWORD`: PostgreSQL 密码

#### 通用

- `DEFAULT_BACKEND`: 默认后端（milvus/pgvector，默认：milvus）
- `VECTOR_DIMENSION`: 向量维度（默认：1024）

## 部署

### Docker 部署

```bash
# 构建镜像
make docker-build

# 运行容器
docker run -d \
  --name vector-store-adapter \
  -p 8003:8003 \
  -e MILVUS_HOST=milvus \
  -e PGVECTOR_HOST=postgres \
  vector-store-adapter:latest
```

### Kubernetes 部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vector-store-adapter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vector-store-adapter
  template:
    metadata:
      labels:
        app: vector-store-adapter
    spec:
      containers:
        - name: vector-store-adapter
          image: vector-store-adapter:latest
          ports:
            - containerPort: 8003
          env:
            - name: MILVUS_HOST
              value: 'milvus-service'
            - name: PGVECTOR_HOST
              value: 'postgres-service'
```

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│           Vector Store Adapter Service                   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │        VectorStoreManager                        │   │
│  │  ┌──────────────┐      ┌──────────────┐        │   │
│  │  │   Milvus     │      │  pgvector    │        │   │
│  │  │   Backend    │      │   Backend    │        │   │
│  │  └──────────────┘      └──────────────┘        │   │
│  └─────────────────────────────────────────────────┘   │
│                        ▲                                 │
│                        │                                 │
│              FastAPI REST API                            │
└────────────────────────┼────────────────────────────────┘
                         │
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
  indexing-service  retrieval-service  其他服务
```

## 性能指标

- **插入延迟**：< 50ms (批量 100 条)
- **检索延迟**：< 20ms (Top 10)
- **并发能力**：≥ 500 RPS

## 监控指标

访问 `/metrics` 端点查看 Prometheus 指标：

- `vector_operations_total`: 操作总数
- `vector_operation_duration_seconds`: 操作延迟

## 健康检查

- `/health`: 基础健康检查
- `/ready`: 就绪检查（包含后端状态）

## 开发

```bash
# 安装依赖
make install

# 开发模式运行
make dev

# 运行测试
make test
```

## License

MIT
