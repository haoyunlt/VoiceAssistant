# VoiceHelper-00-总览

## 摘要

### 项目目标

VoiceHelper 是一个企业级 AI 客服与语音助手平台，致力于提供：

- **多模态交互**：支持文本、语音、图片等多种输入输出方式
- **智能对话管理**：基于上下文的对话理解和意图识别
- **知识检索增强**：混合检索、图谱推理、自我纠错的 RAG 系统
- **智能体协作**：ReAct、Plan-Execute、Multi-Agent 协作的任务执行能力
- **企业级可靠性**：服务网格、熔断重试、全链路追踪、多租户隔离

### 项目边界

**在范围内**：

- 对话管理和上下文维护
- 用户身份认证和权限管理
- RAG检索增强生成系统
- AI Agent 任务编排和执行
- 多模态内容处理（文本、语音、图片）
- 模型路由和成本优化
- 多租户数据隔离
- 全链路可观测性

**非目标**：

- 不提供训练自定义大模型的能力（依赖第三方 LLM API）
- 不包含 CRM、工单等业务系统功能
- 不提供物理机房和硬件管理
- 不提供客户端 APP 开发（仅提供 API）

### 运行环境与部署形态

- **容器化**：Docker 容器 + Kubernetes 编排
- **服务网格**：Istio + Envoy Sidecar
- **配置中心**：Nacos 统一配置管理
- **数据库**：PostgreSQL（业务数据）、Redis（缓存）、Milvus（向量）、Elasticsearch（全文检索）
- **消息队列**：Kafka（异步事件）
- **可观测性**：Prometheus + Grafana + Jaeger + OpenTelemetry
- **负载均衡**：Istio Gateway + EnvoyFilter

---

## 整体架构图

```mermaid
graph TB
    subgraph "客户端层"
        WebClient[Web 客户端]
        MobileClient[移动端客户端]
        ThirdParty[第三方集成]
    end

    subgraph "网关与流量管理层 - Istio Service Mesh"
        IstioGW[Istio Gateway<br/>统一流量入口]
        VS[VirtualService<br/>路由规则]
        DR[DestinationRule<br/>流量策略]

        subgraph "Gateway 功能"
            RateLimit[限流控制]
            JWTAuth[JWT 认证]
            mTLS[服务间 mTLS]
            Retry[重试与超时]
        end
    end

    subgraph "Go 微服务层 - 业务编排"
        IdentitySvc[Identity Service<br/>认证授权服务<br/>:9000 gRPC]
        ConvSvc[Conversation Service<br/>对话管理服务<br/>:50052 gRPC]
        AIOrchSvc[AI Orchestrator<br/>AI 编排服务<br/>:50054 gRPC]
        ModelRouterSvc[Model Router<br/>模型路由服务<br/>:50055 gRPC]
        AnalyticsSvc[Analytics Service<br/>分析统计服务<br/>:50056 gRPC]
        NotificationSvc[Notification Service<br/>通知推送服务<br/>:50057 gRPC]
    end

    subgraph "Python AI 服务层 - 算法能力"
        AgentEngine[Agent Engine<br/>智能体引擎<br/>:8010 HTTP]
        RAGEngine[RAG Engine<br/>检索增强生成<br/>:8006 HTTP]
        RetrievalSvc[Retrieval Service<br/>混合检索服务<br/>:8012 HTTP]
        KnowledgeSvc[Knowledge Service<br/>知识图谱服务<br/>:8013 HTTP]
        ModelAdapter[Model Adapter<br/>LLM 适配器<br/>:8005 HTTP]
        VoiceEngine[Voice Engine<br/>语音处理<br/>:8004 HTTP]
        MultimodalEngine[Multimodal Engine<br/>多模态引擎<br/>:8008 HTTP]
        IndexingSvc[Indexing Service<br/>文档索引<br/>:8011 HTTP]
        VectorAdapter[Vector Store Adapter<br/>向量存储适配<br/>:8009 HTTP]
    end

    subgraph "数据存储层"
        PostgreSQL[(PostgreSQL<br/>业务数据库<br/>用户/对话/知识库)]
        Redis[(Redis<br/>缓存层<br/>会话/Token黑名单)]
        Milvus[(Milvus<br/>向量数据库<br/>Embedding 存储)]
        ES[(Elasticsearch<br/>全文搜索<br/>BM25 检索)]
        MinIO[(MinIO<br/>对象存储<br/>文档/图片/音频)]
        ClickHouse[(ClickHouse<br/>分析数据库<br/>指标聚合)]
    end

    subgraph "基础设施层"
        Nacos[Nacos<br/>配置中心<br/>服务发现]
        Kafka[Kafka<br/>消息队列<br/>异步事件]
    end

    subgraph "可观测性层"
        Prometheus[Prometheus<br/>指标采集]
        Grafana[Grafana<br/>可视化]
        Jaeger[Jaeger<br/>链路追踪]
        OTel[OpenTelemetry<br/>Collector]
    end

    subgraph "外部服务"
        OpenAI[OpenAI GPT-4]
        Claude[Claude API]
        Qwen[通义千问]
        AzureSpeech[Azure Speech<br/>ASR/TTS]
    end

    %% 客户端到网关
    WebClient --> IstioGW
    MobileClient --> IstioGW
    ThirdParty --> IstioGW

    %% 网关到服务
    IstioGW --> VS
    VS --> DR
    DR --> RateLimit
    DR --> JWTAuth
    DR --> mTLS

    %% 网关路由到 Go 服务
    mTLS --> IdentitySvc
    mTLS --> ConvSvc
    mTLS --> AIOrchSvc

    %% Go 服务间通信 (gRPC)
    ConvSvc -->|gRPC| IdentitySvc
    ConvSvc -->|gRPC| AIOrchSvc
    AIOrchSvc -->|gRPC| ModelRouterSvc
    AnalyticsSvc -->|gRPC| ConvSvc

    %% Go 调用 Python (HTTP/JSON)
    AIOrchSvc -->|HTTP| AgentEngine
    AIOrchSvc -->|HTTP| RAGEngine
    ConvSvc -->|HTTP| VoiceEngine
    ModelRouterSvc -->|HTTP| ModelAdapter

    %% Python 服务间通信 (HTTP)
    AgentEngine -->|HTTP| RAGEngine
    AgentEngine -->|HTTP| ModelAdapter
    RAGEngine -->|HTTP| RetrievalSvc
    RAGEngine -->|HTTP| KnowledgeSvc
    RetrievalSvc -->|HTTP| VectorAdapter
    IndexingSvc -->|HTTP| VectorAdapter

    %% 服务访问数据层
    IdentitySvc --> PostgreSQL
    IdentitySvc --> Redis
    ConvSvc --> PostgreSQL
    ConvSvc --> Redis
    RAGEngine --> Milvus
    RetrievalSvc --> Milvus
    RetrievalSvc --> ES
    IndexingSvc --> MinIO
    VectorAdapter --> Milvus
    AnalyticsSvc --> ClickHouse
    KnowledgeSvc --> PostgreSQL

    %% 配置中心
    IdentitySvc -.配置.-> Nacos
    ConvSvc -.配置.-> Nacos
    AIOrchSvc -.配置.-> Nacos
    AgentEngine -.配置.-> Nacos
    RAGEngine -.配置.-> Nacos

    %% 消息队列
    ConvSvc -.事件.-> Kafka
    NotificationSvc -.事件.-> Kafka
    AnalyticsSvc -.事件.-> Kafka

    %% Python 调用外部服务
    ModelAdapter --> OpenAI
    ModelAdapter --> Claude
    ModelAdapter --> Qwen
    VoiceEngine --> AzureSpeech

    %% 可观测性
    IstioGW -.指标.-> Prometheus
    IdentitySvc -.指标.-> Prometheus
    ConvSvc -.指标.-> Prometheus
    AIOrchSvc -.指标.-> Prometheus
    AgentEngine -.指标.-> Prometheus
    RAGEngine -.指标.-> Prometheus
    Prometheus --> Grafana

    IstioGW -.追踪.-> OTel
    IdentitySvc -.追踪.-> OTel
    ConvSvc -.追踪.-> OTel
    AIOrchSvc -.追踪.-> OTel
    AgentEngine -.追踪.-> OTel
    OTel --> Jaeger

    style IstioGW fill:#f9f,stroke:#333,stroke-width:4px
    style IdentitySvc fill:#bbf,stroke:#333,stroke-width:2px
    style ConvSvc fill:#bbf,stroke:#333,stroke-width:2px
    style AIOrchSvc fill:#bbf,stroke:#333,stroke-width:2px
    style AgentEngine fill:#bfb,stroke:#333,stroke-width:2px
    style RAGEngine fill:#bfb,stroke:#333,stroke-width:2px
    style PostgreSQL fill:#fbb,stroke:#333,stroke-width:2px
    style Milvus fill:#fbb,stroke:#333,stroke-width:2px
```

