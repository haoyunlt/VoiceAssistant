# VoiceHelper 服务完成度审查报告

> **审查日期**: 2025-10-26
> **源项目版本**: v0.9.2 (main 分支)
> **源项目地址**: https://github.com/haoyunlt/voicehelper > **当前项目版本**: v2.0.0 (开发中)
> **总体完成度**: 约 25%

---

## 📊 服务完成度总览

| 服务                                           | 源项目状态 | 当前项目状态          | 完成度 | 优先级 |
| ---------------------------------------------- | ---------- | --------------------- | ------ | ------ |
| **Backend Gateway**                            | ✅ 完整    | ⏳ 部分 (APISIX 配置) | 40%    | 🔥 P0  |
| **Auth Service** → **Identity Service**        | ✅ 完整    | ✅ 基本完成           | 80%    | ⭐ P1  |
| **Session Service** → **Conversation Service** | ✅ 完整    | ✅ 基本完成           | 75%    | ⭐ P1  |
| **Document Service** → **Knowledge Service**   | ✅ 完整    | 🚧 进行中             | 30%    | 🔥 P0  |
| **GraphRAG Service** → **3 个服务**            | ✅ 完整    | ❌ 未开始             | 5%     | 🔥 P0  |
| **Agent Service** → **Agent Engine**           | ✅ 完整    | ❌ 框架               | 15%    | 🔥 P0  |
| **Voice Service** → **Voice Engine**           | ✅ 完整    | ❌ 框架               | 10%    | ⭐ P1  |
| **LLM Router** → **2 个服务**                  | ✅ 完整    | ❌ 框架               | 10%    | 🔥 P0  |
| **Multimodal Service** → **Multimodal Engine** | ✅ 完整    | ❌ 框架               | 10%    | ⭐ P1  |
| **Notification Service**                       | ✅ 完整    | ❌ 框架               | 10%    | ⭐ P1  |
| **AI Orchestrator**                            | ❌ 新增    | ❌ 框架               | 5%     | 🔥 P0  |
| **Analytics Service**                          | ❌ 新增    | ❌ 框架               | 5%     | ⭐ P1  |

---

## 🔍 服务详细审查

### 1. Backend Gateway → APISIX (40%)

#### 源项目功能 (backend/gateway/)

```go
✅ 完整实现的功能：
- Gin 框架路由
- 中间件链 (CORS, 日志, 恢复, 限流, Consul健康检查)
- JWT 认证中间件
- 请求/响应日志
- Prometheus 指标
- WebSocket 代理
- gRPC 反向代理
- 动态服务发现 (Consul)
- 分布式限流 (Redis)
- API 版本管理
- 请求追踪 (Trace ID)
```

#### 当前项目状态

```yaml
✅ 已完成:
  - docker-compose.yml 中 APISIX 配置
  - configs/gateway/apisix.yaml 基础配置

❌ 缺失:
  - 完整的路由配置 (14个服务的路由)
  - JWT 认证插件配置
  - 限流插件配置
  - Consul 服务发现集成
  - WebSocket 代理配置
  - gRPC 转码配置
  - 灰度发布配置
  - 监控指标配置
```

#### 📋 TODO 清单

**🔥 P0 - 阻塞开发**:

- [ ] **完整路由配置** (2 天)

  ```yaml
  # configs/gateway/apisix-routes.yaml
  routes:
    - id: identity-service
      uri: /api/v1/identity/*
      upstream: identity-service:9000
      plugins: [jwt-auth, limit-req, prometheus]
    - id: conversation-service
      uri: /api/v1/conversation/*
      ...
    # 14个服务的完整路由
  ```

- [ ] **JWT 认证插件** (1 天)

  ```yaml
  plugins:
    jwt-auth:
      header: Authorization
      secret: ${VAULT:secret/jwt#secret}
      claim_specs:
        - claim: user_id
        - claim: tenant_id
  ```

- [ ] **限流插件配置** (1 天)
  ```yaml
  plugins:
    limit-req:
      rate: 100 # 每秒100请求
      burst: 50
      key: $remote_addr
      rejected_code: 429
  ```

**⭐ P1 - 短期完成**:

- [ ] **Consul 服务发现** (2 天)

  - 集成 APISIX Discovery 插件
  - 自动服务注册/注销
  - 健康检查配置

- [ ] **WebSocket 代理** (1 天)

  ```yaml
  routes:
    - uri: /ws/*
      plugins:
        websocket: {}
      upstream: conversation-service:8080
  ```

- [ ] **gRPC 转码** (2 天)

  ```yaml
  plugins:
    grpc-transcode:
      proto_id: identity_v1
      service: identity.v1.IdentityService
      method: Login
  ```

- [ ] **监控配置** (1 天)
  ```yaml
  plugins:
    prometheus:
      prefer_name: true
    opentelemetry:
      sampler: always_on
  ```

**💡 P2 - 优化增强**:

- [ ] **灰度发布** (2 天)

  ```yaml
  plugins:
    traffic-split:
      rules:
        - weighted_upstreams:
            - weight: 90 # v1
            - weight: 10 # v2 (canary)
  ```

- [ ] **熔断器** (1 天)
  ```yaml
  plugins:
    api-breaker:
      break_response_code: 503
      unhealthy:
        http_statuses: [500, 502, 503]
        failures: 3
  ```

**预计工时**: P0: 4 天, P1: 6 天, P2: 3 天, **总计: 13 天**

---

### 2. Auth Service → Identity Service (80%)

#### 源项目功能 (backend/auth-service/)

```python
✅ 完整实现的功能：
- 用户注册/登录/登出
- JWT Token 签发 (访问令牌 + 刷新令牌)
- Token 验证和续期
- 密码加密 (bcrypt)
- 用户信息管理
- Redis Token 缓存
- Consul 服务注册
- Prometheus 指标
- 结构化日志
```

#### 当前项目状态

