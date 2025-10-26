# VoiceHelper 功能迭代执行清单

> **开始日期**: 2025-10-26
> **执行团队**: 4 人 (2 Go + 2 Python)
> **执行周期**: 18 周 (~4.5 个月)
> **当前阶段**: Phase 1 - Week 1

---

## 📋 使用说明

- ✅ 已完成
- 🟡 进行中
- ❌ 未开始
- ⏸️ 阻塞中
- 🔥 高优先级
- ⚠️ 有风险

**更新频率**: 每日更新进度
**检查点**: 每周五 16:00 团队同步

---

## Phase 1: 基础打通 (4 周)

**目标**: MVP 可用，技术债务清零

### Week 1: 技术债务修复 (2025-10-26 ~ 2025-11-01)

#### Day 1-2: Go 服务修复 (Go Team)

**负责人**: [Go Lead]
**预计工时**: 2 天

- [ ] 🔥 **生成 Wire 依赖注入代码** (1 天)

  - [ ] identity-service
    ```bash
    cd cmd/identity-service && wire gen && cd ../..
    ```
  - [ ] conversation-service
  - [ ] knowledge-service
  - [ ] ai-orchestrator
  - [ ] model-router
  - [ ] notification-service
  - [ ] analytics-service
  - [ ] 验证: 所有服务可正常启动

- [ ] 🔥 **集成 Consul 服务发现** (1 天)
  - [ ] 安装 Consul Agent
    ```bash
    docker-compose up -d consul
    ```
  - [ ] 实现服务注册逻辑
    ```go
    // internal/server/registry.go
    func RegisterToConsul(serviceName string, port int) error
    ```
  - [ ] 实现健康检查
    ```go
    Check: &api.AgentServiceCheck{
        GRPC:     "127.0.0.1:9000/grpc.health.v1.Health/Check",
        Interval: "10s",
    }
    ```
  - [ ] 所有服务集成注册逻辑
  - [ ] 验证: Consul UI 可见所有服务

#### Day 2-3: Redis 缓存完善 (Go Team)

**负责人**: [Go Dev]
**预计工时**: 1 天

- [ ] 🔥 **Identity Service 缓存**

  - [ ] 用户信息缓存 (TTL: 1h)
    ```go
    func (c *UserCache) GetUser(id string) (*User, error)
    func (c *UserCache) SetUser(user *User) error
    ```
  - [ ] Token 缓存 (TTL: 24h)
  - [ ] 权限缓存 (TTL: 10min)
  - [ ] 验证: 缓存命中率 > 30%

- [ ] 🔥 **Conversation Service 缓存**
  - [ ] 会话上下文缓存 (TTL: 24h)
    ```go
    func (c *ContextCache) GetContext(convID string) (*Context, error)
    func (c *ContextCache) AppendMessage(convID string, msg *Message) error
    ```
  - [ ] 验证: 上下文读写正常

#### Day 1-2: Kafka Event Schema (Go Team)

**负责人**: [Go Lead]
**预计工时**: 1 天

- [ ] 🔥 **定义 Protobuf Event Schema**
  - [ ] `api/proto/events/v1/conversation.proto`
    ```protobuf
    message ConversationEvent {
      string event_id = 1;
      string event_type = 2;  // message.sent, message.received
      string conversation_id = 3;
      string tenant_id = 4;
      google.protobuf.Timestamp timestamp = 5;
      google.protobuf.Any payload = 6;
    }
    ```
  - [ ] `api/proto/events/v1/document.proto`
    ```protobuf
    message DocumentEvent {
      string event_id = 1;
      string event_type = 2;  // uploaded, deleted, indexed
      string document_id = 3;
      string tenant_id = 4;
      google.protobuf.Timestamp timestamp = 5;
      google.protobuf.Any payload = 6;
    }
    ```
  - [ ] 生成代码
    ```bash
    ./scripts/proto-gen.sh
    ```
  - [ ] 验证: Proto 编译通过

#### Day 2-3: Event Publisher/Consumer (Go + Python Team)

**负责人**: [Go Dev] + [Python Lead]
**预计工时**: 1 天

- [ ] 🔥 **Conversation Service - Producer** (Go)

  - [ ] 实现 Event Publisher
    ```go
    // internal/infra/kafka/publisher.go
    func (p *EventPublisher) PublishMessageSent(msg *Message) error
    ```
  - [ ] 集成到业务逻辑
  - [ ] 验证: 消息发送到 Kafka

