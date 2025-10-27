# Knowledge Service - 知识库服务

## 概述

Knowledge Service 是 VoiceAssistant 平台的知识管理服务，负责知识库管理、文档处理、文本分块和向量化。

## 核心功能

### 1. 知识库管理

- **创建知识库**: 支持多种类型（通用、产品、FAQ、政策等）
- **配置管理**: 向量化模型、分块大小、重叠配置
- **状态管理**: 激活、停用、归档
- **统计信息**: 文档数量、分块数量、总大小

### 2. 文档管理

- **文档上传**: 支持多种格式（PDF、Word、Markdown、HTML、JSON）
- **文档处理**: 自动提取内容和分块
- **状态追踪**: pending → processing → completed/failed
- **元数据管理**: 自定义元数据存储

### 3. 文本分块

- **智能分块**: 基于配置的分块大小和重叠
- **内容哈希**: SHA-256 去重
- **Token 统计**: 估算 Token 数量
- **位置追踪**: 记录分块位置序号

### 4. 向量化管理

- **多模型支持**: OpenAI、Cohere、HuggingFace、本地模型
- **向量存储**: PostgreSQL FLOAT4 数组或 pgvector 扩展
- **状态追踪**: pending → completed/failed
- **批量处理**: 支持批量向量化

## 架构设计

### 分层架构 (DDD)

```
┌─────────────────────────────────────────┐
│          Service Layer                   │  gRPC/HTTP API
├─────────────────────────────────────────┤
│          Business Logic (Biz)            │  知识库、文档用例
├─────────────────────────────────────────┤
│          Domain Layer                    │  KnowledgeBase、Document、Chunk
├─────────────────────────────────────────┤
│          Data Layer                      │  GORM仓储实现
└─────────────────────────────────────────┘
```

### 核心领域模型

#### KnowledgeBase (知识库)

```go
type KnowledgeBase struct {
    ID             string
    Name           string
    Type           KnowledgeBaseType   // general/product/faq/policy/custom
    Status         KnowledgeBaseStatus // active/inactive/archived
    EmbeddingModel EmbeddingModel      // 向量化模型
    EmbeddingDim   int                 // 向量维度
    ChunkSize      int                 // 分块大小
    ChunkOverlap   int                 // 分块重叠
    DocumentCount  int                 // 文档数量
    ChunkCount     int                 // 分块数量
}
```

#### Document (文档)

```go
type Document struct {
    ID              string
    KnowledgeBaseID string
    Name            string
    FileType        DocumentType  // text/pdf/word/markdown/html/json
    FileSize        int64
    Content         string
    Status          DocumentStatus // pending/processing/completed/failed/deleted
    ChunkCount      int
}
```

#### Chunk (分块)

```go
type Chunk struct {
    ID              string
    DocumentID      string
    KnowledgeBaseID string
    Content         string
    ContentHash     string
    Position        int
    TokenCount      int
    Embedding       []float32
    EmbeddingStatus string // pending/completed/failed
}
```

## API 接口

### gRPC API

#### CreateKnowledgeBase - 创建知识库

```protobuf
rpc CreateKnowledgeBase(CreateKnowledgeBaseRequest) returns (KnowledgeBaseResponse);
```

#### GetKnowledgeBase - 获取知识库

```protobuf
rpc GetKnowledgeBase(GetKnowledgeBaseRequest) returns (KnowledgeBaseResponse);
```

#### ListKnowledgeBases - 列出知识库

```protobuf
rpc ListKnowledgeBases(ListKnowledgeBasesRequest) returns (ListKnowledgeBasesResponse);
```

#### UploadDocument - 上传文档

```protobuf
rpc UploadDocument(UploadDocumentRequest) returns (DocumentResponse);
```

#### ProcessDocument - 处理文档

```protobuf
rpc ProcessDocument(ProcessDocumentRequest) returns (DocumentResponse);
```

## 数据库设计

### knowledge_bases 表

| 字段            | 类型         | 说明         |
| --------------- | ------------ | ------------ |
| id              | VARCHAR(64)  | 知识库 ID    |
| name            | VARCHAR(255) | 知识库名称   |
| type            | VARCHAR(20)  | 类型         |
| status          | VARCHAR(20)  | 状态         |
| tenant_id       | VARCHAR(64)  | 租户 ID      |
| embedding_model | VARCHAR(50)  | 向量化模型   |
| embedding_dim   | INT          | 向量维度     |
| chunk_size      | INT          | 分块大小     |
| chunk_overlap   | INT          | 分块重叠     |
| settings        | JSONB        | 其他设置     |
| document_count  | INT          | 文档数量     |
| chunk_count     | INT          | 分块数量     |
| total_size      | BIGINT       | 总大小(字节) |

### documents 表

| 字段              | 类型         | 说明      |
| ----------------- | ------------ | --------- |
| id                | VARCHAR(64)  | 文档 ID   |
| knowledge_base_id | VARCHAR(64)  | 知识库 ID |
| name              | VARCHAR(255) | 文档名称  |
| file_name         | VARCHAR(255) | 文件名    |
| file_type         | VARCHAR(20)  | 文件类型  |
| file_size         | BIGINT       | 文件大小  |
| file_path         | VARCHAR(500) | 存储路径  |
| content           | TEXT         | 文档内容  |
| status            | VARCHAR(20)  | 状态      |
| chunk_count       | INT          | 分块数量  |
| metadata          | JSONB        | 元数据    |

### chunks 表

