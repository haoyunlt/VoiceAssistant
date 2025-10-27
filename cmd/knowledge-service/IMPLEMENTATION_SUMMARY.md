# Knowledge Service 实现总结

## 项目概述

**服务名称**: Knowledge Service (知识库服务)
**框架**: Kratos v2.7+ (Go)
**架构模式**: DDD (领域驱动设计)
**实现日期**: 2025-10-26

## 核心职责

Knowledge Service 是 VoiceAssistant 平台的**知识管理服务**，负责：

1. **知识库管理**: 创建、配置、状态管理知识库
2. **文档管理**: 上传、处理、删除文档
3. **文本分块**: 智能分块、Token 统计、内容哈希
4. **向量化管理**: 支持多种向量化模型，批量处理
5. **元数据管理**: 灵活的 JSONB 元数据存储

## 实现架构

### 分层结构 (DDD)

```
cmd/knowledge-service/
├── internal/
│   ├── domain/              # 领域层
│   │   ├── knowledge_base.go   # KnowledgeBase聚合根
│   │   ├── document.go         # Document聚合根
│   │   ├── chunk.go            # Chunk实体
│   │   ├── errors.go           # 领域错误定义
│   │   └── repository.go       # 仓储接口
│   ├── biz/                 # 业务逻辑层
│   │   ├── knowledge_base_usecase.go  # 知识库用例
│   │   └── document_usecase.go        # 文档用例
│   ├── data/                # 数据访问层
│   │   ├── data.go                 # Data初始化
│   │   ├── db.go                   # 数据库连接
│   │   ├── knowledge_base_repo.go  # 知识库仓储
│   │   ├── document_repo.go        # 文档仓储
│   │   └── chunk_repo.go           # 分块仓储
│   ├── service/             # 服务层
│   │   └── knowledge_service.go    # gRPC服务实现
│   └── server/              # 服务器配置
│       ├── grpc.go         # gRPC服务器
│       └── http.go         # HTTP服务器
├── wire.go                  # Wire依赖注入
├── main_app.go             # 主程序入口
├── Makefile                # 构建脚本
└── README.md               # 服务文档
```

## 核心领域模型

### 1. KnowledgeBase (知识库聚合根)

**文件**: `internal/domain/knowledge_base.go`

```go
type KnowledgeBase struct {
    ID             string
    Name           string
    Description    string
    Type           KnowledgeBaseType   // general/product/faq/policy/custom
    Status         KnowledgeBaseStatus // active/inactive/archived
    TenantID       string
    CreatedBy      string
    EmbeddingModel EmbeddingModel      // openai/cohere/huggingface/local
    EmbeddingDim   int                 // 向量维度: 768/1536等
    ChunkSize      int                 // 分块大小: 默认500
    ChunkOverlap   int                 // 分块重叠: 默认50
    Settings       map[string]interface{}
    DocumentCount  int                 // 文档数量
    ChunkCount     int                 // 分块数量
    TotalSize      int64               // 总大小(字节)
    LastIndexedAt  *time.Time          // 最后索引时间
    CreatedAt      time.Time
    UpdatedAt      time.Time
}
```

**知识库类型**:

- `general`: 通用知识库
- `product`: 产品知识库
- `faq`: FAQ 知识库
- `policy`: 政策知识库
- `custom`: 自定义知识库

**核心方法**:

- `NewKnowledgeBase()`: 创建新知识库，自动配置向量维度
- `Update()`: 更新名称和描述
- `UpdateSettings()`: 更新自定义设置
- `SetChunkConfig()`: 设置分块配置（验证参数）
- `Activate()` / `Deactivate()` / `Archive()`: 状态管理
- `IncrementDocumentCount()`: 文档数量统计
- `IncrementChunkCount()`: 分块数量统计
- `AddSize()`: 大小统计
- `IsActive()` / `CanModify()`: 状态检查

### 2. Document (文档聚合根)

**文件**: `internal/domain/document.go`

```go
type Document struct {
    ID              string
    KnowledgeBaseID string
    Name            string
    FileName        string
    FileType        DocumentType    // text/pdf/word/markdown/html/json
    FileSize        int64
    FilePath        string          // 存储路径
    FileURL         string          // 访问URL
    Content         string          // 文档内容
    Summary         string          // 文档摘要
    Status          DocumentStatus  // pending/processing/completed/failed/deleted
    ChunkCount      int
    TenantID        string
    UploadedBy      string
    Metadata        map[string]interface{}
    ErrorMessage    string          // 错误信息
    ProcessedAt     *time.Time
    CreatedAt       time.Time
    UpdatedAt       time.Time
}
```