```go
✅ 已完成 (80%):
  - ✅ Kratos 框架集成
  - ✅ Protobuf API (19个RPC)
  - ✅ DDD 分层架构
  - ✅ JWT 认证 (访问令牌 + 刷新令牌)
  - ✅ 多租户管理
  - ✅ RBAC 权限系统
  - ✅ 配额控制
  - ✅ 数据库迁移

❌ 缺失 (20%):
  - Wire 依赖注入未生成
  - Redis 缓存集成不完整
  - Consul 服务发现未集成
  - OAuth 2.0 / SSO 未实现
  - MFA 多因素认证未实现
  - 审计日志不完整
  - 单元测试缺失
```

#### 📋 TODO 清单

**🔥 P0 - 立即完成**:

- [ ] **生成 Wire 代码** (0.5 天)

  ```bash
  cd cmd/identity-service
  wire gen
  # 生成 wire_gen.go
  ```

- [ ] **完善 Redis 缓存** (1 天)

  ```go
  // internal/data/cache.go
  type UserCache struct {
      redis *redis.Client
  }

  func (c *UserCache) GetUser(id string) (*User, error)
  func (c *UserCache) SetUser(user *User, ttl time.Duration) error
  func (c *UserCache) DeleteUser(id string) error
  ```

- [ ] **Consul 服务注册** (1 天)

  ```go
  // internal/server/registry.go
  import "github.com/hashicorp/consul/api"

  func RegisterToConsul() error {
      client, _ := api.NewClient(api.DefaultConfig())
      registration := &api.AgentServiceRegistration{
          ID:      "identity-service-1",
          Name:    "identity-service",
          Port:    9000,
          Address: "127.0.0.1",
          Check: &api.AgentServiceCheck{
              GRPC:     "127.0.0.1:9000/grpc.health.v1.Health/Check",
              Interval: "10s",
          },
      }
      return client.Agent().ServiceRegister(registration)
  }
  ```

**⭐ P1 - 短期完成**:

- [ ] **OAuth 2.0 集成** (3 天)

  ```go
  // internal/biz/oauth.go
  type OAuthUsecase struct {
      providers map[string]OAuthProvider
  }

  func (uc *OAuthUsecase) GoogleLogin(code string) (*Token, error)
  func (uc *OAuthUsecase) GithubLogin(code string) (*Token, error)
  ```

- [ ] **审计日志增强** (1 天)

  ```go
  // internal/domain/audit_log.go
  type AuditLog struct {
      ID        string
      UserID    string
      TenantID  string
      Action    string  // "login", "logout", "create_user"
      Resource  string
      IPAddress string
      UserAgent string
      Timestamp time.Time
  }
  ```

- [ ] **单元测试** (3 天)
  ```go
  // internal/biz/user_test.go
  func TestCreateUser(t *testing.T)
  func TestAuthenticate(t *testing.T)
  func TestRefreshToken(t *testing.T)
  // 目标: 70%+ 覆盖率
  ```

**💡 P2 - 优化增强**:

- [ ] **MFA 多因素认证** (3 天)

  - TOTP (Time-based One-Time Password)
  - SMS 验证码
  - 邮箱验证码

- [ ] **SSO 单点登录** (5 天)
  - SAML 2.0
  - CAS
  - LDAP

**预计工时**: P0: 2.5 天, P1: 7 天, P2: 8 天, **总计: 17.5 天**

---

### 3. Session Service → Conversation Service (75%)

#### 源项目功能 (backend/session-service/)

```python
✅ 完整实现的功能：
- 会话 CRUD
- 消息管理
- 会话上下文维护
- Redis 缓存 (会话信息, 上下文)
- PostgreSQL 持久化
- 流式响应 (SSE)
- 会话分享
- Consul 服务注册
- Prometheus 指标
```

#### 当前项目状态

```go
✅ 已完成 (75%):
  - ✅ Protobuf API (12个RPC)
  - ✅ DDD 分层架构
  - ✅ 会话管理 (多模式: chat/agent/workflow/voice)
  - ✅ 消息管理
  - ✅ 上下文管理
  - ✅ Kafka 事件发布
  - ✅ 数据库迁移

❌ 缺失 (25%):
  - Redis 缓存实现不完整
  - 流式响应 (SSE/WebSocket) 未实现
  - 会话分享功能未实现
  - AI Orchestrator 调用未实现
  - 单元测试缺失
```

#### 📋 TODO 清单

**🔥 P0 - 立即完成**:

- [ ] **Redis 上下文缓存** (1 天)

  ```go
  // internal/data/context_cache.go
  type ContextCache struct {
      redis *redis.Client
  }

  func (c *ContextCache) GetContext(convID string) (*Context, error)
  func (c *ContextCache) SetContext(convID string, ctx *Context) error
  func (c *ContextCache) AppendMessage(convID string, msg *Message) error
  ```

- [ ] **调用 AI Orchestrator** (2 天)

  ```go
  // internal/infra/ai_client.go
  type AIClient struct {
      client pb.OrchestratorClient
  }

  func (c *AIClient) ProcessMessage(req *ProcessRequest) (*ProcessResponse, error)
  func (c *AIClient) StreamResponse(req *ProcessRequest) (stream, error)
  ```

**⭐ P1 - 短期完成**:

- [ ] **流式响应 (SSE)** (2 天)

  ```go
  // internal/interface/http/stream_handler.go
  func (h *StreamHandler) HandleSSE(c *gin.Context) {
      c.Writer.Header().Set("Content-Type", "text/event-stream")
      c.Writer.Header().Set("Cache-Control", "no-cache")

      for chunk := range stream {
          fmt.Fprintf(c.Writer, "data: %s\n\n", chunk)
          c.Writer.Flush()
      }
  }
  ```

- [ ] **WebSocket 支持** (2 天)

  ```go
  // internal/interface/websocket/handler.go
  func (h *WSHandler) HandleConnection(conn *websocket.Conn)
  func (h *WSHandler) BroadcastMessage(convID string, msg *Message)
  ```

