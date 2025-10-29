# VoiceHelper 架构概览

## 系统架构图

```mermaid
graph TB
    subgraph "外部访问"
        Client[客户端]
        WebApp[Web应用]
    end

    subgraph "API Gateway (Istio + Envoy)"
        Gateway[Istio Gateway<br/>统一入口]

        subgraph "Gateway Features"
            RoutePlugin[VirtualService & EnvoyFilter<br/>限流/JWT/mTLS]
        end

        subgraph "Go Services"
            Identity[Identity Service<br/>认证/授权]
            Conversation[Conversation Service<br/>对话管理]
            Knowledge[Knowledge Service<br/>知识管理]
            AIOrch[AI Orchestrator<br/>AI编排]
            ModelRouter[Model Router<br/>模型路由]
            Notification[Notification Service<br/>通知]
            Analytics[Analytics Service<br/>分析]
        end

        subgraph "Python AI Services"
            Agent[Agent Engine<br/>智能体引擎]
            RAG[RAG Engine<br/>检索增强]
            Voice[Voice Engine<br/>语音处理]
            ModelAdapter[Model Adapter<br/>模型适配]
            Retrieval[Retrieval Service<br/>检索服务]
            Indexing[Indexing Service<br/>索引服务]
            Multimodal[Multimodal Engine<br/>多模态]
            VectorAdapter[Vector Store Adapter<br/>向量存储适配]
        end
    end

    subgraph "基础设施服务"
        Postgres[(PostgreSQL<br/>关系数据库)]
        Redis[(Redis<br/>缓存)]
        Milvus[(Milvus<br/>向量数据库)]
        ES[(Elasticsearch<br/>全文搜索)]
        Nacos[Nacos<br/>配置中心]
        MinIO[(MinIO<br/>对象存储)]
    end

    subgraph "可观测性"
        Prometheus[Prometheus<br/>指标]
        Grafana[Grafana<br/>可视化]
        OTel[OpenTelemetry<br/>链路追踪]
        Kafka[Kafka<br/>日志收集]
    end

    subgraph "外部服务"
        LLM[LLM APIs<br/>OpenAI/Claude等]
        Azure[Azure Speech<br/>语音服务]
    end

    Client --> Gateway
    WebApp --> Gateway
    Gateway --> RoutePlugin

    RoutePlugin --> Identity
    RoutePlugin --> Conversation
    RoutePlugin --> Knowledge
    RoutePlugin --> AIOrch
    RoutePlugin --> Voice

    Identity --> Postgres
    Identity --> Redis

    Conversation --> Postgres
    Conversation --> Redis
    Conversation --> AIOrch

    Knowledge --> Postgres
    Knowledge --> Retrieval
    Knowledge --> Indexing

    AIOrch --> Agent
    AIOrch --> RAG
    AIOrch --> ModelRouter

    Agent --> RAG
    Agent --> ModelAdapter

    RAG --> Retrieval
    RAG --> Milvus

    Retrieval --> Milvus
    Retrieval --> ES
    Retrieval --> VectorAdapter

    Indexing --> Milvus
    Indexing --> MinIO

    ModelAdapter --> LLM
    Voice --> Azure

    VectorAdapter --> Milvus

    Identity -.配置.-> Nacos
    Conversation -.配置.-> Nacos
    Knowledge -.配置.-> Nacos
    Agent -.配置.-> Nacos

    Identity -.指标.-> Prometheus
    Conversation -.指标.-> Prometheus
    AIOrch -.指标.-> Prometheus
    Agent -.指标.-> Prometheus
    Gateway -.指标.-> Prometheus

    Prometheus --> Grafana
    Gateway -.追踪.-> OTel
    Identity -.追踪.-> OTel
    Conversation -.追踪.-> OTel
    AIOrch -.追踪.-> OTel

    Gateway -.日志.-> Kafka
```

## 关键时序图

### 1. 语音对话流程

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant Voice
    participant AIOrch
    participant Agent
    participant RAG
    participant ModelAdapter
    participant LLM

    Client->>Gateway: WebSocket连接
    Gateway->>Voice: 建立语音流

    Client->>Voice: 语音数据流
    Voice->>Voice: VAD检测
    Voice->>Voice: ASR转文字

    Voice->>AIOrch: 文本消息
    AIOrch->>Agent: 处理请求

    Agent->>RAG: 检索上下文
    RAG-->>Agent: 相关知识

    Agent->>ModelAdapter: LLM推理
    ModelAdapter->>LLM: API调用
    LLM-->>ModelAdapter: 响应
    ModelAdapter-->>Agent: 生成结果

    Agent-->>AIOrch: 处理结果
    AIOrch-->>Voice: 文本响应

    Voice->>Voice: TTS合成
    Voice->>Client: 语音流输出
