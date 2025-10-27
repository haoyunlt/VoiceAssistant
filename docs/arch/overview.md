# VoiceAssistant 微服务架构概览

## 系统架构

VoiceAssistant 是一个基于微服务架构的 AI 语音助手平台，采用 Go 和 Python 混合技术栈，支持大规模并发和高可用性。

### 架构组件图

```mermaid
graph TB
    %% 客户端层
    Client[客户端/Web/移动端] --> Gateway[API Gateway<br/>APISIX]

    %% API网关层
    Gateway --> LB{负载均衡<br/>服务发现}

    %% Go核心服务
    LB --> Identity[Identity Service<br/>认证授权]
    LB --> Conversation[Conversation Service<br/>会话管理]
    LB --> Knowledge[Knowledge Service<br/>知识管理]
    LB --> Orchestrator[AI Orchestrator<br/>任务编排]
    LB --> ModelRouter[Model Router<br/>模型路由]
    LB --> Notification[Notification Service<br/>通知服务]
    LB --> Analytics[Analytics Service<br/>分析服务]

    %% Python AI引擎
    Orchestrator --> Agent[Agent Engine<br/>智能体引擎]
    Orchestrator --> RAG[RAG Engine<br/>检索增强生成]
    Orchestrator --> Voice[Voice Engine<br/>语音处理]
    Orchestrator --> Multimodal[Multimodal Engine<br/>多模态处理]

    %% AI基础服务
    RAG --> Retrieval[Retrieval Service<br/>检索服务]
    RAG --> ModelAdapter[Model Adapter<br/>模型适配]
    Knowledge --> Indexing[Indexing Service<br/>索引服务]
    Retrieval --> VectorStore[Vector Store Adapter<br/>向量存储适配]

    %% 数据存储层
    Identity --> DB[(PostgreSQL<br/>关系数据库)]
    Conversation --> DB
    Knowledge --> DB
    VectorStore --> Milvus[(Milvus<br/>向量数据库)]
    Agent --> Redis[(Redis<br/>缓存/会话)]

    %% 服务发现与配置
    LB --> Consul[Consul<br/>服务发现]
    Gateway --> Consul

    %% 消息队列
    Notification --> Kafka[Kafka/NATS<br/>消息队列]
    Analytics --> Kafka

    %% 可观测性
    Gateway -.-> Prometheus[Prometheus<br/>指标]
    Identity -.-> Prometheus
    Conversation -.-> Prometheus
    Gateway -.-> Jaeger[Jaeger<br/>追踪]
    Identity -.-> Jaeger

    %% 存储
    Voice --> MinIO[(MinIO<br/>对象存储)]
    Multimodal --> MinIO

    style Gateway fill:#ff6b6b
    style Orchestrator fill:#4ecdc4
    style Agent fill:#95e1d3
    style RAG fill:#95e1d3
    style DB fill:#ffd93d
    style Milvus fill:#ffd93d
    style Redis fill:#ffd93d
```

### 关键时序图

#### 1. 语音对话流程

```mermaid
sequenceDiagram
    participant C as 客户端
    participant G as API Gateway
    participant Conv as Conversation Service
    participant Orch as AI Orchestrator
    participant Voice as Voice Engine
    participant Agent as Agent Engine
    participant RAG as RAG Engine
    participant Model as Model Adapter

    C->>G: 1. 发送语音 (WebSocket)
    G->>Conv: 2. 创建会话
    Conv-->>G: 会话ID

    G->>Orch: 3. 提交语音任务
    Orch->>Voice: 4. ASR转文本
    Voice-->>Orch: 文本内容

    Orch->>Agent: 5. 智能体处理
    Agent->>RAG: 6. 检索相关知识
    RAG-->>Agent: 知识上下文

    Agent->>Model: 7. LLM生成回复
    Model-->>Agent: 生成内容
    Agent-->>Orch: 处理结果

    Orch->>Voice: 8. TTS语音合成
    Voice-->>Orch: 语音文件
    Orch-->>G: 9. 返回结果
    G-->>C: 10. 推送语音 (Stream)

    G->>Conv: 11. 保存对话历史
```