- [ ] **会话分享** (1 天)

  ```go
  // internal/biz/share_usecase.go
  func (uc *ShareUsecase) CreateShareLink(convID string, opts ShareOptions) (*ShareLink, error)
  func (uc *ShareUsecase) GetSharedConversation(shareID string) (*Conversation, error)
  ```

- [ ] **单元测试** (3 天)

**💡 P2 - 优化增强**:

- [ ] **会话导出** (2 天)

  - 导出为 PDF
  - 导出为 Markdown
  - 导出为 JSON

- [ ] **会话模板** (2 天)
  - 创建模板
  - 从模板创建会话

**预计工时**: P0: 3 天, P1: 8 天, P2: 4 天, **总计: 15 天**

---

### 4. Document Service → Knowledge Service (30%)

#### 源项目功能 (backend/document-service/)

```python
✅ 完整实现的功能：
- 文档 CRUD (上传/下载/删除/更新)
- 文件格式转换 (Pandoc)
- 病毒扫描 (ClamAV)
- 文档版本管理 (多版本支持)
- MinIO 对象存储集成
- PostgreSQL 元数据存储
- 文档分享 (公开/私有链接)
- 权限管理 (所有者/编辑/查看)
- Consul 服务注册
- Prometheus 指标
```

#### 当前项目状态

```go
✅ 已完成 (30%):
  - ✅ Protobuf API 定义
  - ✅ 领域模型骨架

❌ 缺失 (70%):
  - MinIO 集成未实现
  - 文件上传/下载未实现
  - 病毒扫描未集成
  - 版本管理未实现
  - Kafka 事件发布未实现
  - 权限管理未实现
  - 业务逻辑层空白
  - 数据层实现缺失
```

#### 📋 TODO 清单

**🔥 P0 - 立即完成**:

- [ ] **MinIO 集成** (2 天)

  ```go
  // internal/infrastructure/storage/minio_client.go
  type MinIOClient struct {
      client *minio.Client
      bucket string
  }

  func (c *MinIOClient) UploadFile(key string, file io.Reader, size int64) error
  func (c *MinIOClient) DownloadFile(key string) (io.Reader, error)
  func (c *MinIOClient) DeleteFile(key string) error
  func (c *MinIOClient) GetPresignedURL(key string, expires time.Duration) (string, error)
  ```

- [ ] **文档上传流程** (3 天)

  ```go
  // internal/application/document_service.go
  func (s *DocumentService) UploadDocument(req *UploadRequest) (*Document, error) {
      // 1. 验证文件类型和大小
      // 2. 生成唯一文件名
      // 3. 病毒扫描
      // 4. 上传到 MinIO
      // 5. 保存元数据到 PostgreSQL
      // 6. 发布 document.uploaded 事件到 Kafka
  }
  ```

- [ ] **ClamAV 病毒扫描** (1 天)

  ```go
  // internal/infrastructure/security/virus_scanner.go
  type VirusScanner struct {
      clamavHost string
      clamavPort int
  }

  func (s *VirusScanner) ScanFile(file io.Reader) (bool, error)
  ```

- [ ] **Kafka 事件发布** (1 天)

  ```go
  // internal/infrastructure/event/publisher.go
  type EventPublisher struct {
      producer *kafka.Producer
  }

  func (p *EventPublisher) PublishDocumentUploaded(doc *Document) error
  func (p *EventPublisher) PublishDocumentDeleted(docID string) error
  ```

**⭐ P1 - 短期完成**:

- [ ] **版本管理** (3 天)

  ```go
  // internal/domain/version.go
  type DocumentVersion struct {
      ID         string
      DocumentID string
      Version    int
      FileKey    string
      FileSize   int64
      CreatedAt  time.Time
      CreatedBy  string
  }

  func (s *DocumentService) CreateVersion(docID string, file io.Reader) (*DocumentVersion, error)
  func (s *DocumentService) GetVersion(docID string, version int) (*DocumentVersion, error)
  func (s *DocumentService) ListVersions(docID string) ([]*DocumentVersion, error)
  func (s *DocumentService) CompareVersions(docID string, v1, v2 int) (*VersionDiff, error)
  ```

- [ ] **权限管理** (2 天)

  ```go
  // internal/domain/permission.go
  type DocumentPermission struct {
      DocumentID string
      UserID     string
      Role       string  // "owner", "editor", "viewer"
  }

  func (s *DocumentService) GrantPermission(docID, userID, role string) error
  func (s *DocumentService) RevokePermission(docID, userID string) error
  func (s *DocumentService) CheckPermission(docID, userID string, action string) (bool, error)
  ```

- [ ] **文档分享** (2 天)
  ```go
  // internal/application/share_service.go
  func (s *ShareService) CreateShareLink(docID string, opts ShareOptions) (*ShareLink, error)
  func (s *ShareService) GetSharedDocument(shareID string) (*Document, error)
  ```

**💡 P2 - 优化增强**:

- [ ] **格式转换** (3 天)

  - 集成 Pandoc
  - PDF → Markdown
  - Word → Markdown
  - HTML → Markdown

- [ ] **文档预览** (2 天)
  - PDF 预览
  - 图片预览
  - Office 文档预览

**预计工时**: P0: 7 天, P1: 7 天, P2: 5 天, **总计: 19 天**

---

### 5. GraphRAG Service → 3 个服务 (5%)

#### 源项目功能 (algo/graphrag-service/)

```python
✅ 完整实现的功能：
- 文档解析 (PDF/Word/Markdown/HTML)
- 文档分块 (RecursiveCharacterTextSplitter)
- 向量化 (BGE-M3 Embeddings)
- FAISS 向量存储和检索
- Neo4j 知识图谱构建
- 实体识别和关系抽取
- 社区检测 (Louvain/Label Propagation)
- 混合检索 (向量 + BM25 + 图谱)
- 重排序 (Cross-Encoder)
- 查询改写
- 语义缓存
- Prometheus 指标
```