```

### 2. A/B测试模型路由流程

```mermaid
sequenceDiagram
    participant Client
    participant Gateway
    participant ModelRouter
    participant ABTestSvc
    participant Cache
    participant DB
    participant ModelAdapter

    Client->>Gateway: 路由请求 (user_id, enable_ab_test)
    Gateway->>ModelRouter: 转发请求

    alt A/B测试已启用
        ModelRouter->>ABTestSvc: SelectVariant(test_id, user_id)
        ABTestSvc->>Cache: GetUserVariant(test_id, user_id)

        alt 缓存命中
            Cache-->>ABTestSvc: 返回已缓存变体
        else 缓存未命中
            ABTestSvc->>DB: GetTest(test_id)
            DB-->>ABTestSvc: 测试配置
            ABTestSvc->>ABTestSvc: 应用分流策略
            ABTestSvc->>Cache: SetUserVariant (TTL: 24h)
        end

        ABTestSvc-->>ModelRouter: 选中的变体
        ModelRouter->>ModelRouter: GetModel(variant.model_id)
    else 常规路由
        ModelRouter->>ModelRouter: 应用路由策略 (cheapest/fastest)
    end

    ModelRouter->>ModelAdapter: 调用模型
    ModelAdapter-->>ModelRouter: 模型响应

    opt 记录A/B测试指标
        ModelRouter->>ABTestSvc: RecordMetric (success, latency, cost)
        ABTestSvc->>DB: 插入指标记录
    end

    ModelRouter-->>Gateway: 响应 + 元数据
    Gateway-->>Client: 最终响应
```

### 3. RAG 检索-重排流程（v2.0 优化版）

```mermaid
sequenceDiagram
    participant Agent
    participant Router as Query Router
    participant Cache as Semantic Cache
    participant RAG as RAG Engine
    participant Vector as Vector Search
    participant BM25 as BM25 Search
    participant Graph as Graph RAG
    participant Rerank as Cross-Encoder
    participant LLM
    participant SelfCheck as Self-Checker

    Agent->>Router: 复杂查询请求
    Router->>Router: 分析查询类型 & 复杂度
    Router->>Cache: 检查语义缓存 (FAISS)

    alt 缓存命中 (相似度>0.92)
        Cache-->>Agent: 返回缓存结果
    else 缓存未命中
        Router->>RAG: 路由到最优策略

        alt 简单事实查询
            RAG->>Vector: 向量检索 (Top-20)
        else 复杂多跳查询
            par 并行检索
                RAG->>Vector: 向量检索 (Top-20)
                Vector->>Vector: Dense Retrieval
            and
                RAG->>BM25: 稀疏检索 (Top-20)
                BM25->>BM25: BM25 算法
            and
                RAG->>Graph: 图谱路径查询 (2-3跳)
                Graph->>Graph: BFS/DFS 遍历
            end
        end

        Vector-->>RAG: 向量结果
        BM25-->>RAG: 关键词结果
        Graph-->>RAG: 图谱结果

        RAG->>RAG: RRF 融合 (Reciprocal Rank Fusion)
        RAG->>Rerank: Cross-Encoder 重排 (Batch)
        Rerank-->>RAG: Top-5 精排结果

        alt 启用上下文压缩 (Iter 3)
            RAG->>RAG: LLMLingua 压缩 (保留50%)
        end

        RAG->>RAG: 构建上下文 + 引用标注
        RAG->>LLM: 生成答案
        LLM-->>SelfCheck: 初步答案

        alt Self-RAG 启用 (Iter 3)
            SelfCheck->>SelfCheck: 幻觉检测 (NLI)
            alt 检测到幻觉
                SelfCheck->>LLM: 重新生成（增强 Prompt）
                LLM-->>SelfCheck: 修正答案
            end
        end

        SelfCheck->>Cache: 缓存结果 (TTL=1h)
        SelfCheck-->>Agent: 最终答案 + 引用来源
    end
