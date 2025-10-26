# VoiceHelper AI 微服务架构 v2.0

## 概览

VoiceHelper AI 采用基于领域驱动设计（DDD）的云原生微服务架构，利用 Kratos（Go）和 FastAPI（Python）双栈实现。

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                  Client Applications                         │
│           (Web, Mobile, Voice Assistants)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Apache APISIX API Gateway                       │
│  • 动态路由  • 限流熔断  • 认证授权  • 链路追踪             │
└────────────┬───────────────────────────┬────────────────────┘
             │                           │
    ┌────────▼──────────┐       ┌───────▼─────────┐
    │   Go 微服务层     │       │ Python AI 引擎   │
    │   (Kratos gRPC)   │       │  (FastAPI)       │
    ├───────────────────┤       ├──────────────────┤
    │ Identity Service  │       │ Agent Engine     │
    │ Conversation Svc  │       │ RAG Engine       │
    │ Knowledge Service │       │ Voice Engine     │
    │ AI Orchestrator   │       │ Retrieval Svc    │
    │ Model Router      │       │ Indexing Svc     │
    │ Notification Svc  │       │ Multimodal Eng   │
    │ Analytics Service │       │ Model Adapter    │
    └────────┬──────────┘       └───────┬──────────┘
             │                           │
             └────────────┬──────────────┘
                          │
         ┌────────────────▼───────────────────┐
         │       事件总线 (Kafka)             │
         │    + CDC (Debezium)                │
         │    + 流计算 (Flink)                │
         └────────────────┬───────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
┌───▼────┐  ┌──────▼──────┐  ┌────▼─────┐  ┌──▼───┐
│PostgreSQL│ │   Milvus    │  │ClickHouse│  │Neo4j│
│  (OLTP)  │ │  (向量检索)  │  │  (OLAP)  │  │(图谱)│
└──────────┘ └─────────────┘  └──────────┘  └─────┘
```

## 服务职责

### Go 微服务层（Kratos）

1. **Identity Service** - 用户域
   - 用户认证与授权
   - JWT Token 管理
   - 租户管理
   - RBAC 权限控制

2. **Conversation Service** - 对话域
   - 会话管理
   - 消息存储
   - 上下文管理
   - 对话状态机

3. **Knowledge Service** - 知识域
   - 文档管理
   - 版本控制
   - 访问控制
   - 元数据管理

4. **AI Orchestrator** - AI 编排
   - 任务编排
   - 流程控制
   - 服务调度
   - 状态管理

5. **Model Router** - 模型路由
   - 模型选择
   - 负载均衡
   - 成本优化
   - 自动降级

6. **Notification Service** - 通知域
   - 消息推送
   - 邮件发送
   - Webhook 回调
   - 通知模板

7. **Analytics Service** - 分析域
   - 实时统计
   - 报表生成
   - 数据聚合
   - 成本分析

### Python AI 引擎层（FastAPI）

1. **Agent Engine** - Agent 执行
   - LangGraph 编排
   - ReAct 模式
   - 工具调用
   - 自我反思

2. **RAG Engine** - 检索增强生成
   - 混合检索
   - 上下文压缩
   - 语义缓存
   - 结果重排

3. **Indexing Service** - 索引服务
   - 文档解析
   - 文本分块
   - 向量化
   - 图谱构建

4. **Retrieval Service** - 检索服务
   - 向量检索（Milvus）
   - BM25 检索
   - RRF 融合
   - Cross-Encoder 重排

5. **Voice Engine** - 语音引擎
   - ASR（Whisper）
   - TTS（Edge TTS）
   - VAD（Silero）
   - 编解码

6. **Multimodal Engine** - 多模态引擎
   - OCR
   - 图像理解
   - 视频分析
   - 多模态融合

7. **Model Adapter** - 模型适配器
   - API 适配
   - 协议转换
   - Token 计数
   - 成本追踪

## 数据流

### 1. 对话流程

```
User → APISIX → Conversation Service → AI Orchestrator
                                      ↓
                            Agent Engine / RAG Engine
                                      ↓
                          Model Adapter → LLM API
                                      ↓
                          Response → User
```

### 2. 知识入库流程

```
User → APISIX → Knowledge Service → MinIO
                      ↓
                  Kafka (document.uploaded)
                      ↓
            Indexing Service (subscribe)
                      ↓
              Parse + Chunk + Vectorize
                      ↓
        Milvus (vectors) + Neo4j (graph)
                      ↓
            Kafka (document.indexed)
```

### 3. 实时分析流程

```
Conversation Service → PostgreSQL
            ↓
    Debezium CDC → Kafka
            ↓
    Flink (streaming)
            ↓
    ClickHouse (aggregated)
            ↓
    Analytics Service → Grafana
```

## 技术选型

### 通信协议
- **服务间**: gRPC (grpc-go)
- **前后端**: HTTP/2 + JSON
- **实时**: WebSocket / SSE

### 数据存储
- **OLTP**: PostgreSQL 15+
- **向量**: Milvus 2.3+
- **OLAP**: ClickHouse 23+
- **图谱**: Neo4j 5+
- **缓存**: Redis 7+
- **对象**: MinIO

### 消息与流
- **消息队列**: Kafka 3.6+
- **CDC**: Debezium 2.5+
- **流计算**: Flink 1.18+

### 基础设施
- **网关**: Apache APISIX 3.7+
- **编排**: Kubernetes 1.28+
- **部署**: Argo CD 2.9+
- **监控**: OpenTelemetry + Prometheus + Grafana
- **追踪**: Jaeger 1.52+

## 非功能性需求

### 性能
- API Gateway P95 < 100ms
- gRPC P95 < 50ms
- 向量检索 P95 < 10ms
- 端到端问答 < 2.5s
- 并发能力 ≥ 1k RPS

### 可用性
- SLA ≥ 99.95%
- 自动故障转移
- 金丝雀发布
- 自动回滚

### 可扩展性
- 水平扩展
- HPA 自动伸缩
- 无状态设计
- 事件驱动

### 安全性
- JWT 认证
- RBAC 授权
- TLS 加密
- PII 脱敏
- 审计日志

## 部署拓扑

### 生产环境
- 3 个 Availability Zones
- 每个服务 ≥ 3 副本
- PostgreSQL 主从复制
- Milvus 3 Shards + 2 Replicas
- Kafka 3 Brokers

### 开发环境
- Docker Compose
- 单机部署
- 本地数据库

## 下一步

- [API 文档](../api/API_OVERVIEW.md)
- [部署指南](../deployment/README.md)
- [运维手册](../runbook/README.md)