#### 当前项目状态

**需拆分为 3 个服务**:

1. **Indexing Service** (Python/FastAPI) - 索引构建
2. **Retrieval Service** (Python/FastAPI) - 检索服务
3. **RAG Engine** (Python/FastAPI) - RAG 引擎

```python
❌ 当前状态 (5%):
  - ✅ 目录结构存在
  - ✅ FastAPI 基础框架
  - ❌ 核心功能完全缺失
```

#### 📋 TODO 清单 - Indexing Service

**🔥 P0 - 立即完成** (10 天):

- [ ] **Kafka Consumer** (1 天)

  ```python
  # app/infrastructure/kafka_consumer.py
  from confluent_kafka import Consumer

  class DocumentEventConsumer:
      def __init__(self):
          self.consumer = Consumer({
              'bootstrap.servers': 'kafka:9092',
              'group.id': 'indexing-service',
              'auto.offset.reset': 'earliest'
          })
          self.consumer.subscribe(['document.events'])

      def consume(self):
          while True:
              msg = self.consumer.poll(1.0)
              if msg:
                  self.handle_event(msg.value())
  ```

- [ ] **文档解析器** (3 天)

  ```python
  # app/core/parsers/
  class PDFParser:
      def parse(self, file_path: str) -> str

  class WordParser:
      def parse(self, file_path: str) -> str

  class MarkdownParser:
      def parse(self, file_path: str) -> str

  class ExcelParser:
      def parse(self, file_path: str) -> List[str]
  ```

- [ ] **文档分块** (1 天)

  ```python
  # app/core/chunker.py
  from langchain.text_splitter import RecursiveCharacterTextSplitter

  class DocumentChunker:
      def __init__(self, chunk_size=500, chunk_overlap=50):
          self.splitter = RecursiveCharacterTextSplitter(
              chunk_size=chunk_size,
              chunk_overlap=chunk_overlap
          )

      def chunk(self, text: str) -> List[str]
  ```

- [ ] **向量化** (2 天)

  ```python
  # app/core/embedder.py
  from sentence_transformers import SentenceTransformer

  class BGE_M3_Embedder:
      def __init__(self):
          self.model = SentenceTransformer('BAAI/bge-m3')

      def embed(self, texts: List[str]) -> np.ndarray
      def embed_query(self, query: str) -> np.ndarray
  ```

- [ ] **Milvus 集成** (2 天)

  ```python
  # app/infrastructure/milvus_client.py
  from pymilvus import Collection, connections

  class MilvusClient:
      def __init__(self):
          connections.connect(host='milvus', port='19530')
          self.collection = Collection('document_chunks')

      def insert_vectors(self, chunks: List[Chunk], embeddings: np.ndarray)
      def search(self, query_embedding: np.ndarray, top_k: int) -> List[Chunk]
  ```

- [ ] **Neo4j 图谱构建** (2 天)

  ```python
  # app/core/graph_builder.py
  from neo4j import GraphDatabase

  class GraphBuilder:
      def __init__(self):
          self.driver = GraphDatabase.driver('bolt://neo4j:7687')

      def extract_entities(self, text: str) -> List[Entity]
      def extract_relationships(self, text: str) -> List[Relationship]
      def build_graph(self, document_id: str, entities, relationships)
  ```

#### 📋 TODO 清单 - Retrieval Service

**🔥 P0 - 立即完成** (8 天):

- [ ] **Milvus 向量检索** (1 天)

  ```python
  # app/core/vector_retriever.py
  class VectorRetriever:
      def retrieve(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Chunk]
  ```

- [ ] **BM25 检索** (2 天)

  ```python
  # app/core/bm25_retriever.py
  from rank_bm25 import BM25Okapi

  class BM25Retriever:
      def __init__(self):
          self.bm25 = None  # 需要从文档语料库构建

      def retrieve(self, query: str, top_k: int = 10) -> List[Chunk]
  ```

- [ ] **图谱检索** (2 天)

  ```python
  # app/core/graph_retriever.py
  class GraphRetriever:
      def retrieve_by_entity(self, entity: str) -> List[Node]
      def retrieve_by_relationship(self, source: str, target: str) -> List[Path]
      def retrieve_community(self, entity: str, depth: int = 2) -> List[Node]
  ```

- [ ] **混合检索 (RRF)** (1 天)

  ```python
  # app/core/hybrid_retriever.py
  class HybridRetriever:
      def __init__(self):
          self.vector_retriever = VectorRetriever()
          self.bm25_retriever = BM25Retriever()
          self.graph_retriever = GraphRetriever()

      def retrieve(self, query: str, mode: str = "hybrid", top_k: int = 20) -> List[Chunk]:
          # RRF (Reciprocal Rank Fusion)
          vector_results = self.vector_retriever.retrieve(...)
          bm25_results = self.bm25_retriever.retrieve(...)
          graph_results = self.graph_retriever.retrieve(...)

          return self.fuse_results(vector_results, bm25_results, graph_results)
  ```

- [ ] **重排序** (1 天)

  ```python
  # app/core/reranker.py
  from sentence_transformers import CrossEncoder

  class Reranker:
      def __init__(self):
          self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')

      def rerank(self, query: str, chunks: List[Chunk], top_k: int = 10) -> List[Chunk]
  ```

- [ ] **Redis 语义缓存** (1 天)

  ```python
  # app/infrastructure/semantic_cache.py
  class SemanticCache:
      def __init__(self):
          self.redis = redis.Redis()
          self.embedder = BGE_M3_Embedder()

      def get(self, query: str, threshold: float = 0.95) -> Optional[List[Chunk]]
      def set(self, query: str, results: List[Chunk], ttl: int = 86400)
  ```

#### 📋 TODO 清单 - RAG Engine

**🔥 P0 - 立即完成** (5 天):