```

**优化亮点**：
- ✅ 混合检索（Vector + BM25 + Graph）
- ✅ 语义缓存（命中率 60%+）
- ✅ Cross-Encoder 重排
- ✅ Self-RAG 自我纠错
- ✅ 上下文压缩（节省 Token 30%）

### 4. 工具调用流程

```mermaid
sequenceDiagram
    participant Agent
    participant PlanExecutor
    participant ToolService
    participant ExternalAPI
    participant Memory

    Agent->>PlanExecutor: 复杂任务
    PlanExecutor->>PlanExecutor: 任务分解

    loop 执行计划步骤
        PlanExecutor->>ToolService: 调用工具
        ToolService->>ExternalAPI: 外部API
        ExternalAPI-->>ToolService: 结果
        ToolService-->>PlanExecutor: 执行结果

        PlanExecutor->>Memory: 存储中间结果
        PlanExecutor->>PlanExecutor: 评估是否继续
    end

    PlanExecutor-->>Agent: 最终结果
    Agent->>Memory: 更新上下文
```

## 核心组件说明

### Go 服务层

- **Identity Service** ([`cmd/identity-service/`](../../cmd/identity-service/))

  - JWT 认证/授权
  - 用户管理
  - RBAC 权限控制

- **Conversation Service** ([`cmd/conversation-service/`](../../cmd/conversation-service/))

  - 对话会话管理
  - 消息持久化
  - 上下文压缩

- **Knowledge Service** ([`cmd/knowledge-service/`](../../cmd/knowledge-service/))

  - 知识库管理
  - 文档管理
  - 向量索引协调

- **AI Orchestrator** ([`cmd/ai-orchestrator/`](../../cmd/ai-orchestrator/))
  - AI 服务编排
  - 请求路由
  - 服务聚合

### Python AI 服务层

- **Agent Engine** ([`algo/agent-engine/`](../../algo/agent-engine/))

  - ReAct/Plan-Execute 智能体
  - 工具调用
  - 多智能体协作

- **RAG Engine** ([`algo/rag-engine/`](../../algo/rag-engine/))

  - **v2.0 架构** ([优化迭代计划](../RAG_ENGINE_ITERATION_PLAN.md))
  - 多策略检索（Vector + BM25 + Graph）
  - 查询重写/分解
  - Cross-Encoder 重排
  - Self-RAG 自我纠错
  - 语义缓存（FAISS + Redis）
  - 上下文压缩（LLMLingua）
  - Agentic RAG（计划中）

- **Voice Engine** ([`algo/voice-engine/`](../../algo/voice-engine/))

  - VAD 语音检测
  - ASR 语音识别
  - TTS 语音合成

- **Model Adapter** ([`algo/model-adapter/`](../../algo/model-adapter/))
  - 统一 LLM 接口
  - 多模型适配（OpenAI/Claude/通义等）
  - 流式响应

- **Model Router** ([`cmd/model-router/`](../../cmd/model-router/))
  - 智能模型路由（成本/延迟/质量优化）
  - A/B测试管理
  - 模型健康检查与熔断
  - 成本预测与预算控制

### 基础设施

- **Nacos**: 配置中心和服务发现
- **PostgreSQL**: 业务数据持久化
- **Redis**: 缓存和会话存储
- **Milvus**: 向量数据库
- **Elasticsearch**: 全文检索
- **MinIO**: 对象存储（文档、多媒体）

## 部署架构

### Kubernetes + Istio Service Mesh

> **架构演进**: 已从 APISIX 迁移到 Istio Gateway + Envoy，实现服务网格架构

- **命名空间隔离**:

  - `voiceassistant-prod`: 应用服务（Sidecar 自动注入）
  - `voiceassistant-infra`: 基础设施
  - `istio-system`: Istio 控制平面与 Ingress Gateway

- **流量管理 (Istio)**:

  - Istio Gateway: 外部流量入口（HTTP/HTTPS/gRPC/WebSocket）
  - VirtualService: 路由规则（URI、Header、权重路由）
  - DestinationRule: 流量策略（负载均衡、连接池、熔断）
  - EnvoyFilter: 高级功能（限流、认证、压缩、日志）
  - Sidecar 模式：每个服务 Pod 注入 Envoy 代理

- **安全**:

  - PeerAuthentication: 服务间 mTLS（STRICT 模式，零信任）
  - RequestAuthentication: JWT 验证（多 Issuer 支持）
  - AuthorizationPolicy: 细粒度授权（Namespace、ServiceAccount、JWT Claims）
  - Deny by Default: 默认拒绝策略 + 显式授权
  - 租户隔离: 基于 JWT tenant_id 的访问控制
  - PII 数据脱敏: 日志自动脱敏

- **可观测性**:

  - OpenTelemetry: 全链路追踪（服务间调用链完整）
  - Prometheus: 指标采集（Istio Metrics + Envoy Stats）
  - Grafana: Istio 官方 Dashboard（Mesh/Service/Workload）
  - JSON Access Log: 结构化日志（租户/用户/会话 ID）
  - ServiceMonitor: 自动发现和采集

- **性能与可靠性**:

  - HPA 自动扩缩容（Gateway 3-10 副本，Istiod 2-5 副本）
  - 连接池优化（HTTP/1.1 + HTTP/2）
  - 熔断与重试（OutlierDetection）
  - 流量分割与金丝雀发布（基于权重）
  - Redis 分布式限流

### Istio vs APISIX 对比

| 维度 | APISIX | Istio + Envoy | 说明 |
|------|--------|---------------|------|
| **架构** | 集中式网关 | Sidecar 模式 | Istio 实现服务级流量控制 |
| **资源消耗** | 低（~1.5GB） | 高（~15GB+） | Istio 每服务额外 Sidecar |
| **配置方式** | Route/Upstream | Gateway/VirtualService/DestinationRule | Istio Kubernetes 原生 |
| **插件生态** | 80+ 内置插件 | Envoy Filter + 社区生态 | Istio 是云原生标准 |
| **性能** | 优秀（低延迟） | 好（+5-10ms） | Sidecar 有额外开销 |
| **学习曲线** | 平缓 | 陡峭 | Istio 概念更多 |
| **可观测性** | 网关层面 | 服务间全链路 | Istio 完整调用链追踪 |
| **安全** | mTLS + JWT + WAF | mTLS + RBAC + JWT | Istio 零信任架构 |
| **流量管理** | 路由规则 | VirtualService + DestinationRule | Istio 更细粒度控制 |
| **多集群** | 有限支持 | 原生多集群联邦 | Istio 跨集群流量管理 |

**迁移文档**: [`deployments/k8s/istio/MIGRATION_GUIDE.md`](../../deployments/k8s/istio/MIGRATION_GUIDE.md)

## NFR 指标

### 系统级指标

| 指标            | 目标值  | 当前值 | 状态   |
| --------------- | ------- | ------ | ------ |
| API Gateway P95 | < 200ms | -      | 待测试 |
| TTFB (Stream)   | < 300ms | -      | 待测试 |
| E2E QA          | < 2.5s  | -      | 待测试 |
| 可用性          | ≥ 99.9% | -      | 待测试 |
| 并发 RPS        | ≥ 1000  | -      | 待测试 |

### RAG Engine 专项指标 (v2.0 目标)

| 指标类别 | 指标名称 | v1.0 当前值 | v2.0 目标值 | 提升幅度 |
|---------|---------|------------|------------|---------|
| **准确性** | 检索召回率@5 | 0.68 | 0.85+ | +25% |
| **准确性** | 答案准确率 | 0.71 | 0.90+ | +27% |
| **准确性** | 幻觉率 | 15% | <5% | -67% |
| **性能** | E2E 延迟 P95 | 3200ms | <2500ms | -22% |
| **性能** | 检索延迟 P95 | 800ms | <500ms | -38% |
| **成本** | 平均 Token 消耗 | 2450 | <2000 | -18% |
| **体验** | 缓存命中率 | 20% | 60%+ | +200% |

**详细优化计划**: [RAG Engine 迭代计划](../RAG_ENGINE_ITERATION_PLAN.md)

## 扩展性

- **水平扩展**: HPA 自动扩缩容
- **垂直扩展**: VPA 资源调整
- **数据库**: 读写分离、分片
- **缓存**: Redis 集群、多级缓存
- **向量库**: Milvus 分布式集群

## 参考链接

- [部署指南](../../deployments/k8s/README.md)
- [Runbook](../runbook/index.md)
- [API 文档](../../api/openapi.yaml)
- [SLO 目标](../nfr/slo.md)