#### 2. RAG 检索-重排流程

```mermaid
sequenceDiagram
    participant C as 客户端
    participant RAG as RAG Engine
    participant Retrieval as Retrieval Service
    participant Vector as Vector Store Adapter
    participant Milvus as Milvus
    participant Elastic as Elasticsearch
    participant Model as Model Adapter

    C->>RAG: 1. 查询请求

    RAG->>RAG: 2. 查询改写

    par 混合检索
        RAG->>Retrieval: 3a. 向量检索请求
        Retrieval->>Vector: 向量化查询
        Vector->>Milvus: 相似度搜索
        Milvus-->>Vector: Top-K结果
        Vector-->>Retrieval: 向量结果
    and
        RAG->>Retrieval: 3b. 全文检索请求
        Retrieval->>Elastic: BM25搜索
        Elastic-->>Retrieval: 全文结果
    end

    Retrieval->>Retrieval: 4. 结果合并 (RRF)
    Retrieval->>Model: 5. LLM重排序
    Model-->>Retrieval: 重排结果
    Retrieval-->>RAG: 6. Top-N文档

    RAG->>RAG: 7. 上下文构建
    RAG->>Model: 8. LLM生成答案
    Model-->>RAG: 生成结果

    RAG-->>C: 9. 带引用的答案
```

#### 3. 工具调用流程

```mermaid
sequenceDiagram
    participant Agent as Agent Engine
    participant Model as Model Adapter
    participant Tools as Tool Service
    participant External as 外部API/服务
    participant Memory as Memory Store

    Agent->>Model: 1. 用户请求分析
    Model-->>Agent: 需要调用工具

    Agent->>Agent: 2. 工具选择与参数提取

    loop 工具调用循环 (最多10步)
        Agent->>Tools: 3. 调用工具
        Tools->>External: 4. 执行外部调用
        External-->>Tools: 执行结果
        Tools-->>Agent: 5. 工具返回

        Agent->>Memory: 6. 保存执行记录

        Agent->>Model: 7. 判断是否继续
        Model-->>Agent: 决策 (继续/完成)

        opt 需要继续
            Agent->>Agent: 8. 计划下一步
        end
    end

    Agent->>Model: 9. 生成最终回复
    Model-->>Agent: 回复内容

    Agent->>Memory: 10. 保存完整对话
```

## 技术栈

### 后端服务

- **Go 服务**: Kratos 框架, Gin, gRPC, GORM
- **Python 服务**: FastAPI, LangChain, LangGraph
- **API 网关**: Apache APISIX

### 数据存储

- **关系数据库**: PostgreSQL (pgvector 扩展)
- **向量数据库**: Milvus
- **缓存**: Redis
- **消息队列**: Kafka / NATS
- **对象存储**: MinIO

### 基础设施

- **容器编排**: Kubernetes
- **服务发现**: Consul
- **配置管理**: Nacos (可选)
- **负载均衡**: APISIX + K8s Service

### 可观测性

- **指标**: Prometheus + Grafana
- **追踪**: Jaeger / OpenTelemetry
- **日志**: ELK Stack / Loki
- **监控**: Grafana Dashboards

### AI/ML

- **LLM**: OpenAI, Anthropic, 本地模型
- **Embedding**: BGE-M3, OpenAI Ada
- **语音**: ASR/TTS 引擎集成

## 核心特性

### 1. 高可用性

- ✅ N+1 冗余部署
- ✅ 自动故障转移
- ✅ 金丝雀发布
- ✅ 健康检查与自动恢复

### 2. 高性能

- ✅ API 网关 P95 延迟 < 200ms
- ✅ 流式响应 TTFB < 300ms
- ✅ 端到端 QA < 2.5s
- ✅ 支持 1000+ RPS 基准

### 3. 可扩展性

- ✅ 水平扩展支持
- ✅ HPA 自动伸缩
- ✅ 微服务解耦设计
- ✅ 插件化架构