### 架构图说明

#### 1. 图意概述

该架构图展示了 VoiceHelper 平台的五层架构体系：客户端层、网关与流量管理层、应用服务层（Go + Python）、数据存储层、基础设施层及可观测性层。核心设计理念是**前后端分离、微服务解耦、服务网格流量管理、混合语言技术栈**。

#### 2. 关键组件与接口

**网关层（Istio Service Mesh）**：
- **Istio Gateway**：统一的南北向流量入口，支持 HTTP/HTTPS/gRPC/WebSocket
- **VirtualService**：定义路由规则，支持基于 URI、Header、权重的路由
- **DestinationRule**：定义流量策略，包括负载均衡、连接池、熔断器
- **EnvoyFilter**：实现限流、JWT 认证、mTLS、请求/响应转换
- **Sidecar 注入**：每个服务 Pod 自动注入 Envoy 代理，实现服务间 mTLS 和流量劫持

**Go 微服务层**（gRPC 通信）：
- `Identity Service`：用户认证（JWT）、租户管理（RBAC）、Token 黑名单
- `Conversation Service`：对话会话管理、消息持久化、上下文窗口压缩
- `AI Orchestrator`：协调 Agent Engine 和 RAG Engine，处理复杂 AI 任务
- `Model Router`：智能模型路由、A/B 测试、成本预算控制、模型健康检查
- `Analytics Service`：实时和离线指标统计、用户行为分析、成本归因
- `Notification Service`：多渠道通知推送（邮件、短信、Webhook）

**Python AI 服务层**（HTTP/JSON 通信）：
- `Agent Engine`：ReAct/Plan-Execute/Reflexion 模式的智能体、Multi-Agent 协作、LangGraph 工作流编排
- `RAG Engine`：混合检索（Vector + BM25）、Cross-Encoder 重排、Graph RAG、Self-RAG 自我纠错、上下文压缩
- `Retrieval Service`：统一检索接口、RRF 融合、语义缓存（FAISS）
- `Knowledge Service`：知识图谱构建（NetworkX/Neo4j）、实体关系抽取、多跳推理
- `Model Adapter`：统一 LLM 接口，支持 OpenAI、Claude、通义千问等多家模型
- `Voice Engine`：VAD 语音检测、Azure ASR 实时识别、Azure TTS 情感语音合成、WebSocket 流式传输
- `Multimodal Engine`：图像识别、OCR、表格解析
- `Indexing Service`：文档解析（PDF/Word/HTML）、语义分块、向量化、批量索引
- `Vector Store Adapter`：向量数据库适配层，支持 Milvus、Qdrant 等

#### 3. 边界条件

**并发与扩展**：
- Istio Gateway 支持 HPA 自动扩缩容（3-10 副本）
- Go 服务支持水平扩展，无状态设计
- Python 服务基于 FastAPI 异步框架，支持高并发
- 向量检索支持分片和副本，Milvus 集群化部署

**超时与重试**：
- 网关层超时：30s（可配置）
- Go 服务间调用超时：10s（gRPC）
- Go 调用 Python 超时：60s（Agent/RAG 任务）、30s（其他服务）
- 重试策略：指数退避，最多 3 次重试
- 熔断器：连续 5 次失败触发熔断，60s 后尝试恢复

**幂等性**：
- 所有写操作（创建对话、发送消息、上传文档）基于幂等键（Idempotency-Key）
- Redis 存储幂等键，TTL 24 小时
- 熔断器状态持久化到 Redis

**顺序保证**：
- 对话消息按 `created_at` 时间戳排序
- Kafka 消息按 `partition key`（tenant_id + user_id）保证顺序
- Graph RAG 多跳查询使用 BFS/DFS 确保路径顺序

#### 4. 异常与回退

**网关层异常**：
- 限流触发：返回 429 + Retry-After header
- JWT 验证失败：返回 401，提示重新登录
- 路由目标不可用：503，触发上游熔断器

**服务层异常**：
- LLM API 超时/限流：切换到备用模型（通义千问 → 文心一言）
- 向量检索失败：降级到 BM25 纯关键词检索
- 图谱查询超时：回退到向量检索
- Agent 执行超时：强制终止，返回部分结果

**数据层异常**：
- PostgreSQL 主库故障：自动切换到只读副本（5s 内）
- Redis 缓存失效：直接查询数据库，并记录 Cache Miss 指标
- Milvus 集群不可用：返回缓存结果或空结果 + 告警

**回退策略**：
- 优雅降级：关闭非核心功能（Self-RAG、上下文压缩）以降低延迟
- 预设响应：高频问题使用预定义答案（FAQ）
- 人工介入：复杂任务转人工客服

#### 5. 性能与容量

**网关层**：
- 单 Gateway Pod：8 核 CPU / 16 GB 内存
- 支持 5000 RPS，P95 延迟 <50ms
- Envoy 连接池：HTTP/1.1 每目标 1024 连接，HTTP/2 每目标 100 流

**Go 服务层**：
- Identity Service：10000 Token 验证/秒，P95 <10ms
- Conversation Service：3000 消息/秒，P95 <100ms
- 数据库连接池：最大 50 连接/Pod

**Python AI 服务层**：
- Agent Engine：50 任务/秒，P95 <3s（简单任务）
- RAG Engine：200 查询/秒，P95 <2s（混合检索 + 重排）
- 语义缓存命中率：60%+（FAISS 索引 100 万向量）

**数据层**：
- PostgreSQL：10000 读 QPS / 2000 写 QPS（单实例）
- Redis：100000 ops/s（集群模式）
- Milvus：10000 向量查询/秒，召回率@5：0.82

**带宽**：
- Gateway 出口带宽：10 Gbps
- 服务间通信：1 Gbps（Pod to Pod）

#### 6. 版本兼容与演进

**协议版本**：
- gRPC API：`v1`（向后兼容，新增字段使用 `optional`）
- HTTP REST API：`/api/v1`（Major 版本不兼容时升级到 v2）
- Proto 文件：使用 `reserved` 保留废弃字段，避免冲突