- [ ] 🔥 **Indexing Service - Consumer** (Python)
  - [ ] 实现 Kafka Consumer
    ```python
    # app/infrastructure/kafka_consumer.py
    class DocumentEventConsumer:
        def consume(self):
            # 订阅 document.events
    ```
  - [ ] 验证: 消费消息正常

#### Day 3-4: APISIX 配置完善 (Go Team)

**负责人**: [Go Lead]
**预计工时**: 2 天

- [ ] 🔥 **完整路由配置** (1 天)

  - [ ] 创建 `configs/gateway/apisix-routes.yaml`
  - [ ] 配置 14 个服务路由
    ```yaml
    routes:
      - id: identity-service
        uri: /api/v1/identity/*
        upstream:
          nodes:
            - host: identity-service
              port: 9000
        plugins:
          jwt-auth: {}
          limit-req: { rate: 100, burst: 50 }
          prometheus: {}
    ```
  - [ ] JWT 认证插件配置
  - [ ] 限流插件配置
  - [ ] 验证: 所有路由可访问

- [ ] 🔥 **监控配置** (1 天)
  - [ ] Prometheus 插件配置
  - [ ] OpenTelemetry 插件配置
  - [ ] 验证: Prometheus 可抓取指标

#### Week 1 验收标准

- ✅ 所有 Go 服务可正常启动
- ✅ Consul UI 显示所有服务健康
- ✅ Redis 缓存正常读写
- ✅ Kafka 事件正常发布/消费
- ✅ APISIX 路由全部配置完成
- ✅ Prometheus 可抓取到指标

**风险**:

- ⚠️ Wire 依赖注入可能遇到循环依赖 → 提前检查依赖关系
- ⚠️ Consul 集成可能影响服务启动 → 增加降级逻辑

---

### Week 2-3: 核心服务实现 (2025-11-02 ~ 2025-11-15)

#### Knowledge Service 完善 (Go Team, 3 天)

**负责人**: [Go Dev 1]
**预计工时**: 3 天

- [ ] 🔥 **MinIO 集成** (Day 1)

  - [ ] 安装 MinIO SDK
    ```bash
    go get github.com/minio/minio-go/v7
    ```
  - [ ] 实现 MinIO Client
    ```go
    // internal/infra/storage/minio_client.go
    func (c *MinIOClient) UploadFile(key string, file io.Reader) error
    func (c *MinIOClient) DownloadFile(key string) (io.Reader, error)
    func (c *MinIOClient) GetPresignedURL(key string) (string, error)
    ```
  - [ ] 集成到上传接口
  - [ ] 验证: 文件可正常上传/下载

- [ ] 🔥 **Kafka 事件发布** (Day 2)

  - [ ] 实现 Event Publisher
    ```go
    // internal/infra/kafka/publisher.go
    func (p *Publisher) PublishDocumentUploaded(doc *Document) error
    func (p *Publisher) PublishDocumentDeleted(docID string) error
    ```
  - [ ] 集成到业务逻辑
  - [ ] 验证: 事件发送到 Kafka

- [ ] 🔥 **ClamAV 病毒扫描** (Day 3)
  - [ ] 安装 ClamAV
    ```bash
    docker-compose up -d clamav
    ```
  - [ ] 实现扫描客户端
    ```go
    // internal/infra/security/virus_scanner.go
    func (s *VirusScanner) ScanFile(file io.Reader) (bool, error)
    ```
  - [ ] 集成到上传流程
  - [ ] 验证: 病毒文件被拦截

#### Indexing Service 实现 (Python Team, 5 天)

**负责人**: [Python Lead]
**预计工时**: 5 天

- [ ] 🔥 **Kafka Consumer** (Day 1)

  - [ ] 安装依赖
    ```bash
    pip install confluent-kafka
    ```
  - [ ] 实现 Consumer

    ```python
    # app/infrastructure/kafka_consumer.py
    class DocumentEventConsumer:
        def __init__(self):
            self.consumer = Consumer({
                'bootstrap.servers': 'kafka:9092',
                'group.id': 'indexing-service',
            })

        def consume(self):
            # 订阅 document.events
    ```

  - [ ] 验证: 可消费 Kafka 消息