### 4. 弹性容错

- ✅ 断路器模式
- ✅ 指数退避重试
- ✅ 限流与降级
- ✅ 超时控制

### 5. 安全性

- ✅ JWT 认证
- ✅ RBAC 权限控制
- ✅ 数据加密
- ✅ PII 脱敏
- ✅ 审计日志

### 6. 可观测性

- ✅ OpenTelemetry 全链路追踪
- ✅ Prometheus 指标采集
- ✅ 统一日志聚合
- ✅ SLO/Error Budget 监控

## 服务清单

### Go 服务 (7 个)

| 服务                 | 职责               | 端口                      | 语言 |
| -------------------- | ------------------ | ------------------------- | ---- |
| identity-service     | 用户认证与授权     | 9000 (gRPC) / 8080 (HTTP) | Go   |
| conversation-service | 会话管理           | 8080                      | Go   |
| knowledge-service    | 知识库管理         | 9000 (gRPC) / 8080 (HTTP) | Go   |
| ai-orchestrator      | AI 任务编排        | 9003                      | Go   |
| model-router         | 模型路由与负载均衡 | 9004                      | Go   |
| notification-service | 通知服务           | 9006                      | Go   |
| analytics-service    | 分析服务           | 9007                      | Go   |

### Python 服务 (9 个)

| 服务                       | 职责         | 端口 | 语言   |
| -------------------------- | ------------ | ---- | ------ |
| agent-engine               | 智能体引擎   | 8003 | Python |
| rag-engine                 | 检索增强生成 | 8006 | Python |
| retrieval-service          | 检索服务     | 8012 | Python |
| indexing-service           | 文档索引     | 8004 | Python |
| model-adapter              | 模型适配器   | 8005 | Python |
| vector-store-adapter       | 向量存储适配 | 8003 | Python |
| voice-engine               | 语音处理     | 8002 | Python |
| multimodal-engine          | 多模态处理   | 8007 | Python |
| knowledge-service (Python) | 知识图谱服务 | 8010 | Python |

## 部署架构

### Kubernetes 部署

```
Namespace: voiceassistant
├── Go Services (Deployments)
│   ├── identity-service (3 replicas, HPA)
│   ├── conversation-service (3 replicas, HPA)
│   └── ...
├── Python Services (Deployments)
│   ├── agent-engine (3 replicas, HPA)
│   ├── rag-engine (3 replicas, HPA)
│   └── ...
├── Infrastructure
│   ├── PostgreSQL (StatefulSet, 3 replicas)
│   ├── Redis (StatefulSet, 3 replicas)
│   ├── Milvus (StatefulSet)
│   ├── Consul (StatefulSet, 3 replicas)
│   └── Kafka (StatefulSet, 3 replicas)
└── Observability
    ├── Prometheus (StatefulSet)
    ├── Grafana (Deployment)
    └── Jaeger (Deployment)
```

## NFR (非功能需求)

### 性能指标

- API Gateway P95 延迟: **< 200ms**
- 流式 TTFB: **< 300ms**
- 端到端 QA: **< 2.5s**
- 基准 RPS: **1000+**

### 可用性

- SLA: **≥ 99.9%**
- 核心服务: **N+1 冗余**
- 故障恢复: **自动 + 金丝雀**

### 可观测性

- 追踪: **OpenTelemetry 全链路**
- 指标: **Prometheus + Grafana**
- SLO/Error Budget: **实时监控**

### 安全性

- 认证: **JWT + OAuth2**
- 授权: **RBAC 最小权限**
- 数据: **KMS 加密 + PII 脱敏**
- 合规: **GDPR/CCPA 审计日志**

### 成本

- 请求级 Token 计费
- 模型/Embedding/召回/重排拆分
- 预算告警与自动降级

## 链接

- [源码入口](../../)
- [API 文档](../../api/)
- [运行手册](../runbook/index.md)
- [SLO 指标](../nfr/slo.md)
- [变更日志](../../CHANGELOG.md)