**数据库迁移**：
- 使用 Flyway/Liquibase 管理 Schema 变更
- 灰度发布：新旧版本共存 7 天，逐步切换流量
- 回滚策略：保留最近 3 个版本的数据库快照

**API 废弃策略**：
- 废弃通知：提前 3 个月在文档和响应 Header（`Deprecation: true`）中告知
- 过渡期：6 个月
- 下线前：邮件通知所有 API 用户

**配置热更新**：
- Nacos 配置变更自动推送到服务（5s 内生效）
- 支持回滚到历史版本（保留 30 天）

---

## 全局时序图

### 1. 用户登录与身份认证流程

```mermaid
sequenceDiagram
    autonumber
    participant Client as 客户端
    participant Gateway as Istio Gateway
    participant Identity as Identity Service
    participant Redis as Redis 缓存
    participant PG as PostgreSQL

    Client->>Gateway: POST /api/v1/auth/login<br/>{username, password}
    Gateway->>Gateway: 限流检查（100 req/min/IP）
    Gateway->>Identity: gRPC Login(request)

    Identity->>Identity: 密码强度预检（8位+大小写+数字）
    Identity->>PG: SELECT user WHERE email=?
    PG-->>Identity: User 实体（含密码哈希）

    Identity->>Identity: bcrypt.Compare(输入密码, 存储哈希)

    alt 密码匹配
        Identity->>Identity: 生成 JWT Access Token（1h）<br/>生成 Refresh Token（7天）
        Identity->>Redis: SET token_blacklist:{user_id} false TTL=1h
        Identity->>PG: UPDATE users SET last_login=NOW()
        Identity->>Redis: SET user_cache:{user_id} {user_data} TTL=1h
        Identity-->>Gateway: LoginResponse{access_token, refresh_token}
        Gateway-->>Client: 200 OK + Tokens
    else 密码不匹配
        Identity->>PG: UPDATE users SET failed_attempts+=1
        Identity-->>Gateway: 401 Unauthorized
        Gateway-->>Client: 401 + {error: "Invalid credentials"}
    end

    Note over Client,PG: 后续请求携带 Access Token
    Client->>Gateway: GET /api/v1/conversations<br/>Authorization: Bearer {token}
    Gateway->>Gateway: JWT 签名验证（EnvoyFilter）
    Gateway->>Identity: gRPC VerifyToken(token)
    Identity->>Redis: GET token_blacklist:{user_id}

    alt Token 有效且未失效
        Redis-->>Identity: false（未加入黑名单）
        Identity->>Redis: GET user_cache:{user_id}
        alt 缓存命中
            Redis-->>Identity: User 数据
        else 缓存未命中
            Identity->>PG: SELECT user WHERE id=?
            PG-->>Identity: User 实体
            Identity->>Redis: SET user_cache:{user_id} TTL=1h
        end
        Identity-->>Gateway: VerifyResponse{user, permissions}
        Gateway->>Gateway: 注入 User Context 到 Metadata
        Gateway->>ConvSvc: gRPC ListConversations(user_id)
    else Token 已失效或被拉黑
        Identity-->>Gateway: 401 Token Invalid
        Gateway-->>Client: 401 + {error: "Token expired"}
    end
```

**流程关键点**：

1. **限流层**：Istio Gateway 使用 Redis 分布式限流，防止暴力破解（100 req/min/IP）
2. **密码验证**：bcrypt 哈希对比，强度检查在前端和后端双重校验
3. **Token 机制**：Access Token 短期有效（1h），Refresh Token 长期有效（7天），支持无感刷新
4. **黑名单机制**：登出时将 Token 加入 Redis 黑名单，TTL 等于 Token 剩余有效期
5. **缓存策略**：用户信息缓存 1 小时，减少数据库查询
6. **审计日志**：每次登录/验证失败记录到 PostgreSQL `audit_logs` 表
7. **失败重试**：超过 5 次失败尝试后锁定账户 15 分钟

---

### 2. 智能对话全流程（文本输入）

```mermaid
sequenceDiagram
    autonumber
    participant Client as 客户端
    participant Gateway as Istio Gateway
    participant Conv as Conversation Service
    participant AIOrch as AI Orchestrator
    participant Agent as Agent Engine
    participant RAG as RAG Engine
    participant Retrieval as Retrieval Service
    participant ModelAdapter as Model Adapter
    participant LLM as OpenAI GPT-4
    participant PG as PostgreSQL
    participant Redis as Redis

    Client->>Gateway: POST /api/v1/conversations/{id}/messages<br/>{content: "如何重置密码？"}
    Gateway->>Conv: gRPC SendMessage(conversation_id, content)

    Conv->>Redis: GET conversation_context:{conv_id}
    alt 上下文缓存命中
        Redis-->>Conv: 最近 10 轮对话历史
    else 缓存未命中
        Conv->>PG: SELECT messages WHERE conv_id=? ORDER BY created_at DESC LIMIT 10
        PG-->>Conv: 历史消息列表
        Conv->>Redis: SET conversation_context:{conv_id} TTL=30min
    end

    Conv->>Conv: 构建上下文窗口（Token 数限制 4000）
    Conv->>PG: INSERT INTO messages(conv_id, role=user, content)
    Conv->>AIOrch: gRPC ProcessMessage(user_query, context)

    AIOrch->>AIOrch: 意图分类（FAQ / 知识查询 / 任务执行）

    alt 识别为知识查询
        AIOrch->>RAG: HTTP POST /api/v1/rag/query<br/>{query, tenant_id, mode: "ultimate"}

        RAG->>RAG: Query Classifier（查询类型识别）
        RAG->>Redis: GET semantic_cache:{query_embedding}

        alt 语义缓存命中（相似度 >0.92）
            Redis-->>RAG: 缓存答案
            RAG-->>AIOrch: 直接返回缓存结果
        else 缓存未命中
            RAG->>Retrieval: HTTP POST /api/v1/retrieval/hybrid<br/>{query, top_k: 20}

            par 并行混合检索
                Retrieval->>VectorStore: 向量检索（Dense Retrieval）
                VectorStore-->>Retrieval: Top-20 向量结果
            and
                Retrieval->>Elasticsearch: BM25 关键词检索
                Elasticsearch-->>Retrieval: Top-20 BM25 结果
            end

            Retrieval->>Retrieval: RRF 融合（Reciprocal Rank Fusion）
            Retrieval->>Retrieval: Cross-Encoder 重排（保留 Top-5）
            Retrieval-->>RAG: 精排后的文档列表

            RAG->>RAG: 上下文构建 + 引用标注

            opt 启用上下文压缩
                RAG->>RAG: LLMLingua 压缩（保留 50% Token）
            end

            RAG->>ModelAdapter: HTTP POST /api/v1/models/chat<br/>{messages, model: "gpt-4"}
            ModelAdapter->>LLM: OpenAI Chat Completion API
            LLM-->>ModelAdapter: 生成答案
            ModelAdapter-->>RAG: LLM 响应

            opt Self-RAG 幻觉检测
                RAG->>RAG: NLI 模型检测幻觉（阈值 0.7）
                alt 检测到幻觉
                    RAG->>ModelAdapter: 重新生成（增强 Prompt）
                    ModelAdapter->>LLM: 再次调用
                    LLM-->>ModelAdapter: 修正答案
                    ModelAdapter-->>RAG: 修正后响应
                end
            end

            RAG->>Redis: SET semantic_cache:{query_embedding} {answer} TTL=1h
            RAG-->>AIOrch: 最终答案 + 引用来源
        end

    else 识别为复杂任务
        AIOrch->>Agent: HTTP POST /api/v1/agent/execute<br/>{task, mode: "react", tools: ["search", "calculator"]}

        loop ReAct 循环（最多 10 步）
            Agent->>ModelAdapter: LLM Reasoning（下一步行动）
            ModelAdapter->>LLM: Thought + Action
            LLM-->>ModelAdapter: Action: search(keyword)
            ModelAdapter-->>Agent: 工具调用指令
            Agent->>ToolRegistry: 执行工具 search(keyword)
            ToolRegistry-->>Agent: Observation（工具结果）
            Agent->>Agent: 判断是否完成任务
        end

        Agent-->>AIOrch: 任务执行结果
    end

    AIOrch-->>Conv: AI 响应内容
    Conv->>PG: INSERT INTO messages(conv_id, role=assistant, content)
    Conv->>Redis: UPDATE conversation_context:{conv_id} APPEND new_message
    Conv-->>Gateway: SendMessageResponse{message}
    Gateway-->>Client: 200 OK + AI 回复

    Note over Client,Redis: 异步：指标上报和日志记录
    Conv->>Kafka: PUBLISH conversation.message_sent<br/>{conv_id, latency, tokens}
    Analytics->>Kafka: CONSUME conversation.message_sent
    Analytics->>ClickHouse: INSERT INTO message_stats
```

