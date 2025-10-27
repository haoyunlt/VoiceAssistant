# VoiceAssistant 架构概览

## 系统架构图

```mermaid
graph TB
    subgraph "外部访问"
        Client[客户端]
        WebApp[Web应用]
    end

    subgraph "Istio Service Mesh"
        Gateway[Istio Gateway]

        subgraph "API Gateway Layer"
            IstioProxy[Envoy Proxy]
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
        Jaeger[Jaeger<br/>链路追踪]
        Kiali[Kiali<br/>服务网格]
    end

    subgraph "外部服务"
        LLM[LLM APIs<br/>OpenAI/Claude等]
        Azure[Azure Speech<br/>语音服务]
    end

    Client --> Gateway
    WebApp --> Gateway
    Gateway --> IstioProxy

    IstioProxy --> Identity
    IstioProxy --> Conversation
    IstioProxy --> Knowledge
    IstioProxy --> AIOrch
    IstioProxy --> Voice

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

    Prometheus --> Grafana
    Jaeger -.追踪.-> Identity
    Jaeger -.追踪.-> Conversation
    Jaeger -.追踪.-> AIOrch
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

### 2. RAG 检索-重排流程

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

### 3. 工具调用流程

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

### 基础设施

- **Nacos**: 配置中心和服务发现
- **PostgreSQL**: 业务数据持久化
- **Redis**: 缓存和会话存储
- **Milvus**: 向量数据库
- **Elasticsearch**: 全文检索
- **MinIO**: 对象存储（文档、多媒体）

## 部署架构

### Kubernetes + Istio

- **命名空间隔离**:

  - `voiceassistant-prod`: 应用服务
  - `voiceassistant-infra`: 基础设施
  - `istio-system`: Istio 组件

- **流量管理**:

  - Istio Gateway 统一入口
  - VirtualService 路由规则
  - DestinationRule 负载均衡

- **安全**:

  - mTLS 服务间加密
  - JWT 认证
  - RBAC 授权策略
  - Network Policy 网络隔离

- **可观测性**:
  - Prometheus 指标采集
  - Jaeger 分布式追踪
  - Grafana 可视化
  - Kiali 服务网格监控

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
