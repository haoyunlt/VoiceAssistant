# VoiceAssistant 架构概览

## 系统架构图

```mermaid
graph TB
    subgraph "外部访问"
        Client[客户端]
        WebApp[Web应用]
    end

    subgraph "API Gateway (APISIX)"
        Gateway[APISIX Gateway<br/>统一入口]

        subgraph "Gateway Features"
            RoutePlugin[路由 & 插件<br/>限流/JWT/mTLS]
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

### 3. RAG 检索-重排流程

```mermaid
sequenceDiagram
    participant Agent
    participant RAG
    participant Retrieval
    participant VectorStore
    participant ES
    participant Rerank

    Agent->>RAG: 查询请求
    RAG->>RAG: 查询重写/扩展

    par 并行检索
        RAG->>Retrieval: 向量检索
        Retrieval->>VectorStore: 语义搜索
        VectorStore-->>Retrieval: Top-K结果
    and
        RAG->>Retrieval: 关键词检索
        Retrieval->>ES: BM25搜索
        ES-->>Retrieval: Top-K结果
    end

    Retrieval->>Retrieval: 混合融合
    Retrieval->>Rerank: 重排序
    Rerank-->>Retrieval: 精排结果

    Retrieval-->>RAG: 最终Top-N
    RAG->>RAG: 构建上下文
    RAG-->>Agent: 增强上下文
```

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

  - 检索增强生成
  - 查询重写
  - 上下文构建

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

### Kubernetes + APISIX Gateway

> **架构演进**: 已从 Istio/Envoy 迁移到 APISIX，实现更轻量级的网关架构

- **命名空间隔离**:

  - `voiceassistant-prod`: 应用服务
  - `voiceassistant-infra`: 基础设施
  - `apisix`: APISIX 网关

- **流量管理 (APISIX)**:

  - APISIX Gateway 统一入口（替代 Istio Gateway + Envoy）
  - Routes 路由规则（对应 Istio VirtualService）
  - Upstreams 负载均衡和健康检查（对应 Istio DestinationRule）
  - 支持 HTTP/HTTPS、WebSocket、gRPC
  - Kubernetes 服务发现

- **安全**:

  - mTLS 服务间加密（APISIX Upstream TLS）
  - JWT 认证（jwt-auth 插件）
  - RBAC 授权策略（APISIX RBAC）
  - WAF 防护（自定义规则）
  - PII 数据脱敏
  - IP 限流和租户限流

- **可观测性**:

  - OpenTelemetry 全链路追踪（替代 Jaeger）
  - Prometheus 指标采集（APISIX metrics exporter）
  - Grafana Dashboard 可视化
  - Kafka 日志收集（access log + error log）
  - 自定义告警规则

- **性能优化**:

  - 无 Sidecar 开销（~90% 内存节省）
  - HPA 自动扩缩容（3-10 副本）
  - 连接池和 keepalive 优化
  - Redis 集群限流缓存

### APISIX vs Istio 对比

| 维度 | Istio/Envoy | APISIX | 说明 |
|------|-------------|--------|------|
| **架构** | Sidecar 模式 | 集中式网关 | APISIX 无 Sidecar 开销 |
| **资源消耗** | 高（每 Pod 1 Sidecar） | 低（共享网关） | ~90% 内存节省 |
| **配置方式** | CRD (Gateway/VirtualService) | Route/Upstream | APISIX 更直观 |
| **插件生态** | Envoy Filter | 80+ 内置插件 | APISIX 插件更丰富 |
| **性能** | 好 | 优秀 | APISIX 延迟更低 |
| **学习曲线** | 陡峭 | 平缓 | APISIX 更易上手 |
| **可观测性** | Istio Telemetry | OpenTelemetry + Prometheus | 功能对等 |
| **安全** | mTLS + RBAC | mTLS + JWT + WAF | APISIX 更全面 |

**迁移文档**: [`deployments/k8s/apisix/README.md`](../../deployments/k8s/apisix/README.md)

## NFR 指标

| 指标            | 目标值  | 当前值 | 状态   |
| --------------- | ------- | ------ | ------ |
| API Gateway P95 | < 200ms | -      | 待测试 |
| TTFB (Stream)   | < 300ms | -      | 待测试 |
| E2E QA          | < 2.5s  | -      | 待测试 |
| 可用性          | ≥ 99.9% | -      | 待测试 |
| 并发 RPS        | ≥ 1000  | -      | 待测试 |

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