**流程关键点**：

1. **上下文管理**：Redis 缓存最近 10 轮对话（30min TTL），避免每次查库
2. **Token 窗口**：动态压缩上下文，保持在 4000 Token 以内（GPT-4-turbo 限制）
3. **意图分类**：AIOrchestrator 根据查询类型路由到不同引擎（RAG / Agent）
4. **语义缓存**：FAISS 索引，相似度 >0.92 直接返回，命中率 60%
5. **混合检索**：向量检索（召回） + BM25（关键词） + RRF 融合 + Cross-Encoder 精排
6. **上下文压缩**：使用 LLMLingua 在不损失关键信息的前提下减少 30% Token
7. **Self-RAG**：NLI 模型检测幻觉，幻觉率从 15% 降至 8%
8. **异步处理**：消息发送成功后立即返回，指标上报通过 Kafka 异步处理

---

### 3. 语音对话全流程（WebSocket 实时流）

```mermaid
sequenceDiagram
    autonumber
    participant Client as 客户端（浏览器）
    participant Gateway as Istio Gateway
    participant Voice as Voice Engine
    participant Azure as Azure Speech API
    participant AIOrch as AI Orchestrator
    participant RAG as RAG Engine
    participant Conv as Conversation Service

    Client->>Gateway: WebSocket Upgrade Request<br/>GET /ws/voice?token={jwt}
    Gateway->>Gateway: JWT 验证（EnvoyFilter）
    Gateway->>Voice: 建立 WebSocket 连接
    Voice-->>Client: WebSocket 连接就绪（101 Switching Protocols）

    Note over Client,Voice: 实时语音流开始

    loop 音频流传输（实时）
        Client->>Voice: WebSocket Binary Frame<br/>（16kHz PCM 音频数据，200ms 每帧）
        Voice->>Voice: VAD 检测（语音活动检测）

        alt 检测到语音
            Voice->>Azure: Azure Speech SDK<br/>StartRecognizingAsync()
            Azure-->>Voice: RecognitionResult（流式返回）
            Voice->>Voice: 累积文本片段
        else 检测到静音（>1s）
            Voice->>Voice: 触发语音结束事件
            Voice->>Azure: StopRecognizingAsync()
            Azure-->>Voice: FinalRecognitionResult<br/>{text: "如何使用产品X？"}

            Voice->>Voice: 构建对话请求
            Voice->>AIOrch: HTTP POST /api/v1/ai/process<br/>{query: "如何使用产品X？", session_id}

            AIOrch->>RAG: RAG 查询（同文本流程）
            RAG-->>AIOrch: 答案文本
            AIOrch-->>Voice: 文本响应

            Voice->>Azure: Azure TTS Synthesize<br/>{text, voice: "zh-CN-XiaoxiaoNeural", style: "friendly"}

            loop TTS 流式返回
                Azure-->>Voice: AudioChunk（MP3/Opus 格式）
                Voice->>Client: WebSocket Binary Frame（音频流）
                Client->>Client: 播放音频（Web Audio API）
            end

            Voice->>Conv: 异步保存对话记录<br/>gRPC SaveMessage(session_id, user_text, ai_text)
        end
    end

    Note over Client,Voice: 用户关闭连接
    Client->>Voice: WebSocket Close Frame
    Voice->>Azure: 释放 Speech SDK 资源
    Voice->>Voice: 清理会话状态
    Voice-->>Client: WebSocket Close ACK
```

**流程关键点**：

1. **VAD 检测**：Voice Activity Detection 识别语音开始和结束，减少无效传输
2. **流式 ASR**：Azure Speech SDK 实时识别，TTFB（Time To First Byte）<300ms
3. **静音触发**：1 秒静音自动触发语音结束，避免等待超时
4. **TTS 流式合成**：边合成边传输，降低首字延迟（First Token Latency）
5. **音频格式**：客户端上传 PCM 16kHz，服务端返回 Opus 压缩（节省 50% 带宽）
6. **会话管理**：WebSocket 连接绑定 session_id，支持断线重连（30s 内）
7. **异步持久化**：对话记录异步保存，不阻塞音频流
8. **情感语音**：TTS 支持多种情感（友好/正式/抱歉），根据意图动态选择

---

### 4. 文档索引与向量化流程