**文档状态流转**:

```
pending → processing → completed
                    ↓
                  failed
```

**核心方法**:

- `NewDocument()`: 创建新文档（初始状态 pending）
- `SetContent()`: 设置文档内容
- `StartProcessing()`: 开始处理（status → processing）
- `CompleteProcessing()`: 完成处理（status → completed）
- `FailProcessing()`: 处理失败（status → failed）
- `MarkDeleted()`: 标记删除（status → deleted）
- `CanProcess()`: 检查是否可以处理

### 3. Chunk (文档分块)

**文件**: `internal/domain/chunk.go`

```go
type Chunk struct {
    ID              string
    DocumentID      string
    KnowledgeBaseID string
    Content         string          // 分块内容
    ContentHash     string          // SHA-256内容哈希
    Position        int             // 位置序号
    TokenCount      int             // Token数量（估算）
    CharCount       int             // 字符数量
    Metadata        map[string]interface{}
    Embedding       []float32       // 向量（1536维等）
    EmbeddingStatus string          // pending/completed/failed
    TenantID        string
    CreatedAt       time.Time
    UpdatedAt       time.Time
}
```

**核心方法**:

- `NewChunk()`: 创建新分块，自动计算 Token 和字符数
- `SetContentHash()`: 设置内容哈希
- `SetEmbedding()`: 设置向量（status → completed）
- `FailEmbedding()`: 向量化失败（status → failed）
- `AddMetadata()`: 添加元数据
- `HasEmbedding()` / `IsEmbeddingPending()`: 状态检查

## 业务逻辑层

### KnowledgeBaseUsecase (知识库用例)

**文件**: `internal/biz/knowledge_base_usecase.go`

**核心方法**:

1. **CreateKnowledgeBase**: 创建知识库

   - 根据 embedding_model 自动设置向量维度
   - 验证必填字段
   - 持久化到数据库

2. **GetKnowledgeBase**: 获取知识库详情

3. **UpdateKnowledgeBase**: 更新知识库信息

   - 检查是否已归档（不可修改）

4. **DeleteKnowledgeBase**: 删除知识库

   - 检查是否有文档（有文档不可删除）

5. **ListKnowledgeBases**: 列出租户的知识库

   - 分页查询

6. **ActivateKnowledgeBase** / **DeactivateKnowledgeBase**: 状态管理

7. **UpdateChunkConfig**: 更新分块配置

   - 验证 chunk_size (100-2000)
   - 验证 chunk_overlap (0 - chunk_size)

8. **UpdateSettings**: 更新自定义设置

### DocumentUsecase (文档用例)

**文件**: `internal/biz/document_usecase.go`

**核心方法**:

1. **UploadDocument**: 上传文档

   - 检查知识库是否激活
   - 创建文档记录（status=pending）
   - 更新知识库统计（文档数+1，大小累加）

2. **GetDocument**: 获取文档详情

3. **UpdateDocument**: 更新文档信息

4. **DeleteDocument**: 删除文档

   - 删除所有分块
   - 标记文档为 deleted
   - 更新知识库统计

5. **ListDocuments**: 列出知识库的文档

   - 排除已删除文档

6. **ProcessDocument**: 处理文档（核心流程）

   ```
   开始处理（status=processing）
    ↓
   设置文档内容
    ↓
   获取知识库配置（chunk_size, chunk_overlap）
    ↓
   调用 chunkDocument() 分块
    ↓
   批量保存分块
    ↓
   完成处理（status=completed）
    ↓
   更新知识库统计
   ```

7. **chunkDocument**: 分块算法（内部方法）

   - 固定大小分块 + 滑动窗口
   - 计算内容哈希（SHA-256）
   - 估算 Token 数量
   - 添加元数据（document_name, file_type）

8. **GetDocumentChunks**: 获取文档的分块列表

9. **ReprocessDocument**: 重新处理文档
   - 删除旧分块
   - 重新分块

## 数据访问层

### KnowledgeBaseRepository (知识库仓储)

**文件**: `internal/data/knowledge_base_repo.go`

**持久化对象**:

```go
type KnowledgeBasePO struct {
    ID             string `gorm:"primaryKey"`
    Name           string `gorm:"index:idx_name"`
    Type           string `gorm:"index:idx_type"`
    Status         string `gorm:"index:idx_status"`
    TenantID       string `gorm:"index:idx_tenant"`
    Settings       string `gorm:"type:jsonb"`  // JSONB存储
    // ... 其他字段
}
```

**实现方法**:

- `Create()`: 创建知识库
- `GetByID()`: 根据 ID 查询
- `Update()`: 更新知识库
- `Delete()`: 删除知识库
- `ListByTenant()`: 租户知识库列表（分页）
- `ListByStatus()`: 按状态查询

### DocumentRepository (文档仓储)

**文件**: `internal/data/document_repo.go`

**持久化对象**:

```go
type DocumentPO struct {
    ID              string `gorm:"primaryKey"`
    KnowledgeBaseID string `gorm:"index:idx_knowledge_base"`
    Status          string `gorm:"index:idx_status"`
    TenantID        string `gorm:"index:idx_tenant"`
    Metadata        string `gorm:"type:jsonb"`
    // ... 其他字段
}
```

**实现方法**:

- `Create()`: 创建文档
- `GetByID()`: 根据 ID 查询
- `Update()`: 更新文档
- `Delete()`: 删除文档
- `ListByKnowledgeBase()`: 知识库文档列表（排除 deleted）
- `ListByStatus()`: 按状态查询
- `CountByKnowledgeBase()`: 统计文档数量

### ChunkRepository (分块仓储)

**文件**: `internal/data/chunk_repo.go`

**持久化对象**:

```go
type ChunkPO struct {
    ID              string `gorm:"primaryKey"`
    DocumentID      string `gorm:"index:idx_document"`
    KnowledgeBaseID string `gorm:"index:idx_knowledge_base"`
    ContentHash     string `gorm:"index:idx_content_hash"`
    Metadata        string `gorm:"type:jsonb"`
    Embedding       pq.Float32Array `gorm:"type:float4[]"` // PostgreSQL数组
    EmbeddingStatus string `gorm:"index:idx_embedding_status"`
    // ... 其他字段
}
```

**向量存储**:

- 使用 PostgreSQL `FLOAT4[]`数组类型
- 支持 pgvector 扩展（vector 类型）
- 使用`lib/pq`的`Float32Array`类型

**实现方法**:

- `Create()`: 创建单个分块
- `BatchCreate()`: 批量创建分块（100 条/批）
- `GetByID()`: 根据 ID 查询
- `Update()`: 更新分块
- `Delete()`: 删除分块
- `ListByDocument()`: 文档分块列表（按 position 排序）
- `ListByKnowledgeBase()`: 知识库分块列表
- `DeleteByDocument()`: 删除文档所有分块
- `CountByDocument()`: 统计文档分块数
- `CountByKnowledgeBase()`: 统计知识库分块数
- `ListPendingEmbedding()`: 获取待向量化分块

## 服务层

### KnowledgeService

**文件**: `internal/service/knowledge_service.go`

**gRPC 接口实现** (临时定义，待 proto 生成):

1. **CreateKnowledgeBase**: 创建知识库
2. **GetKnowledgeBase**: 获取知识库
3. **ListKnowledgeBases**: 列出知识库
4. **UploadDocument**: 上传文档
5. **GetDocument**: 获取文档
6. **ProcessDocument**: 处理文档
7. **DeleteDocument**: 删除文档

## 数据库设计

### 表结构

#### knowledge_bases 表

| 字段            | 类型         | 说明       | 索引       |
| --------------- | ------------ | ---------- | ---------- |
| id              | VARCHAR(64)  | 知识库 ID  | PK         |
| name            | VARCHAR(255) | 名称       | idx_name   |
| type            | VARCHAR(20)  | 类型       | idx_type   |
| status          | VARCHAR(20)  | 状态       | idx_status |
| tenant_id       | VARCHAR(64)  | 租户 ID    | idx_tenant |
| embedding_model | VARCHAR(50)  | 向量化模型 | -          |
| embedding_dim   | INT          | 向量维度   | -          |
| chunk_size      | INT          | 分块大小   | -          |
| chunk_overlap   | INT          | 分块重叠   | -          |
| settings        | JSONB        | 其他设置   | -          |
| document_count  | INT          | 文档数量   | -          |
| chunk_count     | INT          | 分块数量   | -          |
| total_size      | BIGINT       | 总大小     | -          |