- [ ] 🔥 **文档解析器** (Day 2-3)

  - [ ] 安装依赖
    ```bash
    pip install pdfplumber python-docx mistune openpyxl
    ```
  - [ ] 实现解析器

    ```python
    # app/core/parsers/pdf_parser.py
    class PDFParser:
        def parse(self, file_path: str) -> str

    # app/core/parsers/word_parser.py
    # app/core/parsers/markdown_parser.py
    # app/core/parsers/excel_parser.py
    ```

  - [ ] 实现解析器工厂
    ```python
    # app/core/parsers/__init__.py
    def get_parser(file_type: str) -> Parser
    ```
  - [ ] 验证: 各类文档可正常解析

- [ ] 🔥 **向量化 + Milvus 存储** (Day 4-5)
  - [ ] 安装依赖
    ```bash
    pip install pymilvus sentence-transformers
    ```
  - [ ] 实现 Embedder
    ```python
    # app/core/embedder.py
    class BGE_M3_Embedder:
        def embed(self, texts: List[str]) -> np.ndarray
    ```
  - [ ] 实现 Milvus Client
    ```python
    # app/infrastructure/milvus_client.py
    class MilvusClient:
        def insert_vectors(self, chunks, embeddings)
    ```
  - [ ] 集成完整流程
    ```python
    # 文档解析 → 分块 → 向量化 → Milvus 存储
    ```
  - [ ] 验证: 文档可成功入库

#### Retrieval Service 完善 (Python Team, 2 天)

**负责人**: [Python Dev 1]
**预计工时**: 2 天

- [ ] 🔥 **完善 BM25 检索** (Day 1)

  - [ ] 持久化倒排索引 (使用 Redis)

    ```python
    # app/core/bm25_retriever.py
    class BM25Retriever:
        def __init__(self):
            self.redis = redis.Redis()

        def build_index(self, documents):
            # 构建倒排索引并存储到 Redis
    ```

  - [ ] 验证: BM25 检索正常

- [ ] 🔥 **Neo4j 图谱检索** (Day 2)
  - [ ] 安装依赖
    ```bash
    pip install neo4j
    ```
  - [ ] 实现图谱检索器
    ```python
    # app/core/graph_retriever.py
    class GraphRetriever:
        def retrieve_by_entity(self, entity: str) -> List[Node]
        def retrieve_community(self, entity: str) -> List[Node]
    ```
  - [ ] 验证: 图谱检索正常

#### AI Orchestrator 实现 (Go Team, 3 天)

**负责人**: [Go Dev 2]
**预计工时**: 3 天

- [ ] 🔥 **任务路由器** (Day 1)

  - [ ] 实现路由器
    ```go
    // internal/app/task_router.go
    func (r *TaskRouter) RouteTask(task *Task) (EngineClient, error) {
        switch task.Type {
        case "agent":
            return r.agentEngine, nil
        case "rag":
            return r.ragEngine, nil
        }
    }
    ```
  - [ ] 验证: 路由逻辑正确

- [ ] 🔥 **流程编排器** (Day 2)

  - [ ] 实现编排服务
    ```go
    // internal/app/orchestration_service.go
    func (s *OrchestrationService) ExecuteWorkflow(workflow *Workflow) (*Result, error) {
        // 支持串行、并行、条件分支
    }
    ```
  - [ ] 验证: 工作流执行正常

- [ ] 🔥 **gRPC 服务实现** (Day 3)
  - [ ] 实现 gRPC Service
    ```go
    // internal/service/orchestrator.go
    func (s *OrchestratorService) ProcessTask(ctx context.Context, req *pb.ProcessRequest) (*pb.ProcessResponse, error)
    ```
  - [ ] 验证: gRPC 调用正常

#### Week 2-3 验收标准

- ✅ Knowledge Service 可上传文档到 MinIO
- ✅ Kafka 事件 document.uploaded 正常发布
- ✅ Indexing Service 可消费事件并入库
- ✅ 文档可被解析、向量化、存入 Milvus
- ✅ Retrieval Service 可检索文档
- ✅ AI Orchestrator 可路由任务

**风险**:

- ⚠️ 文档解析可能失败 (格式复杂) → 增加异常处理和日志
- ⚠️ Milvus 连接不稳定 → 增加重试机制
- ⚠️ 向量化速度慢 (大文档) → 使用批处理

---

### Week 4: 基础测试与文档 (2025-11-16 ~ 2025-11-22)

#### 单元测试 (All Team, 2 天)

**负责人**: [Tech Lead]
**预计工时**: 2 天