| 字段              | 类型        | 说明                    |
| ----------------- | ----------- | ----------------------- |
| id                | VARCHAR(64) | 分块 ID                 |
| document_id       | VARCHAR(64) | 文档 ID                 |
| knowledge_base_id | VARCHAR(64) | 知识库 ID               |
| content           | TEXT        | 分块内容                |
| content_hash      | VARCHAR(64) | 内容哈希                |
| position          | INT         | 位置序号                |
| token_count       | INT         | Token 数量              |
| char_count        | INT         | 字符数量                |
| metadata          | JSONB       | 元数据                  |
| embedding         | FLOAT4[]    | 向量（PostgreSQL 数组） |
| embedding_status  | VARCHAR(20) | 向量化状态              |

### 索引策略

- **知识库**: tenant_id, status, type, created_at
- **文档**: knowledge_base_id, status, tenant_id, (kb_id + status)
- **分块**: document_id, knowledge_base_id, content_hash, embedding_status, (doc_id + position)

## 配置

### 配置文件 (`configs/app/knowledge-service.yaml`)

```yaml
server:
  http:
    addr: 0.0.0.0:8000
    timeout: 30s
  grpc:
    addr: 0.0.0.0:9000
    timeout: 30s

data:
  database:
    driver: postgres
    source: postgres://voiceassistant:voiceassistant_dev@localhost:5432/voiceassistant?sslmode=disable

trace:
  endpoint: http://localhost:4318
```

## 运行指南

### 本地开发

1. **安装依赖**

```bash
make init
```

2. **运行数据库迁移**

```bash
psql -U voiceassistant -d voiceassistant -f migrations/postgres/003_knowledge.sql
```

3. **生成 Wire 代码**

```bash
make wire
```

4. **运行服务**

```bash
make run
```

### Docker 运行

```bash
make docker-build
make docker-run
```

## 使用示例

### 1. 创建知识库

```go
kb, err := client.CreateKnowledgeBase(ctx, &CreateKnowledgeBaseRequest{
    Name: "产品知识库",
    Description: "产品相关文档和FAQ",
    Type: "product",
    TenantID: "tenant_123",
    CreatedBy: "user_456",
    EmbeddingModel: "openai",
})
```

### 2. 上传文档

```go
doc, err := client.UploadDocument(ctx, &UploadDocumentRequest{
    KnowledgeBaseID: kb.ID,
    Name: "产品手册",
    FileName: "manual.pdf",
    FileType: "pdf",
    FileSize: 1024000,
    FilePath: "/uploads/manual.pdf",
    TenantID: "tenant_123",
    UploadedBy: "user_456",
})
```

### 3. 处理文档

```go
// 提取文档内容（实际应该通过文件解析器）
content := extractContent(doc.FilePath)

// 处理文档（分块）
doc, err = client.ProcessDocument(ctx, &ProcessDocumentRequest{
    ID: doc.ID,
    Content: content,
})
```

## 监控指标

### 业务指标

- `knowledge_knowledge_bases_total`: 知识库总数
- `knowledge_documents_total`: 文档总数
- `knowledge_chunks_total`: 分块总数
- `knowledge_document_process_duration_seconds`: 文档处理时长
- `knowledge_chunk_duration_seconds`: 分块处理时长

### 技术指标

- `knowledge_grpc_requests_total`: gRPC 请求数
- `knowledge_db_query_duration_seconds`: 数据库查询延迟

## 集成服务

### 上游服务

- **File Storage**: 文件上传和存储
- **Document Parser**: 文档内容提取

### 下游服务

- **Indexing Service**: 向量化和索引
- **Retrieval Service**: 文档检索

## 性能优化

### 1. 批量处理

- 批量创建分块（100 条/批）
- 批量向量化

### 2. 数据库优化

- JSONB 索引
- 复合索引
- 向量索引（pgvector HNSW/IVFFlat）

### 3. 分块策略

- 智能分块（按段落、句子）
- 语义分块
- 滑动窗口

## 向量化扩展

### pgvector 扩展

如果使用 pgvector，可以获得更好的向量搜索性能：

```sql
-- 安装扩展
CREATE EXTENSION vector;

-- 修改表结构
ALTER TABLE knowledge.chunks
ADD COLUMN embedding_vector vector(1536);

-- 创建HNSW索引（推荐）
CREATE INDEX idx_chunks_embedding_hnsw
ON knowledge.chunks
USING hnsw (embedding_vector vector_cosine_ops);

-- 或IVFFlat索引
CREATE INDEX idx_chunks_embedding_ivfflat
ON knowledge.chunks
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);
```

## 最佳实践

### 1. 分块配置

- **短文档** (< 500 字符): chunk_size=200, overlap=20
- **中文档** (500-2000 字符): chunk_size=500, overlap=50
- **长文档** (> 2000 字符): chunk_size=1000, overlap=100

### 2. 向量模型选择

- **OpenAI ada-002**: 1536 维，性能优秀，成本较高
- **Cohere**: 768 维，多语言支持好
- **本地模型**: 768 维，无 API 成本，需自行部署

### 3. 文档处理流程

1. 上传文档 → status=pending
2. 提取内容 → status=processing
3. 文本分块 → 创建 chunks
4. 向量化 → 调用 Indexing Service
5. 完成 → status=completed

## 故障排查

### 常见问题

1. **文档处理失败**

   - 检查文件格式
   - 检查内容提取
   - 查看 error_message 字段

2. **分块数量异常**

   - 检查 chunk_size 配置
   - 检查文档内容长度
   - 验证分块逻辑

3. **向量化延迟**
   - 检查 Indexing Service 状态
   - 查看 pending chunks 数量
   - 监控 API 限流

## 开发团队

- **Maintainer**: VoiceAssistant Team
- **Created**: 2025-10-26
- **Version**: v1.0.0

## 相关文档

- [架构设计](../../docs/arch/knowledge-service.md)
- [API 文档](../../docs/api/knowledge.md)
- [分块策略](../../docs/guides/chunking-strategy.md)