```mermaid
sequenceDiagram
    autonumber
    participant Client as 管理员
    participant Gateway as Istio Gateway
    participant Knowledge as Knowledge Service (Go)
    participant Indexing as Indexing Service (Python)
    participant MinIO as MinIO 对象存储
    participant VectorAdapter as Vector Store Adapter
    participant Milvus as Milvus 向量库
    participant ES as Elasticsearch
    participant PG as PostgreSQL

    Client->>Gateway: POST /api/v1/knowledge/bases/{kb_id}/documents<br/>Content-Type: multipart/form-data<br/>File: product_manual.pdf (5MB)
    Gateway->>Knowledge: gRPC UploadDocument(kb_id, file_stream)

    Knowledge->>Knowledge: 生成 document_id（UUID）
    Knowledge->>MinIO: PutObject(bucket: documents, key: {doc_id}.pdf)
    MinIO-->>Knowledge: Object URL

    Knowledge->>PG: INSERT INTO documents(id, kb_id, filename, status="pending")
    Knowledge->>Kafka: PUBLISH document.uploaded<br/>{doc_id, kb_id, file_url}
    Knowledge-->>Gateway: UploadResponse{doc_id, status: "processing"}
    Gateway-->>Client: 202 Accepted + doc_id

    Note over Knowledge,Milvus: 异步处理：文档解析与索引

    Indexing->>Kafka: CONSUME document.uploaded
    Indexing->>MinIO: GetObject(doc_id)
    MinIO-->>Indexing: PDF 文件流

    Indexing->>Indexing: 文档解析（PyMuPDF）<br/>提取文本/图片/表格
    Indexing->>Indexing: 文本清洗（去除无效字符/HTML标签）

    Indexing->>Indexing: 语义分块（Semantic Chunking）<br/>- 按段落分割<br/>- 保持句子完整性<br/>- 每块 300-500 Token

    loop 遍历每个文本块
        Indexing->>ModelAdapter: HTTP POST /api/v1/embeddings<br/>{texts: [chunk1, chunk2, ...], model: "bge-large-zh-v1.5"}
        ModelAdapter->>ModelAdapter: 批量 Embedding（Batch=32）
        ModelAdapter-->>Indexing: 向量列表（维度 1024）

        Indexing->>VectorAdapter: HTTP POST /api/v1/vectors/insert<br/>{collection: kb_id, vectors, metadata}
        VectorAdapter->>Milvus: Insert(vectors, metadata)
        Milvus-->>VectorAdapter: Insert OK
        VectorAdapter-->>Indexing: 插入成功

        Indexing->>ES: HTTP POST /_bulk<br/>索引文本块到 BM25
        ES-->>Indexing: Indexed
    end

    Indexing->>PG: UPDATE documents SET status="indexed", chunk_count=N
    Indexing->>Kafka: PUBLISH document.indexed<br/>{doc_id, chunk_count, elapsed_time}

    opt 构建知识图谱
        Indexing->>KnowledgeSvc: HTTP POST /api/v1/graph/extract<br/>{doc_id, chunks}
        KnowledgeSvc->>LLM: 实体关系抽取（NER + RE）
        LLM-->>KnowledgeSvc: 实体列表 + 关系三元组
        KnowledgeSvc->>Neo4j: CREATE (entity)-[relation]->(entity)
        Neo4j-->>KnowledgeSvc: Graph Created
    end

    Note over Client,PG: 客户端轮询或 WebSocket 推送状态
    Client->>Gateway: GET /api/v1/knowledge/documents/{doc_id}/status
    Gateway->>Knowledge: gRPC GetDocumentStatus(doc_id)
    Knowledge->>PG: SELECT status, chunk_count FROM documents WHERE id=?
    PG-->>Knowledge: status="indexed", chunk_count=120
    Knowledge-->>Gateway: StatusResponse{status, chunk_count}
    Gateway-->>Client: 200 OK + {status: "indexed"}
```

**流程关键点**：

1. **文件上传**：大文件（>10MB）使用分片上传（Multipart Upload），断点续传
2. **对象存储**：MinIO 存储原始文件，3 副本保证可靠性
3. **异步处理**：上传后立即返回 202，后台通过 Kafka 触发索引任务
4. **文档解析**：支持 PDF/Word/PPT/HTML/Markdown，使用 PyMuPDF/python-docx
5. **语义分块**：保证句子完整性，避免截断关键信息，每块 300-500 Token
6. **批量向量化**：Batch=32，提升 10 倍效率，降低 API 调用成本
7. **双重索引**：Milvus（向量检索） + Elasticsearch（BM25 关键词检索）
8. **知识图谱**：可选功能，使用 LLM 抽取实体关系，存储到 Neo4j
9. **状态通知**：索引完成后通过 WebSocket 推送通知或客户端轮询

---

### 5. 模型路由与 A/B 测试流程

```mermaid
sequenceDiagram
    autonumber
    participant Client as 业务服务
    participant ModelRouter as Model Router
    participant ABTest as A/B Test Manager
    participant Redis as Redis 缓存
    participant ModelAdapter as Model Adapter
    participant GPT4 as OpenAI GPT-4
    participant Qwen as 通义千问
    participant PG as PostgreSQL

    Client->>ModelRouter: gRPC Chat(request{user_id, query, enable_ab_test: true})

    ModelRouter->>ModelRouter: 提取路由参数（tenant_id, user_id）

    alt A/B 测试已启用
        ModelRouter->>ABTest: SelectVariant(test_id: "cost_optimization_v1", user_id)
        ABTest->>Redis: GET ab_test:user:{user_id}:test:{test_id}

        alt 缓存命中（用户已分配变体）
            Redis-->>ABTest: variant_id: "variant_b"
        else 缓存未命中（首次访问）
            ABTest->>PG: SELECT * FROM ab_tests WHERE id=? AND status='active'
            PG-->>ABTest: Test{variants: [{id: a, weight: 50, model: gpt-4}, {id: b, weight: 50, model: qwen-turbo}]}
            ABTest->>ABTest: 应用分流策略（Weighted Random）<br/>hash(user_id) % 100 < 50 → variant_a<br/>否则 → variant_b
            ABTest->>Redis: SET ab_test:user:{user_id}:test:{test_id} variant_b TTL=24h
            ABTest-->>ModelRouter: variant_id: "variant_b"
        end

        ModelRouter->>ModelRouter: 获取变体配置（model_id: qwen-turbo）

    else 常规路由（无 A/B 测试）
        ModelRouter->>ModelRouter: 应用路由策略（cheapest / fastest / best_quality）
        ModelRouter->>Redis: GET model_health:{model_id}

        alt 首选模型健康
            ModelRouter->>ModelRouter: 选择 gpt-4
        else 首选模型不可用
            ModelRouter->>ModelRouter: 降级到 qwen-turbo
        end
    end

    ModelRouter->>ModelRouter: 检查预算（tenant_id）
    ModelRouter->>Redis: GET budget:{tenant_id}:current_month

    alt 预算充足
        ModelRouter->>ModelAdapter: HTTP POST /api/v1/models/chat<br/>{model: "qwen-turbo", messages, max_tokens: 1000}

        ModelAdapter->>Qwen: Qwen Chat Completion API

        alt LLM 调用成功
            Qwen-->>ModelAdapter: Response{text, usage: {prompt_tokens: 150, completion_tokens: 200}}
            ModelAdapter-->>ModelRouter: ChatResponse{content, tokens: 350, cost: $0.002}

            ModelRouter->>Redis: INCRBY budget:{tenant_id}:current_month 0.002
            ModelRouter->>Redis: SET model_health:qwen-turbo healthy TTL=60s

            opt 记录 A/B 测试指标
                ModelRouter->>ABTest: RecordMetric(test_id, variant_id, success: true, latency: 1.2s, cost: $0.002)
                ABTest->>PG: INSERT INTO ab_test_metrics(test_id, variant_id, metric_type, value)
            end

            ModelRouter-->>Client: ChatResponse{content, metadata: {model: "qwen-turbo", variant: "b"}}

        else LLM 调用失败（超时/限流）
            Qwen-->>ModelAdapter: 429 Rate Limit Exceeded
            ModelAdapter-->>ModelRouter: Error{code: 429}

            ModelRouter->>Redis: SET model_health:qwen-turbo unhealthy TTL=300s
            ModelRouter->>ModelRouter: 触发熔断器，切换到备用模型
            ModelRouter->>ModelAdapter: HTTP POST /api/v1/models/chat<br/>{model: "gpt-3.5-turbo"}
            ModelAdapter->>GPT35: OpenAI GPT-3.5 Turbo API
            GPT35-->>ModelAdapter: Response
            ModelAdapter-->>ModelRouter: ChatResponse

            opt 记录失败指标
                ModelRouter->>ABTest: RecordMetric(test_id, variant_id, success: false, error: "rate_limit")
            end

            ModelRouter-->>Client: ChatResponse{content, metadata: {model: "gpt-3.5-turbo", fallback: true}}
        end

    else 预算不足
        ModelRouter->>ModelRouter: 应用降级策略<br/>- 切换到更便宜的模型（gpt-3.5-turbo）<br/>- 减少 max_tokens
        ModelRouter->>ModelAdapter: HTTP POST /api/v1/models/chat<br/>{model: "gpt-3.5-turbo", max_tokens: 500}
        ModelAdapter->>GPT35: OpenAI GPT-3.5 Turbo API
        GPT35-->>ModelAdapter: Response（截断）
        ModelAdapter-->>ModelRouter: ChatResponse
        ModelRouter-->>Client: ChatResponse + Warning{budget_exceeded: true}
    end
```