- [ ] 🔥 **Go 服务单元测试** (1 天, Go Team)

  - [ ] Identity Service
    ```go
    // internal/biz/user_test.go
    func TestCreateUser(t *testing.T)
    func TestAuthenticate(t *testing.T)
    ```
  - [ ] Conversation Service
  - [ ] Knowledge Service
  - [ ] 目标覆盖率: ≥ 50%

- [ ] 🔥 **Python 服务单元测试** (1 天, Python Team)
  - [ ] Indexing Service
    ```python
    # tests/test_parser.py
    def test_pdf_parser()
    def test_embedder()
    ```
  - [ ] Retrieval Service
  - [ ] 目标覆盖率: ≥ 50%

#### 集成测试 (All Team, 1 天)

**负责人**: [Tech Lead]
**预计工时**: 1 天

- [ ] 🔥 **端到端文档入库流程测试**

  - [ ] 创建测试脚本
    ```python
    # tests/integration/test_document_flow.py
    def test_upload_and_index():
        # 1. 上传文档到 Knowledge Service
        # 2. 验证 Kafka 事件发布
        # 3. 等待 Indexing Service 处理
        # 4. 验证 Milvus 中存在向量
    ```
  - [ ] 验证: 测试通过

- [ ] 🔥 **端到端检索流程测试**
  - [ ] 创建测试脚本
    ```python
    # tests/integration/test_retrieval_flow.py
    def test_search_documents():
        # 1. 调用 Retrieval Service 检索
        # 2. 验证返回结果正确
    ```
  - [ ] 验证: 测试通过

#### 文档 (All Team, 2 天)

**负责人**: [Tech Lead]
**预计工时**: 2 天

- [ ] 🔥 **API 文档完善** (1 天)

  - [ ] 更新 `api/openapi.yaml`
  - [ ] 补充所有接口描述、示例
  - [ ] 生成 Swagger UI
  - [ ] 验证: 文档可访问

- [ ] 🔥 **Runbook 初版** (1 天)
  - [ ] 创建核心服务 Runbook
    ```
    docs/runbook/
    ├── identity-service.md
    ├── conversation-service.md
    ├── knowledge-service.md
    ├── indexing-service.md
    └── retrieval-service.md
    ```
  - [ ] 包含: 启动/停止、健康检查、常见故障
  - [ ] 验证: Runbook 可用

#### Week 4 验收标准

- ✅ 单元测试覆盖率 ≥ 50%
- ✅ 集成测试通过
- ✅ API 文档完善
- ✅ Runbook 初版完成

**Phase 1 总验收标准**:

- ✅ 所有 A 级技术债务清零
- ✅ 核心文档入库流程打通
- ✅ 核心检索流程打通
- ✅ 所有服务健康运行
- ✅ 测试覆盖率 ≥ 50%
- ✅ 基础文档完善

**Go/No-Go 决策**:

- ✅ 如果以上全部满足 → 进入 Phase 2
- ❌ 如果有任何项未满足 → 延期 Phase 2，继续修复

---

## Phase 2: 功能完善 (6 周)

**目标**: 核心功能完整 (GraphRAG、Agent、Voice)

### Week 5-6: GraphRAG 增强 (2025-11-23 ~ 2025-12-06)

#### Indexing 增强 - Neo4j 图谱构建 (Python Team, 3 天)

**负责人**: [Python Lead]
**预计工时**: 3 天

- [ ] 🔥 **实体识别 (NER)** (Day 1)

  - [ ] 安装依赖
    ```bash
    pip install spacy
    python -m spacy download zh_core_web_sm
    ```
  - [ ] 实现 NER
    ```python
    # app/core/ner/entity_extractor.py
    class EntityExtractor:
        def extract(self, text: str) -> List[Entity]
    ```

- [ ] 🔥 **关系抽取** (Day 1)

  - [ ] 实现关系抽取器
    ```python
    # app/core/ner/relation_extractor.py
    class RelationExtractor:
        def extract(self, text: str, entities: List[Entity]) -> List[Relation]
    ```

- [ ] 🔥 **图谱构建** (Day 2)

  - [ ] 实现图谱构建器
    ```python
    # app/core/graph_builder.py
    class GraphBuilder:
        def build_graph(self, document_id: str, entities, relations)
    ```

- [ ] 🔥 **社区检测** (Day 3)
  - [ ] 安装依赖
    ```bash
    pip install python-louvain
    ```
  - [ ] 实现社区检测
    ```python
    # app/core/community_detector.py
    class CommunityDetector:
        def detect(self, graph) -> List[Community]
    ```

#### Retrieval 增强 - 查询改写 (Python Team, 2 天)