#### documents 表

| 字段              | 类型        | 说明      | 索引               |
| ----------------- | ----------- | --------- | ------------------ |
| id                | VARCHAR(64) | 文档 ID   | PK                 |
| knowledge_base_id | VARCHAR(64) | 知识库 ID | idx_knowledge_base |
| status            | VARCHAR(20) | 状态      | idx_status         |
| tenant_id         | VARCHAR(64) | 租户 ID   | idx_tenant         |
| content           | TEXT        | 文档内容  | -                  |
| metadata          | JSONB       | 元数据    | -                  |
| ...               | ...         | ...       | ...                |

**复合索引**: `(knowledge_base_id, status)`

#### chunks 表

| 字段              | 类型        | 说明       | 索引                 |
| ----------------- | ----------- | ---------- | -------------------- |
| id                | VARCHAR(64) | 分块 ID    | PK                   |
| document_id       | VARCHAR(64) | 文档 ID    | idx_document         |
| knowledge_base_id | VARCHAR(64) | 知识库 ID  | idx_knowledge_base   |
| content_hash      | VARCHAR(64) | 内容哈希   | idx_content_hash     |
| embedding         | FLOAT4[]    | 向量       | -                    |
| embedding_status  | VARCHAR(20) | 向量化状态 | idx_embedding_status |
| ...               | ...         | ...        | ...                  |

**复合索引**: `(document_id, position)`

**向量索引** (如果使用 pgvector):

- HNSW 索引（推荐）：高性能，适合大规模
- IVFFlat 索引：适合中等规模

### 外键关系

```
knowledge_bases (1) ──→ (*) documents
knowledge_bases (1) ──→ (*) chunks
documents (1) ──→ (*) chunks
```

**级联删除**:

- 删除知识库 → 删除所有文档和分块
- 删除文档 → 删除所有分块

## 依赖注入 (Wire)

**文件**: `wire.go`

```go
panic(wire.Build(
    // Data layer
    data.NewDB,
    data.NewData,
    data.NewKnowledgeBaseRepo,
    data.NewDocumentRepo,
    data.NewChunkRepo,

    // Business logic layer
    biz.NewKnowledgeBaseUsecase,
    biz.NewDocumentUsecase,

    // Service layer
    service.NewKnowledgeService,

    // Server layer
    server.NewGRPCServer,
    server.NewHTTPServer,

    // App
    newApp,
))
```

**依赖关系图**:

```
App
 ├── gRPC Server
 │   └── KnowledgeService
 │       ├── KnowledgeBaseUsecase
 │       │   ├── KnowledgeBaseRepository (Data)
 │       │   └── DocumentRepository (Data)
 │       └── DocumentUsecase
 │           ├── DocumentRepository (Data)
 │           ├── ChunkRepository (Data)
 │           └── KnowledgeBaseRepository (Data)
 └── HTTP Server
```

## 核心流程示例

### 文档处理完整流程

```
1. 用户上传文档
   UploadDocument(kb_id, name, file_info)
   ↓
   创建Document(status=pending)
   更新KnowledgeBase统计(doc_count+1, size+file_size)

2. 异步处理文档
   ProcessDocument(doc_id, content)
   ↓
   Document.StartProcessing() → status=processing
   ↓
   获取KnowledgeBase配置(chunk_size=500, overlap=50)
   ↓
   chunkDocument():
     - 固定大小分块 + 滑动窗口
     - 计算content_hash (SHA-256)
     - 估算token_count
     - 设置metadata
   ↓
   BatchCreate(chunks) → 批量插入100条/批
   ↓
   Document.CompleteProcessing() → status=completed
   更新KnowledgeBase统计(chunk_count+N)

3. 向量化（后台任务）
   ListPendingEmbedding(limit=100)
   ↓
   调用Indexing Service生成向量
   ↓
   Chunk.SetEmbedding(embedding) → status=completed
```

## 性能指标

### 预期性能

| 指标       | 目标值         |
| ---------- | -------------- |
| 知识库创建 | < 10ms         |
| 文档上传   | < 50ms         |
| 分块处理   | < 1s/1000 字符 |
| 批量插入   | < 100ms/100 条 |
| 文档查询   | < 10ms         |

### 优化措施

1. **批量操作**:

   - 批量创建分块：100 条/批
   - 批量向量化