- [ ] **查询改写** (1 天)

  ```python
  # app/core/query_rewriter.py
  class QueryRewriter:
      def rewrite(self, query: str) -> List[str]:
          # HyDE (Hypothetical Document Embeddings)
          # Multi-Query
          # Step-back Prompting
  ```

- [ ] **上下文构建** (1 天)

  ```python
  # app/core/context_builder.py
  class ContextBuilder:
      def build(self, query: str, chunks: List[Chunk], max_tokens: int = 4000) -> str
  ```

- [ ] **答案生成** (2 天)

  ```python
  # app/core/answer_generator.py
  class AnswerGenerator:
      def generate(self, query: str, context: str) -> str
      def generate_stream(self, query: str, context: str) -> Iterator[str]
  ```

- [ ] **引用来源** (1 天)
  ```python
  # app/core/citation_generator.py
  class CitationGenerator:
      def generate_citations(self, answer: str, chunks: List[Chunk]) -> List[Citation]
  ```

**预计工时**:

- Indexing Service: 10 天
- Retrieval Service: 8 天
- RAG Engine: 5 天
- **总计: 23 天**

---

### 6. Agent Service → Agent Engine (15%)

#### 源项目功能 (algo/agent-service/)

```python
✅ 完整实现的功能：
- LangGraph Agent 工作流
- ReAct (Reason + Act) 模式
- 任务规划 (Planner)
- 工具执行 (Executor)
- 反思机制 (Reflector)
- 工具注册表 (50+ 工具)
- MCP (Model Context Protocol) 集成
- 长期记忆 (FAISS 向量存储)
- 记忆衰减管理
- 对话历史管理
- Prometheus 指标
```

#### 当前项目状态

```python
❌ 当前状态 (15%):
  - ✅ FastAPI 框架
  - ✅ OpenTelemetry 追踪
  - ✅ Prometheus metrics
  - ✅ 基础路由
  - ❌ LangGraph 工作流未实现
  - ❌ 工具系统未实现
  - ❌ 记忆管理未实现
```

#### 📋 TODO 清单

**🔥 P0 - 立即完成** (8 天):

- [ ] **LangGraph 工作流** (3 天)

  ```python
  # app/core/agent/workflow.py
  from langgraph.graph import StateGraph, END

  class AgentWorkflow:
      def __init__(self):
          workflow = StateGraph(AgentState)

          # 添加节点
          workflow.add_node("planner", self.planner_node)
          workflow.add_node("executor", self.executor_node)
          workflow.add_node("reflector", self.reflector_node)

          # 添加边
          workflow.set_entry_point("planner")
          workflow.add_edge("planner", "executor")
          workflow.add_conditional_edges("executor", self.should_reflect, {
              True: "reflector",
              False: END
          })
          workflow.add_edge("reflector", "planner")

          self.graph = workflow.compile()

      def planner_node(self, state: AgentState) -> AgentState
      def executor_node(self, state: AgentState) -> AgentState
      def reflector_node(self, state: AgentState) -> AgentState
  ```

- [ ] **工具注册表** (2 天)

  ```python
  # app/core/tools/registry.py
  class ToolRegistry:
      def __init__(self):
          self.tools = {}
          self.register_builtin_tools()

      def register(self, tool: Tool)
      def get_tool(self, name: str) -> Tool
      def list_tools(self) -> List[Tool]

      def register_builtin_tools(self):
          self.register(SearchTool())
          self.register(CalculatorTool())
          self.register(CodeInterpreterTool())
          self.register(WebScraperTool())
          # ... 50+ 工具
  ```

- [ ] **工具调用系统** (2 天)

  ```python
  # app/core/tools/executor.py
  class ToolExecutor:
      def __init__(self, registry: ToolRegistry):
          self.registry = registry

      def execute(self, tool_name: str, args: Dict) -> ToolResult:
          tool = self.registry.get_tool(tool_name)

          # 白名单检查
          if not self.is_allowed(tool_name):
              raise PermissionError()

          # 参数验证
          tool.validate_args(args)

          # 超时控制
          with timeout(30):
              result = tool.execute(**args)

          # 成本追踪
          self.track_cost(tool_name, result)

          return result
  ```

- [ ] **长期记忆** (1 天)

  ```python
  # app/core/memory/vector_memory.py
  class VectorMemory:
      def __init__(self):
          self.index = faiss.IndexFlatIP(1024)
          self.memories = []

      def add(self, memory: Memory)
      def search(self, query: str, top_k: int = 5) -> List[Memory]
      def decay(self, factor: float = 0.9)
  ```

**⭐ P1 - 短期完成** (5 天):

- [ ] **MCP 集成** (2 天)

  ```python
  # app/core/tools/mcp_integration.py
  class MCPClient:
      def discover_tools(self) -> List[Tool]
      def call_tool(self, tool_name: str, params: Dict) -> Any
  ```

- [ ] **记忆衰减** (1 天)

  ```python
  # app/core/memory/decay_manager.py
  class DecayManager:
      def apply_decay(self, memories: List[Memory], factor: float)
      def prune_old_memories(self, threshold: float)
  ```

- [ ] **对话历史** (1 天)

  ```python
  # app/core/memory/conversation_history.py
  class ConversationHistory:
      def add_turn(self, user_msg: str, assistant_msg: str)
      def get_context(self, max_turns: int = 10) -> str
      def summarize(self) -> str
  ```

- [ ] **单元测试** (1 天)

**💡 P2 - 优化增强** (3 天):

- [ ] **多 Agent 协作** (2 天)
- [ ] **Agent 可视化** (1 天)

**预计工时**: P0: 8 天, P1: 5 天, P2: 3 天, **总计: 16 天**

---

### 7. Voice Service → Voice Engine (10%)

#### 源项目功能 (algo/voice-service/)