**负责人**: [Python Dev 1]
**预计工时**: 2 天

- [ ] 🔥 **HyDE (Hypothetical Document Embeddings)** (Day 1)

  - [ ] 实现 HyDE
    ```python
    # app/core/query_rewriter.py
    class HyDERewriter:
        def rewrite(self, query: str) -> List[str]:
            # 生成假设性文档
    ```

- [ ] 🔥 **Multi-Query** (Day 1)

  - [ ] 实现多查询生成
    ```python
    class MultiQueryRewriter:
        def rewrite(self, query: str) -> List[str]:
            # 生成多个查询变体
    ```

- [ ] 🔥 **Step-back Prompting** (Day 2)
  - [ ] 实现 Step-back
    ```python
    class StepBackRewriter:
        def rewrite(self, query: str) -> str:
            # 生成更抽象的查询
    ```

#### Week 5-6 验收标准

- ✅ Neo4j 图谱可正常构建
- ✅ 实体和关系正确抽取
- ✅ 社区检测正常运行
- ✅ 查询改写提升检索效果 (准确率 +5%)

---

### Week 7-8: Agent 系统完整实现 (2025-12-07 ~ 2025-12-20)

#### LangGraph 工作流 (Python Team, 5 天)

**负责人**: [Python Lead]
**预计工时**: 5 天

- [ ] 🔥 **ReAct 模式** (Day 1-2)

  - [ ] 安装依赖
    ```bash
    pip install langgraph
    ```
  - [ ] 实现 Agent 状态
    ```python
    # app/core/agent/state.py
    class AgentState(TypedDict):
        messages: List[Message]
        next_step: str
        tools_used: List[str]
    ```
  - [ ] 实现 Planner Node
    ```python
    # app/core/agent/nodes.py
    def planner_node(state: AgentState) -> AgentState:
        # 规划任务
    ```
  - [ ] 实现 Executor Node
  - [ ] 实现 Reflector Node

- [ ] 🔥 **工作流组装** (Day 3)

  - [ ] 创建 LangGraph
    ```python
    # app/core/agent/workflow.py
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("reflector", reflector_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")
    workflow.add_conditional_edges("executor", should_reflect)
    ```

- [ ] 🔥 **工具注册表** (Day 4-5)
  - [ ] 实现工具注册表
    ```python
    # app/core/tools/registry.py
    class ToolRegistry:
        def register(self, tool: Tool)
        def get_tool(self, name: str) -> Tool
    ```
  - [ ] 实现内置工具
    - [ ] SearchTool (联网搜索)
    - [ ] CalculatorTool (计算器)
    - [ ] CodeInterpreterTool (代码执行)
    - [ ] DatabaseTool (数据库查询)
    - [ ] ... (50+ 工具)

#### 记忆管理 (Python Team, 1 天)

**负责人**: [Python Dev 1]
**预计工时**: 1 天

- [ ] 🔥 **短期记忆** (Day 1)

  - [ ] 实现对话记忆
    ```python
    # app/core/memory/conversation_history.py
    class ConversationHistory:
        def add_turn(self, user_msg, assistant_msg)
        def get_context(self, max_turns=10) -> str
    ```

- [ ] 🔥 **长期记忆** (Day 1)
  - [ ] 实现向量记忆
    ```python
    # app/core/memory/vector_memory.py
    class VectorMemory:
        def add(self, memory: Memory)
        def search(self, query: str) -> List[Memory]
    ```

#### Week 7-8 验收标准

- ✅ LangGraph 工作流正常运行
- ✅ Agent 可调用工具
- ✅ 记忆管理正常
- ✅ ReAct 模式完整实现

---

### Week 9-10: Voice 实时优化 (2025-12-21 ~ 2026-01-03)

#### ASR/TTS/VAD 集成 (Python Team, 5 天)

**负责人**: [Python Team]
**预计工时**: 5 天

- [ ] 🔥 **Whisper ASR** (Day 1-2)

  - [ ] 安装依赖
    ```bash
    pip install openai-whisper
    ```
  - [ ] 实现 ASR
    ```python
    # app/core/asr/whisper_asr.py
    class WhisperASR:
        def transcribe(self, audio_file: str) -> str
        def transcribe_stream(self, audio_stream) -> Iterator[str]
    ```