**流程关键点**：

1. **A/B 测试分流**：基于用户 ID 哈希，保证同一用户始终分配到相同变体（24h 内）
2. **路由策略**：
   - `cheapest`：优先选择成本最低的模型（qwen-turbo: $0.002/1k tokens）
   - `fastest`：优先选择延迟最低的模型（gpt-3.5-turbo: P95 <1s）
   - `best_quality`：优先选择质量最高的模型（gpt-4: SOTA）
3. **健康检查**：每 60 秒探测模型可用性，连续 5 次失败标记为 unhealthy（5min）
4. **熔断器**：模型失败率 >20% 触发熔断，自动切换到备用模型
5. **预算控制**：租户级别的月度预算（Redis 计数器），超预算后降级或拒绝请求
6. **指标记录**：记录每次调用的成功率、延迟、成本、Token 使用量，用于 A/B 测试分析
7. **降级策略**：
   - 预算不足：gpt-4 → gpt-3.5-turbo → qwen-turbo
   - 模型不可用：主模型 → 备用模型1 → 备用模型2
8. **元数据透传**：响应中包含实际使用的模型和变体信息，便于问题排查

---

## 模块交互矩阵

| 调用方 → 被调方 | Identity Service | Conversation Service | AI Orchestrator | Model Router | Agent Engine | RAG Engine | Retrieval Service | Model Adapter | PostgreSQL | Redis | Milvus | Kafka |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Istio Gateway** | gRPC<br/>同步<br/>JWT 验证<br/>强一致性 | gRPC<br/>同步<br/>对话操作<br/>强一致性 | gRPC<br/>同步<br/>AI 任务<br/>最终一致性 | — | — | — | — | — | — | — | — | — |
| **Conversation Service** | gRPC<br/>同步<br/>Token 验证<br/>强一致性 | — | gRPC<br/>同步<br/>AI 处理<br/>最终一致性 | — | — | — | — | — | SQL<br/>同步<br/>对话数据<br/>强一致性 | TCP<br/>同步<br/>上下文缓存<br/>最终一致性 | — | Kafka<br/>异步<br/>消息事件<br/>最终一致性 |
| **AI Orchestrator** | — | — | — | gRPC<br/>同步<br/>模型路由<br/>最终一致性 | HTTP<br/>同步<br/>Agent 任务<br/>最终一致性 | HTTP<br/>同步<br/>RAG 查询<br/>最终一致性 | — | — | — | — | — | — |
| **Model Router** | — | — | — | — | — | — | — | HTTP<br/>同步<br/>LLM 调用<br/>最终一致性 | SQL<br/>同步<br/>A/B 测试<br/>强一致性 | TCP<br/>同步<br/>健康状态<br/>最终一致性 | — | — |
| **Agent Engine** | — | — | — | — | — | HTTP<br/>同步<br/>知识检索<br/>最终一致性 | — | HTTP<br/>同步<br/>LLM 推理<br/>最终一致性 | — | TCP<br/>同步<br/>工具缓存<br/>最终一致性 | — | — |
| **RAG Engine** | — | — | — | — | — | — | HTTP<br/>同步<br/>混合检索<br/>最终一致性 | HTTP<br/>同步<br/>生成答案<br/>最终一致性 | — | TCP<br/>同步<br/>语义缓存<br/>最终一致性 | HTTP<br/>同步<br/>向量查询<br/>最终一致性 | — |
| **Retrieval Service** | — | — | — | — | — | — | — | — | — | — | gRPC<br/>同步<br/>向量检索<br/>最终一致性 | — |
| **Analytics Service** | — | gRPC<br/>同步<br/>对话统计<br/>最终一致性 | — | — | — | — | — | — | — | — | — | Kafka<br/>异步<br/>消费指标<br/>最终一致性 |

### 交互矩阵说明

#### 1. 协议选择

- **Go ↔ Go**：使用 gRPC，性能优越（延迟 1-2ms），强类型安全
- **Go ↔ Python**：使用 HTTP/JSON，生态成熟，便于调试（延迟 3-5ms）
- **Python ↔ Python**：使用 HTTP/JSON，FastAPI 原生支持
- **服务 ↔ 数据库**：PostgreSQL 使用 SQL（GORM/SQLAlchemy ORM），Redis 使用 TCP 协议客户端

#### 2. 同步 vs 异步

- **同步调用**：所有 API 请求路径（用户等待响应），超时时间 30s-60s
- **异步调用**：日志上报、指标收集、事件通知（通过 Kafka），无需等待

#### 3. 错误语义

- **gRPC 错误**：使用标准 gRPC Status Codes（INVALID_ARGUMENT、NOT_FOUND、UNAVAILABLE）
- **HTTP 错误**：4xx（客户端错误）、5xx（服务端错误）+ 统一错误响应格式
  ```json
  {
    "code": 40001,
    "message": "Invalid conversation ID",
    "details": {"conversation_id": "abc123"}
  }
  ```
- **重试逻辑**：幂等操作（GET/PUT）自动重试 3 次，非幂等操作（POST）需显式传递幂等键

#### 4. 一致性要求

- **强一致性**：
  - 用户认证（Identity → PostgreSQL）：必须立即生效
  - 对话持久化（Conversation → PostgreSQL）：消息不能丢失
  - A/B 测试配置（Model Router → PostgreSQL）：变体分配必须准确

- **最终一致性**：
  - 语义缓存（RAG → Redis）：缓存失效允许短暂不一致（最多 1 小时）
  - 指标统计（Analytics → ClickHouse）：延迟 5-10 秒可接受
  - 模型健康状态（Model Router → Redis）：60 秒内最终一致

- **因果一致性**：
  - 对话上下文（Conversation → Redis）：同一会话内的消息顺序必须保证

---

## 关键设计与权衡

### 1. 一致性、事务与并发控制

#### 分布式事务（Saga 模式）

VoiceHelper 使用 Saga 模式处理跨服务的分布式事务，避免两阶段提交（2PC）的性能开销。

**场景：创建对话并调用 AI 服务**

```
Conversation Service: 创建会话记录 (PostgreSQL)
   ↓ （成功）
AI Orchestrator: 调用 Agent Engine
   ↓ （失败）
Compensation: 删除会话记录 或 标记为失败状态
```

**实现**：
- 使用 Kafka 作为事件总线，记录 Saga 状态
- 每个服务实现 Compensating Transaction（补偿事务）
- 超时机制：30 秒未完成自动触发补偿

**权衡**：
- ✅ 优点：高可用，无单点故障，服务解耦
- ❌ 缺点：最终一致性，需要处理重复消息（幂等性）

#### 乐观锁与悲观锁

- **乐观锁**：用于高并发读多写少场景（如用户信息更新）
  - 实现：`UPDATE users SET ... WHERE id=? AND version=?`
  - 冲突时返回 409 Conflict，客户端重试