```python
✅ 完整实现的功能：
- ASR (Whisper / Azure Speech)
- TTS (Edge TTS / Azure TTS)
- VAD (Silero VAD)
- 说话人分离
- 情感识别
- 语音降噪
- 实时转写
- 流式识别
- WebRTC 集成
- Prometheus 指标
```

#### 当前项目状态

```python
❌ 当前状态 (10%):
  - ✅ FastAPI 框架
  - ❌ ASR 未实现
  - ❌ TTS 未实现
  - ❌ VAD 未实现
```

#### 📋 TODO 清单

**🔥 P0 - 立即完成** (6 天):

- [ ] **Whisper ASR** (2 天)

  ```python
  # app/core/asr/whisper_asr.py
  import whisper

  class WhisperASR:
      def __init__(self, model_size='base'):
          self.model = whisper.load_model(model_size)

      def transcribe(self, audio_file: str) -> str
      def transcribe_stream(self, audio_stream) -> Iterator[str]
  ```

- [ ] **Silero VAD** (1 天)

  ```python
  # app/core/vad/silero_vad.py
  import torch

  class SileroVAD:
      def __init__(self):
          self.model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')

      def detect_speech(self, audio: np.ndarray) -> List[Tuple[float, float]]
  ```

- [ ] **Edge TTS** (2 天)

  ```python
  # app/core/tts/edge_tts.py
  import edge_tts

  class EdgeTTS:
      async def synthesize(self, text: str, voice: str = 'zh-CN-XiaoxiaoNeural') -> bytes
      async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]
  ```

- [ ] **WebRTC 集成** (1 天)

  ```python
  # app/api/webrtc_handler.py
  from aiortc import RTCPeerConnection, RTCSessionDescription

  class WebRTCHandler:
      async def offer(self, sdp: str) -> str
      async def on_track(self, track)
  ```

**⭐ P1 - 短期完成** (4 天):

- [ ] **说话人分离** (2 天)
- [ ] **情感识别** (1 天)
- [ ] **语音降噪** (1 天)

**预计工时**: P0: 6 天, P1: 4 天, **总计: 10 天**

---

### 8. LLM Router → 2 个服务 (10%)

#### 源项目功能 (algo/llm-router-service/)

```python
✅ 完整实现的功能：
- 多模型支持 (OpenAI/Claude/Zhipu/Qianwen)
- 流式和非流式双模式
- 成本优化路由
- 降级策略
- 重试机制
- Token 计数
- 成本追踪
- 语义缓存
- Prometheus 指标
```

#### 当前项目状态

**需拆分为 2 个服务**:

1. **Model Router** (Go/Kratos) - 路由决策
2. **Model Adapter** (Python/FastAPI) - API 适配

```
❌ 当前状态 (10%):
  - ✅ 目录结构
  - ❌ 核心功能未实现
```

#### 📋 TODO 清单 - Model Router (Go)

**🔥 P0 - 立即完成** (5 天):

- [ ] **路由决策引擎** (2 天)

  ```go
  // internal/application/routing_service.go
  type RoutingService struct {
      models    map[string]*Model
      strategies []Strategy
  }

  func (s *RoutingService) SelectModel(req *RouteRequest) (*Model, error) {
      // 策略: 成本优先 / 延迟优先 / 可用性优先
      for _, strategy := range s.strategies {
          if model := strategy.Select(req, s.models); model != nil {
              return model, nil
          }
      }
      return s.fallback(), nil
  }
  ```

- [ ] **成本优化器** (1 天)

  ```go
  // internal/application/cost_optimizer.go
  type CostOptimizer struct {
      pricing map[string]float64
  }

  func (o *CostOptimizer) CalculateCost(model string, tokens int) float64
  func (o *CostOptimizer) SelectCheapestModel(req *RouteRequest) *Model
  ```

- [ ] **降级管理器** (1 天)

  ```go
  // internal/application/fallback_manager.go
  type FallbackManager struct {
      fallbackChain []string
  }

  func (m *FallbackManager) GetFallback(failedModel string) *Model
  ```

- [ ] **gRPC 服务实现** (1 天)

#### 📋 TODO 清单 - Model Adapter (Python)

**🔥 P0 - 立即完成** (6 天):

- [ ] **OpenAI 适配器** (1 天)

  ```python
  # app/adapters/openai_adapter.py
  import openai

  class OpenAIAdapter:
      def chat(self, messages: List[Dict], model: str = 'gpt-4') -> str
      def chat_stream(self, messages: List[Dict]) -> Iterator[str]
      def count_tokens(self, messages: List[Dict]) -> int
  ```

- [ ] **Claude 适配器** (1 天)

  ```python
  # app/adapters/claude_adapter.py
  import anthropic

  class ClaudeAdapter:
      def chat(self, messages: List[Dict], model: str = 'claude-3-opus') -> str
      def chat_stream(self, messages: List[Dict]) -> Iterator[str]
  ```

- [ ] **Zhipu 适配器** (1 天)

  ```python
  # app/adapters/zhipu_adapter.py
  class ZhipuAdapter:
      def chat(self, messages: List[Dict], model: str = 'glm-4') -> str
  ```

- [ ] **协议转换器** (1 天)

  ```python
  # app/core/protocol_converter.py
  class ProtocolConverter:
      def to_openai_format(self, messages: List[Dict]) -> List[Dict]
      def from_openai_format(self, response: Dict) -> str
  ```

- [ ] **错误处理器** (1 天)

  ```python
  # app/core/error_handler.py
  class ErrorHandler:
      def handle(self, error: Exception) -> Response
      def should_retry(self, error: Exception) -> bool
      def get_retry_delay(self, attempt: int) -> float
  ```

- [ ] **gRPC 服务** (1 天)

**预计工时**:

- Model Router: 5 天
- Model Adapter: 6 天
- **总计: 11 天**

---

### 9. Multimodal Service → Multimodal Engine (10%)

#### 源项目功能 (algo/multimodal-service/)