- [ ] 🔥 **Edge TTS** (Day 3)

  - [ ] 安装依赖
    ```bash
    pip install edge-tts
    ```
  - [ ] 实现 TTS
    ```python
    # app/core/tts/edge_tts.py
    class EdgeTTS:
        async def synthesize(self, text: str) -> bytes
        async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]
    ```

- [ ] 🔥 **Silero VAD** (Day 4)

  - [ ] 安装依赖
    ```bash
    pip install torch
    ```
  - [ ] 实现 VAD
    ```python
    # app/core/vad/silero_vad.py
    class SileroVAD:
        def detect_speech(self, audio: np.ndarray) -> List[Tuple[float, float]]
    ```

- [ ] 🔥 **WebRTC 集成** (Day 5)
  - [ ] 安装依赖
    ```bash
    pip install aiortc
    ```
  - [ ] 实现 WebRTC Handler
    ```python
    # app/api/webrtc_handler.py
    class WebRTCHandler:
        async def offer(self, sdp: str) -> str
    ```

#### Week 9-10 验收标准

- ✅ ASR 识别准确率 ≥ 95%
- ✅ TTS 延迟 < 100ms
- ✅ VAD 准确率 ≥ 95%
- ✅ WebRTC 连接稳定

---

## Phase 3: 体验优化 (4 周)

**目标**: 生产可用，性能达标

### Week 11-12: 多模态集成 (略)

### Week 13: 性能调优 (略)

### Week 14: 安全加固 (略)

---

## Phase 4: 生态建设 (4 周)

**目标**: 平台化

### Week 15-16: 开放平台 API (略)

### Week 17-18: 插件系统 (略)

---

## 📊 进度追踪

### 整体进度

| Phase    | 预计周数  | 已完成周数 | 进度   | 状态      |
| -------- | --------- | ---------- | ------ | --------- |
| Phase 1  | 4 周      | 0 周       | 0%     | ❌ 未开始 |
| Phase 2  | 6 周      | 0 周       | 0%     | ❌ 未开始 |
| Phase 3  | 4 周      | 0 周       | 0%     | ❌ 未开始 |
| Phase 4  | 4 周      | 0 周       | 0%     | ❌ 未开始 |
| **总计** | **18 周** | **0 周**   | **0%** | ❌        |

### 本周进度 (Week 1)

| 任务                     | 负责人        | 预计工时 | 实际工时 | 状态 |
| ------------------------ | ------------- | -------- | -------- | ---- |
| Wire 依赖注入            | [Go Lead]     | 1 天     | -        | ❌   |
| Consul 服务发现          | [Go Lead]     | 1 天     | -        | ❌   |
| Redis 缓存               | [Go Dev]      | 1 天     | -        | ❌   |
| Kafka Event Schema       | [Go Lead]     | 1 天     | -        | ❌   |
| Event Publisher/Consumer | [Go + Python] | 1 天     | -        | ❌   |
| APISIX 配置              | [Go Lead]     | 2 天     | -        | ❌   |

### 风险与阻塞

| 风险/阻塞 | 严重程度 | 影响 | 缓解措施 | 状态 |
| --------- | -------- | ---- | -------- | ---- |
| -         | -        | -    | -        | -    |

---

## 📅 每日站会记录

### 2025-10-26 (Day 1)

**参会人**: [团队成员]

**昨日完成**:

- -

**今日计划**:

- [Go Team] 启动 Wire 依赖注入生成
- [Python Team] 研究 LangGraph 文档

**阻塞问题**:

- -

---

## 🎯 里程碑检查点

### Milestone 1: Phase 1 完成 (Week 4)

**日期**: 2025-11-22
**检查项**:

- [ ] 所有 A 级技术债务清零
- [ ] 核心文档入库流程打通
- [ ] 核心检索流程打通
- [ ] 测试覆盖率 ≥ 50%
- [ ] 基础文档完善

**决策**: Go / No-Go 进入 Phase 2

### Milestone 2: Phase 2 完成 (Week 10)

**日期**: 2026-01-03
**检查项**:

- [ ] GraphRAG 增强完成
- [ ] Agent 系统完整实现
- [ ] Voice 实时优化完成
- [ ] 性能指标达标

**决策**: Go / No-Go 进入 Phase 3

---

## 📞 联系方式

- **项目负责人**: [Your Name] - [Email]
- **技术负责人**: [Tech Lead] - [Email]
- **Slack 频道**: #voicehelper-dev
- **紧急联系**: [Phone]

---

**最后更新**: 2025-10-26
**更新人**: [Your Name]
**下次更新**: 2025-10-27 (每日更新)