2. **数据库优化**:

   - JSONB 索引加速元数据查询
   - 复合索引优化常用查询
   - 连接池: MaxOpen=100

3. **分块算法**:
   - 固定大小分块（简单高效）
   - 未来可扩展：语义分块、段落分块

## 监控指标

### 业务指标

```prometheus
# 知识库总数
knowledge_knowledge_bases_total{tenant_id="xxx",status="active"}

# 文档总数
knowledge_documents_total{tenant_id="xxx",status="completed"}

# 分块总数
knowledge_chunks_total{tenant_id="xxx",embedding_status="completed"}

# 文档处理时长
knowledge_document_process_duration_seconds{p="0.95"}

# 分块处理时长
knowledge_chunk_duration_seconds{p="0.95"}
```

### 技术指标

```prometheus
# gRPC请求
knowledge_grpc_requests_total{method="UploadDocument"}

# 数据库查询
knowledge_db_query_duration_seconds{operation="batch_create"}
```

## 集成服务

### 上游服务

- **File Storage**: 文件上传和存储
- **Document Parser**: PDF/Word 等文件内容提取

### 下游服务

- **Indexing Service**: 向量化处理
- **Retrieval Service**: 文档检索

### 基础设施

- PostgreSQL: 主数据存储
- MinIO/S3: 文件存储
- OpenTelemetry Collector: 可观测性

## 待完成工作

### 1. Proto 定义 🔴

```protobuf
// api/proto/knowledge/v1/knowledge.proto
service Knowledge {
    rpc CreateKnowledgeBase(CreateKnowledgeBaseRequest) returns (KnowledgeBaseResponse);
    rpc GetKnowledgeBase(GetKnowledgeBaseRequest) returns (KnowledgeBaseResponse);
    rpc ListKnowledgeBases(ListKnowledgeBasesRequest) returns (ListKnowledgeBasesResponse);
    rpc UploadDocument(UploadDocumentRequest) returns (DocumentResponse);
    rpc ProcessDocument(ProcessDocumentRequest) returns (DocumentResponse);
    rpc DeleteDocument(DeleteDocumentRequest) returns (Empty);
}
```

### 2. 文件解析器集成 🟡

- PDF 解析: PyPDF2, pdfplumber
- Word 解析: python-docx
- HTML 解析: BeautifulSoup

### 3. 智能分块 🟡

- 段落分块
- 句子分块
- 语义分块（基于 embedding）

### 4. pgvector 扩展 🟡

```sql
CREATE EXTENSION vector;
ALTER TABLE knowledge.chunks ADD COLUMN embedding_vector vector(1536);
CREATE INDEX ON knowledge.chunks USING hnsw (embedding_vector vector_cosine_ops);
```

### 5. 向量化集成 🟡

- 集成 Indexing Service
- 批量向量化任务
- 重试机制

### 6. 文档摘要 🟡

- 调用 LLM 生成文档摘要
- 自动提取关键词

## 关键技术点

### 1. JSONB 存储

- 灵活存储自定义设置和元数据
- 支持索引和查询
- 适合动态 schema

### 2. PostgreSQL 数组

- `FLOAT4[]`存储向量
- 原生支持，无需扩展
- 可升级到 pgvector

### 3. 批量操作

- GORM `CreateInBatches()`
- 减少数据库 roundtrip
- 提升插入性能

### 4. 分块算法

- 固定大小 + 滑动窗口
- 可配置 chunk_size 和 overlap
- 未来可扩展更智能的算法

### 5. 内容哈希

- SHA-256 去重
- 避免重复处理
- 支持增量更新

## 总结

Knowledge Service 是 VoiceAssistant 平台的**知识管理核心**，通过 DDD 分层架构实现了：

✅ **完整的知识库管理**: 创建、配置、状态管理
✅ **灵活的文档处理**: 多格式支持、状态追踪
✅ **高效的文本分块**: 可配置分块策略
✅ **向量化支持**: 多模型、批量处理
✅ **可扩展架构**: JSONB 元数据、数组存储
✅ **性能优化**: 批量操作、索引优化

**下一步**:

1. 完成 Proto 定义
2. 集成文件解析器
3. 实现智能分块
4. 集成向量化服务
5. 添加 pgvector 支持

---

**版本**: v1.0.0
**作者**: VoiceAssistant Team
**日期**: 2025-10-26