- **悲观锁**：用于关键资源竞争场景（如预算扣减）
  - 实现：`SELECT ... FOR UPDATE`
  - Redis 分布式锁：`SETNX budget_lock:{tenant_id} 1 EX 10`

#### 幂等性保证

所有写操作要求客户端传递 `Idempotency-Key`（UUID），服务端基于 Redis 存储已处理的键（TTL 24 小时）：

```go
idempotencyKey := request.Header.Get("Idempotency-Key")
exists := redis.Exists(ctx, "idempotency:"+idempotencyKey)
if exists {
    return cachedResponse // 返回缓存的响应
}
// 处理请求
redis.Set(ctx, "idempotency:"+idempotencyKey, response, 24*time.Hour)
```

### 2. 性能关键路径与可观测性

#### 性能关键路径识别

通过 Jaeger 分布式追踪，识别出系统的性能瓶颈：

1. **RAG 查询路径**：占总延迟的 60%
   - 向量检索（Milvus）：500ms
   - Cross-Encoder 重排：300ms
   - LLM 生成：800ms

   **优化措施**：
   - 语义缓存命中率从 20% 提升到 60%（节省 70% 延迟）
   - 批量 Embedding（Batch=32）减少 API 调用次数
   - 上下文压缩节省 30% Token，降低 LLM 延迟

2. **Agent 执行路径**：平均 3.5 步推理
   - 每步 LLM 调用：1.2s
   - 工具执行（API 调用）：0.8s

   **优化措施**：
   - 工具调用结果缓存（Redis，TTL 1 小时）
   - 并行执行无依赖的工具调用

3. **对话上下文加载**：高频操作
   - Redis 缓存命中：<10ms
   - PostgreSQL 查询：100-200ms

   **优化措施**：
   - 上下文缓存（30min TTL）
   - 数据库连接池优化（最大 50 连接/Pod）

#### 全链路追踪

- **OpenTelemetry**：统一追踪 SDK，支持 Go 和 Python
- **Trace Context 传播**：通过 HTTP Header（`traceparent`）和 gRPC Metadata 传递
- **Span 标注**：
  - 服务入口：`span.kind = SERVER`
  - 外部调用：`span.kind = CLIENT`
  - 数据库查询：`db.system = postgresql`
  - LLM 调用：`llm.model = gpt-4`, `llm.tokens = 1500`

#### Prometheus 指标体系

**RED 指标**（面向用户）：
- **Rate**（速率）：`rate(http_requests_total[5m])`
- **Errors**（错误率）：`rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`
- **Duration**（延迟）：`histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`

**USE 指标**（面向资源）：
- **Utilization**（利用率）：CPU、内存、磁盘使用率
- **Saturation**（饱和度）：连接池排队、线程池排队
- **Errors**（错误）：数据库连接失败、OOM 事件

**业务指标**：
- 对话成功率：`conversation_success_rate`
- RAG 缓存命中率：`rag_cache_hit_ratio`
- LLM 成本：`llm_cost_usd_total`
- Agent 平均步骤数：`agent_avg_steps`

### 3. 配置管理（Nacos）

#### 配置分层

```
VoiceHelper 配置体系
├── 环境级（Namespace）
│   ├── dev（开发环境）
│   ├── staging（测试环境）
│   └── prod（生产环境）
├── 服务组（Group）
│   ├── VoiceHelper（业务服务配置）
│   └── VoiceHelper-Common（公共配置）
└── 数据集（DataID）
    ├── conversation-service.yaml
    ├── rag-engine.yaml
    ├── resilience.yaml（熔断器/重试）
    ├── observability.yaml（追踪/指标）
    └── models.yaml（模型配置）
```

#### 配置热更新

- **监听机制**：服务订阅 Nacos 配置，变更后 5 秒内自动推送
- **灰度发布**：先更新 1 个 Pod，观察 5 分钟无异常后再全量发布
- **回滚策略**：Nacos 保留 30 天配置历史，支持一键回滚

#### 敏感配置

- 数据库密码、JWT Secret、LLM API Key 不存储在 Nacos
- 使用 Kubernetes Secrets + 环境变量注入
- 定期轮换（90 天）

### 4. 容量规划与扩展性

#### 当前容量（单集群）

| 资源 | 规格 | 数量 | 总容量 |
|---|---|---|---|
| Kubernetes 节点 | 8 核 CPU / 16 GB 内存 | 10 | 80 核 / 160 GB |
| Go 服务 Pod | 2 核 / 4 GB | 30 | 60 核 / 120 GB |
| Python 服务 Pod | 4 核 / 8 GB | 15 | 60 核 / 120 GB |
| PostgreSQL | 16 核 / 64 GB | 1（主）+ 2（从） | 读 30k QPS / 写 5k QPS |
| Redis | 16 核 / 64 GB | 3 节点集群 | 300k ops/s |
| Milvus | 32 核 / 128 GB | 3 节点集群 | 30k 向量查询/s |

**支持并发**：
- 对话 API：5000 RPS（P95 <200ms）
- RAG 查询：2000 RPS（P95 <2.5s）
- Agent 任务：500 RPS（P95 <5s）

#### 扩展策略

**水平扩展**（Stateless 服务）：
- 使用 Kubernetes HPA（Horizontal Pod Autoscaler）
- CPU 利用率 >70% 自动扩容
- 自定义指标扩容（如 RPS、队列长度）

**垂直扩展**（Stateful 服务）：
- PostgreSQL：读写分离，主库写，从库读（最多 5 个从库）
- Redis：Cluster 模式，16384 哈希槽分片
- Milvus：Collection 分片，每个分片 1000 万向量

**多集群部署**：
- Istio 多集群联邦：跨区域流量路由
- 数据库跨区域异步复制（RPO <5min）
- CDN 加速静态资源

---

## 非功能性需求（NFR）

### 1. 性能目标（SLO）