```python
✅ 完整实现的功能：
- OCR (Tesseract / Paddle OCR)
- 图像理解 (GPT-4V / Claude Vision)
- 表格识别
- 文档布局分析
- 视频分析 (帧提取)
- Prometheus 指标
```

#### 当前项目状态

```python
❌ 当前状态 (10%):
  - ✅ FastAPI 框架
  - ❌ OCR 未实现
  - ❌ 视觉理解未实现
```

#### 📋 TODO 清单

**⭐ P1 - 短期完成** (6 天):

- [ ] **Paddle OCR** (2 天)

  ```python
  # app/core/ocr/paddle_ocr.py
  from paddleocr import PaddleOCR

  class PaddleOCREngine:
      def __init__(self):
          self.ocr = PaddleOCR(lang='ch')

      def recognize(self, image_path: str) -> str
      def recognize_table(self, image_path: str) -> List[List[str]]
  ```

- [ ] **GPT-4V 集成** (2 天)

  ```python
  # app/core/vision/gpt4v.py
  class GPT4VisionEngine:
      def analyze_image(self, image_path: str, prompt: str) -> str
      def extract_entities(self, image_path: str) -> List[Entity]
  ```

- [ ] **视频处理** (2 天)
  ```python
  # app/core/video/analyzer.py
  class VideoAnalyzer:
      def extract_frames(self, video_path: str, interval: int = 1) -> List[np.ndarray]
      def analyze_video(self, video_path: str) -> VideoAnalysis
  ```

**预计工时**: 6 天

---

### 10. Notification Service (10%)

#### 源项目功能 (backend/notification-service/)

```python
✅ 完整实现的功能：
- 多渠道通知 (邮件/短信/Push/Webhook)
- 模板引擎 (Jinja2)
- RabbitMQ 消息队列
- 设备 Token 管理
- 推送通知 (FCM/APNs)
- 通知历史
- 重试机制
- Prometheus 指标
```

#### 当前项目状态

```go
❌ 当前状态 (10%):
  - ✅ 目录结构
  - ❌ 核心功能未实现
```

#### 📋 TODO 清单

**⭐ P1 - 短期完成** (7 天):

- [ ] **邮件发送** (1 天)

  ```go
  // internal/infrastructure/channels/email.go
  type EmailChannel struct {
      smtp SMTPConfig
  }

  func (c *EmailChannel) Send(notification *Notification) error
  ```

- [ ] **短信发送** (1 天)

  ```go
  // internal/infrastructure/channels/sms.go
  type SMSChannel struct {
      provider SMSProvider
  }

  func (c *SMSChannel) Send(notification *Notification) error
  ```

- [ ] **Push 通知** (2 天)

  ```go
  // internal/infrastructure/channels/push.go
  type PushChannel struct {
      fcm  *FCMClient
      apns *APNsClient
  }

  func (c *PushChannel) Send(notification *Notification) error
  ```

- [ ] **模板引擎** (1 天)

  ```go
  // internal/application/template_service.go
  type TemplateService struct {
      templates map[string]*Template
  }

  func (s *TemplateService) Render(templateID string, data map[string]interface{}) (string, error)
  ```

- [ ] **Kafka 消费者** (1 天)

  ```go
  // internal/infrastructure/kafka/consumer.go
  type NotificationConsumer struct {
      consumer *kafka.Consumer
  }

  func (c *NotificationConsumer) Subscribe(topics []string)
  func (c *NotificationConsumer) HandleEvent(event *Event)
  ```

- [ ] **RabbitMQ 任务队列** (1 天)

  ```go
  // internal/infrastructure/queue/rabbitmq.go
  type TaskQueue struct {
      channel *amqp.Channel
  }

  func (q *TaskQueue) Enqueue(task *Task) error
  func (q *TaskQueue) Consume() <-chan *Task
  ```

**预计工时**: 7 天

---

### 11. AI Orchestrator (5%)

#### 新增服务 - 任务编排

```go
❌ 当前状态 (5%):
  - ✅ 目录结构
  - ❌ 核心功能完全未实现
```

#### 📋 TODO 清单

**🔥 P0 - 立即完成** (6 天):

- [ ] **任务路由器** (2 天)

  ```go
  // internal/application/task_router.go
  type TaskRouter struct {
      engines map[string]EngineClient
  }

  func (r *TaskRouter) RouteTask(task *Task) (EngineClient, error) {
      switch task.Type {
      case "agent":
          return r.engines["agent"], nil
      case "rag":
          return r.engines["rag"], nil
      case "voice":
          return r.engines["voice"], nil
      }
  }
  ```

- [ ] **流程编排器** (2 天)

  ```go
  // internal/application/orchestration_service.go
  type OrchestrationService struct {
      router    *TaskRouter
      aggregator *ResultAggregator
  }

  func (s *OrchestrationService) ExecuteWorkflow(workflow *Workflow) (*Result, error) {
      // 支持串行、并行、条件分支
      for _, step := range workflow.Steps {
          engine := s.router.RouteTask(step.Task)
          result := engine.Execute(step.Task)
          // ...
      }
  }
  ```

- [ ] **结果聚合器** (1 天)

  ```go
  // internal/application/result_aggregator.go
  type ResultAggregator struct{}

  func (a *ResultAggregator) Aggregate(results []*Result) *AggregatedResult
  ```

- [ ] **gRPC 服务** (1 天)

**预计工时**: 6 天

---

### 12. Analytics Service (5%)

#### 新增服务 - 实时统计

```go
❌ 当前状态 (5%):
  - ✅ 目录结构
  - ❌ 核心功能完全未实现
```

#### 📋 TODO 清单

**⭐ P1 - 短期完成** (5 天):

- [ ] **ClickHouse 客户端** (1 天)

  ```go
  // internal/infrastructure/clickhouse_client.go
  type ClickHouseClient struct {
      conn clickhouse.Conn
  }

  func (c *ClickHouseClient) Query(sql string, args ...interface{}) (*sql.Rows, error)
  ```