| 指标 | 目标值 | 当前值 | 测量方法 |
|---|---|---|---|
| API Gateway P95 延迟 | <200ms | 150ms | Prometheus `http_request_duration_seconds{quantile="0.95"}` |
| 对话消息发送 P95 延迟 | <1s | 800ms | 包含 AI 处理时间 |
| RAG 查询 P95 延迟 | <2.5s | 2.2s | 端到端（检索 + 生成） |
| 语音 TTFB | <300ms | 280ms | WebSocket 首帧延迟 |
| 系统可用性 | ≥99.9% | 99.95% | Uptime = (Total Time - Downtime) / Total Time |
| 错误率 | <0.1% | 0.05% | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])` |

### 2. 可靠性保障

**故障自愈**：
- Kubernetes Liveness Probe：检测服务存活，失败后自动重启
- Readiness Probe：检测服务就绪，未就绪不接收流量
- PodDisruptionBudget：滚动更新时保证至少 80% Pod 可用

**数据可靠性**：
- PostgreSQL：主从同步复制，RPO=0（零数据丢失）
- Milvus：3 副本，数据分片均匀分布
- MinIO：纠删码（EC 8+4），容忍 4 块磁盘故障

**备份策略**：
- PostgreSQL：每日全量备份 + 实时 WAL 归档，保留 30 天
- Milvus：每周全量快照，保留 4 周
- 配置文件：Git 版本控制 + Nacos 历史记录

### 3. 安全性

**认证与授权**：
- JWT Token（RS256 非对称加密）
- RBAC 权限模型（角色-权限-资源）
- 多租户数据隔离（tenant_id 过滤）

**网络安全**：
- Istio mTLS：服务间通信全加密（STRICT 模式）
- Network Policy：Pod 级别网络隔离
- WAF（Web Application Firewall）：OWASP Top 10 防护

**数据安全**：
- PII 脱敏：日志和监控数据自动脱敏（手机号、邮箱）
- 数据库加密：TDE（Transparent Data Encryption）
- 静态数据加密：MinIO SSE-S3（AES-256）

### 4. 可维护性

**日志管理**：
- 结构化日志（JSON 格式）
- 日志级别：DEBUG（开发）/ INFO（生产）/ ERROR（告警）
- 日志聚合：Kafka → Elasticsearch（保留 7 天）

**告警规则**：
- P0（紧急）：可用性 <99%，5 分钟内响应
- P1（严重）：错误率 >1%，15 分钟内响应
- P2（警告）：延迟 P95 >3s，1 小时内响应

**灰度发布**：
- Istio VirtualService 权重路由
- 10% → 30% → 50% → 100%（每阶段观察 1 小时）
- 自动回滚：错误率 >1% 或延迟劣化 >20%

---

## 部署架构

### Kubernetes + Istio 部署拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Namespace: istio-system                      │  │
│  │  ┌────────────────┐  ┌────────────────┐              │  │
│  │  │ Istio Gateway  │  │ Istiod         │              │  │
│  │  │ (3-10 Pods)    │  │ (控制平面)      │              │  │
│  │  └────────────────┘  └────────────────┘              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │        Namespace: voiceassistant-prod                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐      │  │
│  │  │ Identity   │  │ Conversation│ │ AIOrch     │      │  │
│  │  │ Service    │  │ Service    │  │ Service    │      │  │
│  │  │ (3 Pods)   │  │ (5 Pods)   │  │ (3 Pods)   │      │  │
│  │  │ + Envoy    │  │ + Envoy    │  │ + Envoy    │      │  │
│  │  └────────────┘  └────────────┘  └────────────┘      │  │
│  │                                                         │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐      │  │
│  │  │ Agent      │  │ RAG        │  │ Model      │      │  │
│  │  │ Engine     │  │ Engine     │  │ Adapter    │      │  │
│  │  │ (3 Pods)   │  │ (5 Pods)   │  │ (3 Pods)   │      │  │
│  │  │ + Envoy    │  │ + Envoy    │  │ + Envoy    │      │  │
│  │  └────────────┘  └────────────┘  └────────────┘      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Namespace: voiceassistant-infra               │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │  │
│  │  │PostgreSQL│ │ Redis   │  │ Milvus  │  │ Kafka   │  │  │
│  │  │(1M + 2S) │ │ (3 节点) │  │ (3 节点) │  │ (3 节点) │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Namespace: monitoring                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│  │  │Prometheus│  │ Grafana  │  │ Jaeger   │            │  │
│  │  └──────────┘  └──────────┘  └──────────┘            │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 资源配置示例（Kubernetes YAML）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: conversation-service
  namespace: voiceassistant-prod
  labels:
    app: conversation-service
    version: v1
spec:
  replicas: 5
  selector:
    matchLabels:
      app: conversation-service
  template:
    metadata:
      labels:
        app: conversation-service
        version: v1
      annotations:
        sidecar.istio.io/inject: "true"  # 启用 Sidecar 注入
    spec:
      containers:
      - name: conversation-service
        image: voicehelper/conversation-service:v1.2.3
        ports:
        - containerPort: 8080
          name: http
          protocol: TCP
        - containerPort: 50052
          name: grpc
          protocol: TCP
        env:
        - name: CONFIG_MODE
          value: "nacos"
        - name: NACOS_SERVER_ADDR
          value: "nacos.voiceassistant-infra.svc.cluster.local"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        resources:
          requests:
            cpu: "500m"
            memory: "1Gi"
          limits:
            cpu: "2000m"
            memory: "4Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: conversation-service-hpa
  namespace: voiceassistant-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: conversation-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 监控与告警

### Grafana Dashboard

核心监控面板：

1. **系统总览**：
   - 总 QPS、错误率、P95 延迟
   - 各服务健康状态（绿/黄/红）
   - 数据库连接池使用率

2. **服务性能**：
   - Identity Service：登录成功率、Token 验证延迟
   - Conversation Service：消息吞吐量、上下文缓存命中率
   - AI Orchestrator：任务分发延迟、Agent/RAG 路由比例

3. **AI 服务**：
   - RAG Engine：检索召回率、重排提升、缓存命中率
   - Agent Engine：平均步骤数、工具调用分布、成功率
   - Model Adapter：模型调用分布、成本统计、Token 使用

4. **基础设施**：
   - PostgreSQL：QPS、连接数、慢查询
   - Redis：命中率、内存使用、键空间
   - Milvus：向量查询 QPS、索引大小、召回率

### 告警规则（Prometheus AlertManager）

```yaml
groups:
- name: voicehelper_critical
  interval: 30s
  rules:
  # 可用性告警
  - alert: ServiceDown
    expr: up{job=~".*-service"} == 0
    for: 2m
    labels:
      severity: P0
    annotations:
      summary: "服务不可用: {{ $labels.job }}"
      description: "{{ $labels.job }} 已宕机超过 2 分钟"

  # 错误率告警
  - alert: HighErrorRate
    expr: |
      rate(http_requests_total{status=~"5.."}[5m])
      / rate(http_requests_total[5m]) > 0.01
    for: 5m
    labels:
      severity: P1
    annotations:
      summary: "错误率过高: {{ $labels.service }}"
      description: "{{ $labels.service }} 错误率超过 1%"

  # 延迟告警
  - alert: HighLatency
    expr: |
      histogram_quantile(0.95,
        rate(http_request_duration_seconds_bucket[5m])
      ) > 3.0
    for: 10m
    labels:
      severity: P2
    annotations:
      summary: "延迟过高: {{ $labels.service }}"
      description: "{{ $labels.service }} P95 延迟超过 3 秒"

  # 成本告警
  - alert: BudgetExceeded
    expr: |
      sum by (tenant_id) (llm_cost_usd_total)
      > on(tenant_id) tenant_budget_limit_usd
    for: 1h
    labels:
      severity: P2
    annotations:
      summary: "租户预算超限: {{ $labels.tenant_id }}"
      description: "租户 {{ $labels.tenant_id }} 本月成本已超预算"
```

---

## 总结

VoiceHelper 是一个基于微服务架构、服务网格、混合语言技术栈的企业级 AI 客服平台。核心设计原则包括：

1. **前后端分离**：Go 负责业务编排和数据管理，Python 负责 AI 算法能力
2. **服务网格流量管理**：Istio + Envoy 实现限流、熔断、mTLS、可观测性
3. **混合检索增强**：Vector + BM25 + Graph RAG + Self-RAG，召回率和准确率显著提升
4. **智能体协作**：ReAct、Plan-Execute、Multi-Agent、LangGraph 支持复杂任务自动化
5. **成本优化**：模型路由、A/B 测试、预算控制、上下文压缩节省 30% Token
6. **全链路可观测性**：OpenTelemetry + Prometheus + Grafana + Jaeger 完整监控体系

系统当前支持 5000 并发对话（P95 <1s）、2000 RAG 查询/秒（P95 <2.5s），可用性达到 99.95%，满足企业级生产要求。