- [ ] **实时指标查询** (2 天)

  ```go
  // internal/application/metrics_service.go
  type MetricsService struct {
      ch *ClickHouseClient
  }

  func (s *MetricsService) GetTodayUsage(tenantID string) (*Usage, error)
  func (s *MetricsService) GetTrend(tenantID string, days int) ([]*DataPoint, error)
  func (s *MetricsService) GetTopTenants(limit int) ([]*TenantUsage, error)
  ```

- [ ] **报表生成** (1 天)

  ```go
  // internal/application/report_service.go
  type ReportService struct{}

  func (s *ReportService) GenerateDailyReport(date time.Time) (*Report, error)
  func (s *ReportService) GenerateMonthlyReport(month time.Time) (*Report, error)
  ```

- [ ] **gRPC 服务** (1 天)

**预计工时**: 5 天

---

## 📈 总工时估算

### 按优先级统计

| 优先级    | 服务数 | 预计工时   | 说明                   |
| --------- | ------ | ---------- | ---------------------- |
| 🔥 **P0** | 6      | **64 天**  | 阻塞开发，必须立即完成 |
| ⭐ **P1** | 10     | **71 天**  | 短期完成，1-2 周内     |
| 💡 **P2** | 8      | **35 天**  | 优化增强，1-2 月内     |
| **总计**  | -      | **170 天** | 按 1 人计算            |

### 按服务统计

| 服务                     | P0 工时   | P1 工时   | P2 工时   | 总计        |
| ------------------------ | --------- | --------- | --------- | ----------- |
| 1. Backend Gateway       | 4 天      | 6 天      | 3 天      | **13 天**   |
| 2. Identity Service      | 2.5 天    | 7 天      | 8 天      | **17.5 天** |
| 3. Conversation Service  | 3 天      | 8 天      | 4 天      | **15 天**   |
| 4. Knowledge Service     | 7 天      | 7 天      | 5 天      | **19 天**   |
| 5. Indexing Service      | 10 天     | -         | -         | **10 天**   |
| 6. Retrieval Service     | 8 天      | -         | -         | **8 天**    |
| 7. RAG Engine            | 5 天      | -         | -         | **5 天**    |
| 8. Agent Engine          | 8 天      | 5 天      | 3 天      | **16 天**   |
| 9. Voice Engine          | 6 天      | 4 天      | -         | **10 天**   |
| 10. Model Router         | 5 天      | -         | -         | **5 天**    |
| 11. Model Adapter        | 6 天      | -         | -         | **6 天**    |
| 12. Multimodal Engine    | -         | 6 天      | -         | **6 天**    |
| 13. Notification Service | -         | 7 天      | -         | **7 天**    |
| 14. AI Orchestrator      | 6 天      | -         | -         | **6 天**    |
| 15. Analytics Service    | -         | 5 天      | -         | **5 天**    |
| **GraphRAG 拆分总计**    | 23 天     | -         | -         | **23 天**   |
| **LLM Router 拆分总计**  | 11 天     | -         | -         | **11 天**   |
| **总计**                 | **64 天** | **71 天** | **35 天** | **170 天**  |

### 按团队规模换算

| 团队规模 | 预计时间              | 说明            |
| -------- | --------------------- | --------------- |
| 1 人     | **34 周** (8.5 个月)  | 不推荐          |
| 2 人     | **17 周** (4.25 个月) | 可行，但紧张    |
| 4 人     | **8.5 周** (2 个月)   | **推荐配置** ✅ |
| 6 人     | **5.7 周** (1.5 个月) | 理想但成本高    |

---

## 🎯 推荐执行方案

### 方案 A: 4 人团队 (推荐) ✅

**团队配置**:

- 2 名 Go 工程师 (后端服务)
- 2 名 Python 工程师 (算法服务)

**执行计划** (8 周):

**Week 1-2: P0 阻塞项**

- Go Team: Gateway + Identity + Conversation 完善
- Python Team: Indexing + Retrieval Service

**Week 3-4: P0 核心服务**

- Go Team: Knowledge Service + AI Orchestrator
- Python Team: RAG Engine + Agent Engine

**Week 5-6: P1 重要功能**

- Go Team: Model Router + Notification
- Python Team: Model Adapter + Voice Engine

**Week 7-8: P1 完善 + P2 优化**

- Go Team: Analytics + 测试
- Python Team: Multimodal + 测试

**预计完成**:

- P0: 100%
- P1: 80%
- P2: 30%

---

## 📝 关键建议

### 1. 优先级建议

**立即启动** (本周):

1. ✅ 完善 APISIX 路由配置
2. ✅ 完成 Knowledge Service (MinIO + Kafka)
3. ✅ 实现 Indexing Service (文档解析 + 向量化)
4. ✅ 实现 Retrieval Service (向量检索)

**下周启动**: 5. ✅ 实现 Agent Engine (LangGraph) 6. ✅ 实现 AI Orchestrator 7. ✅ 完善 Identity + Conversation Service

### 2. 技术债务

**必须解决**:

- [ ] 所有服务的 Wire 依赖注入
- [ ] Consul 服务发现集成
- [ ] Redis 缓存完善
- [ ] 单元测试 (目标 70%+)

**可延后**:

- OAuth 2.0 / SSO
- MFA 多因素认证
- 灰度发布
- 多 Agent 协作

### 3. 风险提示

**高风险项**:

- ⚠️ GraphRAG 拆分 (3 个服务) - 工作量大，依赖多
- ⚠️ Agent Engine LangGraph - 复杂度高
- ⚠️ 事件驱动架构 - 需要完整的 Kafka 集成

**缓解措施**:

- 参考源项目代码
- 渐进式开发
- 充分测试

---

**生成时间**: 2025-10-26
**审查人**: AI Code Reviewer
**版本**: v1.0
**建议复审**: 每周更新进度
