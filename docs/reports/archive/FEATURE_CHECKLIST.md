# VoiceHelper 功能完善清单

> **基于源项目**: https://github.com/haoyunlt/voicehelper  
> **当前完成度**: ~30%  
> **更新时间**: 2025-10-26

---

## 📋 使用说明

- ✅ 已完成
- 🟡 进行中
- ❌ 未开始
- 🔥 高优先级
- ⭐ 中优先级
- 💡 低优先级

---

## 🏗️ 1. 基础设施 (60%)

### 1.1 数据存储
- [x] PostgreSQL 15 (带 WAL logical replication)
- [x] Redis 7 (带 persistence)
- [x] Neo4j 5 (带 APOC + GDS)
- [x] Milvus 2.3 (向量数据库)
- [x] ClickHouse 23 (OLAP)
- [x] MinIO (S3 存储)
- [ ] 🔥 Vault (密钥管理) - **P0**
- [ ] 🔥 ElasticSearch (BM25 检索) - **P1**

### 1.2 消息队列
- [x] Apache Kafka 3.6
- [ ] 🔥 RabbitMQ (任务队列) - **P0**, 源项目 v0.8.5 引入
- [ ] 🔥 Debezium (CDC) - **P1**

### 1.3 API 网关
- [x] Apache APISIX 3.7
- [x] etcd 3.5
- [ ] ⭐ APISIX 完整路由配置 - **P1**
- [ ] ⭐ APISIX 插件配置 (jwt-auth, limit-req, etc.) - **P1**

### 1.4 可观测性
- [x] Prometheus 2.48
- [x] Grafana 10.2
- [x] Jaeger 1.52
- [ ] 🔥 Loki + Promtail (日志) - **P1**
- [ ] ⭐ AlertManager - **P1**
- [ ] ⭐ OpenTelemetry Collector - **P1**

### 1.5 统一管理脚本
- [ ] 🔥 `voicehelper.sh` - 统一管理脚本 (参考源项目) - **P0**
  ```bash
  # 参考源项目功能
  ./voicehelper.sh start-dev      # 启动开发环境
  ./voicehelper.sh start-prod     # 启动生产环境
  ./voicehelper.sh status         # 查看状态
  ./voicehelper.sh logs SERVICE   # 查看日志
  ./voicehelper.sh test-api       # 测试 API
  ./voicehelper.sh clean-project  # 清理
  ```

---

## 🔧 2. Go 微服务 (30%)

### 2.1 Identity Service (40%)
- [x] Kratos 框架集成
- [x] 领域模型 (User, Tenant)
- [x] 业务层骨架
- [ ] 🔥 Wire 依赖注入完成 - **P0**
- [ ] 🔥 JWT 签发和验证 - **P0**
- [ ] 🔥 gRPC Service 实现 - **P0**
- [ ] ⭐ OAuth 2.0 / SSO - **P1**
- [ ] ⭐ RBAC 权限引擎 - **P1**
- [ ] ⭐ Redis 缓存集成 - **P1**
- [ ] 💡 单元测试 (70%+) - **P2**

**关键文件需完善**:
- `cmd/identity-service/wire_gen.go` - 缺失
- `internal/service/identity.go` - 需实现 proto service
- `internal/data/user_repo.go` - 需实现数据库操作

### 2.2 Conversation Service (35%)
- [x] 领域模型完整
- [x] Kafka Producer 集成
- [ ] 🔥 数据库 CRUD 实现 - **P0**
- [ ] 🔥 WebSocket/SSE 流式响应 - **P0**
- [ ] 🔥 调用 AI Orchestrator - **P0**
- [ ] ⭐ 会话上下文管理 - **P1**
- [ ] ⭐ 消息路由逻辑 - **P1**
- [ ] 💡 单元测试 - **P2**

### 2.3 Knowledge Service (30%)
- [x] 领域模型
- [ ] 🔥 MinIO 集成 (文件上传/下载) - **P0**
- [ ] 🔥 发布 Kafka 事件 - **P0**
- [ ] 🔥 数据库 CRUD 实现 - **P0**
- [ ] ⭐ 文档版本控制 - **P1**
- [ ] ⭐ 文档病毒扫描 (ClamAV) - **P2**
- [ ] 💡 权限校验 - **P2**

### 2.4 AI Orchestrator (5%)
- [ ] 🔥 任务编排引擎 - **P0**
- [ ] 🔥 gRPC 客户端 (Agent Engine) - **P0**
- [ ] 🔥 ReAct 流程控制 - **P0**
- [ ] ⭐ 流式响应聚合 - **P1**
- [ ] ⭐ 超时和取消处理 - **P1**
- [ ] 💡 成本追踪 - **P2**

### 2.5 Model Router (5%)
- [ ] 🔥 模型路由策略 (成本/延迟/可用性) - **P1**
- [ ] ⭐ 模型能力注册表 - **P1**
- [ ] ⭐ 动态降级逻辑 - **P2**
- [ ] 💡 成本预算管理 - **P2**

### 2.6 Notification Service (5%)
- [ ] ⭐ 多渠道通知 (邮件/短信/Webhook/WebSocket) - **P1**
- [ ] ⭐ 模板引擎 - **P1**
- [ ] ⭐ Kafka 消费者 - **P1**
- [ ] 💡 重试机制 - **P2**

### 2.7 Analytics Service (5%)
- [ ] ⭐ ClickHouse 客户端 - **P1**
- [ ] ⭐ 实时指标计算 - **P1**
- [ ] 💡 报表生成 API - **P2**
- [ ] 💡 成本看板 - **P2**

---

## 🐍 3. Python 微服务 (20%)

### 3.1 Agent Engine (20%)
- [x] FastAPI 框架
- [x] OpenTelemetry 追踪
- [x] Prometheus metrics
- [ ] 🔥 LangGraph workflow 实现 - **P0**
  ```python
  # 参考源项目结构
  - planner_node: 规划任务
  - executor_node: 执行工具
  - reflector_node: 反思结果
  ```
- [ ] 🔥 工具系统 (search, code_search, etc.) - **P0**
- [ ] ⭐ Agent 状态管理 - **P1**
- [ ] ⭐ Redis 长期记忆 - **P1**
- [ ] 💡 多 Agent 协作 - **P2**

**关键文件**:
- `algo/agent-engine/core/agent.py` - 需创建
- `algo/agent-engine/tools/` - 需创建
- `algo/agent-engine/workflows/` - 需创建

### 3.2 RAG Engine (10%)
- [ ] 🔥 检索增强生成流程 - **P0**
- [ ] 🔥 调用 Retrieval Service - **P0**
- [ ] ⭐ Prompt 模板管理 - **P1**
- [ ] ⭐ 上下文压缩 (LLMLingua) - **P1**
- [ ] ⭐ 引用来源生成 - **P1**
- [ ] 💡 语义缓存 - **P2**

### 3.3 Indexing Service (15%)
- [x] FastAPI 框架
- [ ] 🔥 Kafka Consumer (监听 document.events) - **P0**
- [ ] 🔥 文档解析器 - **P0**
  - PDF: PyPDF2 / pdfplumber
  - Word: python-docx
  - Excel: openpyxl
  - Markdown: mistune
- [ ] 🔥 文档分块 - **P0**
- [ ] 🔥 向量化 (BGE-M3) - **P0**
- [ ] 🔥 Milvus 客户端 - **P0**
- [ ] ⭐ Neo4j 客户端 (知识图谱) - **P1**
- [ ] 💡 批处理优化 - **P2**

**流程图**:
```
Kafka Event → MinIO Download → Parse Document 
→ Chunk Text → Vectorize (BGE-M3) → Milvus 
→ Build Graph (Neo4j) → Publish indexed event
```

### 3.4 Retrieval Service (15%)
- [ ] 🔥 Milvus 向量检索 - **P0**
- [ ] 🔥 BM25 检索 (ElasticSearch) - **P0**
- [ ] 🔥 混合检索融合 (RRF) - **P0**
- [ ] ⭐ 重排序 (Cross-Encoder) - **P1**
- [ ] ⭐ Neo4j 图谱查询 - **P1**
- [ ] ⭐ Redis 语义缓存 - **P1**
- [ ] 💡 标量过滤优化 - **P2**

**性能目标** (源项目):
- 向量检索 P95 < 10ms
- 混合检索 P95 < 50ms
- 缓存命中率 > 30%

### 3.5 Voice Engine (10%)
- [ ] 🔥 ASR (Whisper / Azure) - **P1**
  - 流式识别
  - 语言自动检测
- [ ] 🔥 VAD (Silero VAD) - **P1**
  - 端点检测
  - 噪声抑制
- [ ] ⭐ TTS (Edge TTS / Azure) - **P1**
  - 低延迟 (< 100ms)
  - 分片播放
- [ ] 💡 WebRTC 集成 - **P2**

**源项目指标**:
- 端到端延迟 < 3s
- VAD 准确率 > 95%

### 3.6 Multimodal Engine (10%)
- [ ] ⭐ OCR (Tesseract / Paddle OCR) - **P1**
- [ ] ⭐ 图像理解 (GPT-4V) - **P1**
- [ ] 💡 视频分析 - **P2**
- [ ] 💡 表格识别 - **P2**

### 3.7 Model Adapter (10%)
- [ ] 🔥 统一接口 (OpenAI API 格式) - **P0**
- [ ] 🔥 多 Provider 适配 - **P0**
  - OpenAI (GPT-4)
  - Anthropic (Claude 3)
  - 智谱 AI (ChatGLM)
- [ ] ⭐ 协议转换 - **P1**
- [ ] ⭐ Token 计数 - **P1**
- [ ] 💡 成本计算 - **P2**

---

## 📡 4. 事件驱动架构 (40%)

### 4.1 Kafka
- [x] Kafka 3.6 部署
- [ ] 🔥 Topic 初始化脚本 - **P0**
  ```yaml
  topics:
    - conversation.events (partitions: 6)
    - document.events (partitions: 3)
    - ai.tasks (partitions: 12)
    - identity.events (partitions: 3)
  ```
- [ ] 🔥 Event Schema 定义 - **P0**
- [ ] ⭐ Event 序列化 (Avro / Protobuf) - **P1**

### 4.2 Debezium CDC
- [ ] 🔥 Debezium Connector 配置 - **P1**
- [ ] 🔥 PostgreSQL CDC 启用 - **P1**
  ```sql
  ALTER SYSTEM SET wal_level = logical;
  CREATE PUBLICATION voicehelper_pub FOR TABLE 
    conversation.messages, 
    knowledge.documents;
  ```
- [ ] ⭐ CDC 监控 - **P2**

### 4.3 RabbitMQ (源项目 v0.8.5+)
- [ ] 🔥 RabbitMQ 部署 - **P0**
- [ ] 🔥 任务队列定义 - **P0**
  ```yaml
  queues:
    - ai_tasks (durable)
    - document_processing (durable)
    - notification_queue (durable)
  ```
- [ ] ⭐ 死信队列处理 - **P1**

---

## ⚡ 5. Flink 流处理 (15%)

### 5.1 Message Stats Job
- [ ] 🔥 实时消息统计 - **P1**
  ```python
  Kafka[conversation.messages] 
  → Window (1h tumbling)
  → Aggregate (count, avg_length)
  → ClickHouse[message_events_hourly]
  ```

### 5.2 User Behavior Job
- [ ] ⭐ 用户行为分析 - **P1**
  ```python
  Kafka[identity.events + conversation.events]
  → Join (user_id)
  → Session Window (30min)
  → ClickHouse[user_behavior_stats]
  ```

### 5.3 Document Analysis Job
- [ ] ⭐ 文档统计 - **P1**
  ```python
  Kafka[document.events]
  → Aggregate by tenant
  → ClickHouse[document_stats]
  ```

### 5.4 Flink 部署
- [ ] ⭐ Flink Kubernetes Operator - **P1**
- [ ] ⭐ Checkpoint 配置 - **P1**
- [ ] 💡 资源配置优化 - **P2**

---

## 🎨 6. 前端开发 (10%)

### 6.1 Web Platform (Next.js 14)
- [x] 项目结构
- [x] Tailwind CSS
- [ ] 🔥 对话界面 (`/chat`) - **P1**
  - 消息列表
  - 流式响应显示
  - Markdown 渲染
  - 代码高亮
- [ ] ⭐ 知识库管理 (`/knowledge`) - **P1**
  - 文档上传
  - 文档列表
  - 删除/编辑
- [ ] ⭐ 分析看板 (`/analytics`) - **P2**
- [ ] 💡 设置页面 (`/settings`) - **P2**

### 6.2 核心组件
- [ ] 🔥 ChatBox 组件 - **P1**
- [ ] 🔥 DocumentUploader 组件 - **P1**
- [ ] ⭐ VoiceRecorder 组件 - **P2**
- [ ] ⭐ MarkdownRenderer 组件 - **P1**

### 6.3 状态管理
- [ ] ⭐ Zustand / Jotai - **P1**
- [ ] ⭐ React Query (API 客户端) - **P1**

### 6.4 实时通信
- [ ] 🔥 WebSocket 集成 - **P1**
- [ ] ⭐ SSE 流式响应 - **P1**

### 6.5 Admin Platform
- [ ] 💡 用户管理 - **P2**
- [ ] 💡 租户管理 - **P2**
- [ ] 💡 系统配置 - **P2**

---

## 🔐 7. 安全与认证 (25%)

### 7.1 认证
- [ ] 🔥 JWT 签发 - **P0**
- [ ] 🔥 JWT 验证 (APISIX jwt-auth) - **P0**
- [ ] ⭐ Refresh Token - **P1**
- [ ] 💡 OAuth 2.0 / SSO - **P2**

### 7.2 授权
- [ ] 🔥 RBAC 引擎 - **P1**
  - 角色定义 (Admin, User, Guest)
  - 权限策略
  - 租户隔离
- [ ] ⭐ API 权限校验 - **P1**

### 7.3 密钥管理
- [ ] 🔥 Vault 集成 - **P1**
  - 数据库密码
  - JWT Secret
  - API Keys
- [ ] ⭐ 密钥自动轮换 - **P2**

### 7.4 数据安全
- [ ] ⭐ PII 脱敏 (日志/追踪) - **P1**
- [ ] ⭐ 审计日志 - **P1**
- [ ] 💡 数据加密 (静态/传输) - **P2**

### 7.5 文档
- [ ] 💡 威胁模型文档 - **P2**

---

## 📊 8. 可观测性 (50%)

### 8.1 Grafana Dashboards (源项目有 5+)
- [ ] 🔥 系统概览 Dashboard - **P1**
  - CPU/Memory/Network/Disk
- [ ] 🔥 API 性能 Dashboard - **P1**
  - QPS/延迟/错误率/P95/P99
- [ ] ⭐ 业务指标 Dashboard - **P1**
  - 用户活跃度/消息数/文档数
- [ ] ⭐ LLM 监控 Dashboard - **P1**
  - 模型使用/Token 消耗/成本分析
- [ ] 💡 任务监控 Dashboard - **P2**

### 8.2 Prometheus 业务指标
- [ ] 🔥 对话成功率 - **P1**
  ```go
  conversation_success_rate{mode="voice|text"}
  ```
- [ ] 🔥 向量检索延迟 - **P1**
  ```go
  milvus_search_duration_seconds{collection="documents"}
  ```
- [ ] 🔥 LLM 成本追踪 - **P1**
  ```go
  llm_cost_dollars_total{model="gpt-4", provider="openai"}
  llm_tokens_consumed_total{model="gpt-4"}
  ```
- [ ] ⭐ 语音会话指标 - **P2**

### 8.3 告警规则
- [ ] ⭐ AlertManager 配置 - **P1**
- [ ] ⭐ 告警规则 - **P1**
  - 错误率 > 1%
  - P95 延迟 > 500ms
  - 成本超限
  - 服务不可用
- [ ] 💡 告警通知渠道 (Slack/邮件) - **P2**

### 8.4 日志聚合
- [ ] 🔥 Loki + Promtail 部署 - **P1**
- [ ] ⭐ 结构化日志格式 - **P1**
  ```json
  {
    "timestamp": "2025-10-26T10:30:45Z",
    "level": "info",
    "service": "conversation-service",
    "trace_id": "abc123",
    "user_id": "usr_***",
    "message": "..."
  }
  ```
- [ ] 💡 日志查询优化 - **P2**

### 8.5 链路追踪
- [x] Jaeger 部署
- [ ] ⭐ 全服务 OpenTelemetry 集成 - **P1**
- [ ] 💡 自定义 Span 属性 - **P2**

---

## 🚀 9. CI/CD Pipeline (0%)

### 9.1 GitHub Actions
- [ ] 🔥 `.github/workflows/ci.yml` - **P1**
  ```yaml
  - Lint (golangci-lint, ruff, eslint)
  - Unit Test (Go, Python, TypeScript)
  - Coverage Report (Codecov)
  ```
- [ ] 🔥 `.github/workflows/build.yml` - **P1**
  ```yaml
  - Build Docker Images
  - Tag with git SHA
  - Push to Registry
  - Scan Images (Trivy)
  ```
- [ ] ⭐ `.github/workflows/deploy.yml` - **P1**
  ```yaml
  - Deploy to Dev (on merge to develop)
  - Deploy to Prod (on release tag)
  ```

### 9.2 模板
- [ ] ⭐ PR 模板 - **P1**
- [ ] 💡 Issue 模板 - **P2**

### 9.3 自动化
- [ ] 💡 semantic-release 版本管理 - **P2**

---

## 🎯 10. API Gateway (40%)

### 10.1 APISIX 路由
- [x] 基础 APISIX 配置
- [ ] 🔥 完整路由定义 - **P0**
  ```yaml
  # 14 个服务的路由
  - /api/v1/identity/*
  - /api/v1/conversation/*
  - /api/v1/knowledge/*
  - /api/v1/ai/*
  - ...
  ```

### 10.2 APISIX 插件
- [ ] 🔥 jwt-auth - **P0**
- [ ] 🔥 limit-req (限流) - **P0**
- [ ] ⭐ api-breaker (熔断) - **P1**
- [ ] ⭐ prometheus (监控) - **P1**
- [ ] ⭐ opentelemetry (追踪) - **P1**
- [ ] 💡 cors - **P1**

### 10.3 灰度发布
- [ ] ⭐ traffic-split 配置 - **P2**
  ```yaml
  # 金丝雀发布: 10% → 25% → 50% → 100%
  ```

---

## 🧪 11. 测试 (5%)

### 11.1 单元测试
- [ ] 🔥 Go 服务单元测试 (70%+ 覆盖率) - **P1**
  ```bash
  go test ./... -coverprofile=coverage.out
  ```
- [ ] 🔥 Python 服务单元测试 (70%+) - **P1**
  ```bash
  pytest --cov=algo
  ```
- [ ] ⭐ TypeScript 单元测试 - **P2**

### 11.2 集成测试
- [ ] ⭐ Go 集成测试 (dockertest) - **P1**
  ```go
  // 启动测试容器
  // 测试完整流程
  // 清理数据
  ```

### 11.3 E2E 测试
- [ ] ⭐ Playwright E2E 测试 - **P2**
  ```typescript
  // 用户登录 → 对话 → 上传文档
  ```

### 11.4 负载测试
- [ ] 💡 k6 负载测试脚本 - **P2**
  ```javascript
  // 1000 并发用户, 10 分钟
  // 检查 P95 < 500ms, 错误率 < 1%
  ```

---

## 📦 12. 部署 (30%)

### 12.1 Helm Charts
- [x] identity-service 模板
- [ ] 🔥 其余 13 个服务 Helm Charts - **P1**
- [ ] ⭐ values.yaml 完善 - **P1**
  ```yaml
  # HPA, Resources, Probes, etc.
  ```

### 12.2 Argo CD
- [ ] 🔥 Application 定义 (每个服务) - **P1**
- [ ] ⭐ AppProject 定义 - **P1**
- [ ] ⭐ 灰度发布配置 - **P2**

### 12.3 K8s 资源
- [ ] 🔥 ConfigMaps - **P1**
- [ ] 🔥 Secrets - **P1**
- [ ] 🔥 Services - **P1**
- [ ] 🔥 Deployments - **P1**
- [ ] ⭐ HPA - **P1**
- [ ] 💡 PodDisruptionBudget - **P2**
- [ ] 💡 NetworkPolicy - **P2**

### 12.4 Istio
- [ ] 💡 VirtualService - **P2**
- [ ] 💡 DestinationRule - **P2**
- [ ] 💡 Gateway - **P2**

### 12.5 脚本
- [ ] 🔥 `scripts/deploy/deploy.sh` - **P1**
- [ ] 🔥 `scripts/migration/migrate.sh` - **P1**
- [ ] 💡 backup.sh - **P2**

---

## 📝 13. 文档 (70%)

### 13.1 已完成 ✅
- [x] README.md
- [x] QUICKSTART.md
- [x] CONTRIBUTING.md
- [x] 架构设计文档 v2.0 (3227 行)
- [x] 迁移清单
- [x] .cursorrules (2000+ 行)

### 13.2 待完善
- [ ] 🔥 Runbook (每个服务) - **P1**
  ```markdown
  # 源项目有完整模板
  - 服务概述
  - 启动停止
  - 健康检查
  - 故障排查
  - 监控指标
  - 告警处理
  - 回滚步骤
  ```
- [ ] ⭐ API 文档 (OpenAPI 完善) - **P1**
- [ ] ⭐ ADR (架构决策记录) - **P2**
  - 为什么选择 Kratos
  - 为什么选择 Milvus
  - 为什么选择 APISIX
- [ ] 💡 评测基准集 - **P2**
- [ ] 💡 威胁模型文档 - **P2**

---

## 🔧 14. 数据库 & 迁移 (40%)

### 14.1 PostgreSQL
- [x] 基础 Schema (4 个迁移文件)
- [ ] 🔥 完整迁移文件 - **P0**
- [ ] 🔥 Seeding 脚本 - **P1**

### 14.2 ClickHouse
- [x] 基础表 (message_events)
- [ ] ⭐ 物化视图 (按小时/天聚合) - **P1**
- [ ] ⭐ 分布式表 - **P1**

### 14.3 Neo4j
- [ ] ⭐ Cypher 迁移脚本 - **P1**
- [ ] 💡 图谱初始化 - **P2**

### 14.4 迁移工具
- [ ] 🔥 `scripts/migration/migrate.sh` - **P1**
  ```bash
  ./migrate.sh up    # 升级
  ./migrate.sh down  # 回滚
  ```

---

## 📋 15. Proto & gRPC (50%)

### 15.1 Proto 文件
- [x] identity.proto
- [x] conversation.proto
- [x] knowledge.proto
- [ ] 🔥 orchestrator.proto - **P0**
- [ ] 🔥 router.proto - **P0**
- [ ] 🔥 analytics.proto - **P0**
- [ ] 🔥 notification.proto - **P0**

### 15.2 代码生成
- [ ] 🔥 生成所有 gRPC 代码 - **P0**
  ```bash
  ./scripts/proto-gen.sh
  ```

### 15.3 gRPC-Gateway
- [ ] ⭐ gRPC-Gateway 集成 - **P1**
- [ ] ⭐ OpenAPI 自动生成 - **P1**

### 15.4 Schema Registry
- [ ] 💡 Buf Schema Registry - **P2**

---

## 🎯 优先级路线图

### Week 1: P0 任务 (基础打通)
1. ✅ 完成 Go 服务 Wire 依赖注入
2. ✅ 完成所有 Proto 定义和代码生成
3. ✅ Identity Service JWT 实现
4. ✅ Indexing Service Kafka 消费 + Milvus 存储
5. ✅ 添加 RabbitMQ 到 docker-compose
6. ✅ 创建 voicehelper.sh 管理脚本

### Week 2: P1 任务 (核心功能)
1. ✅ Conversation Service 完整流程
2. ✅ Retrieval Service 向量检索
3. ✅ Agent Engine 基础 LangGraph
4. ✅ Knowledge Service MinIO + Kafka
5. ✅ APISIX 完整路由 + 插件
6. ✅ Grafana Dashboard (2-3 个)

### Week 3: P1 + P2 任务 (测试与监控)
1. ✅ 单元测试 (30%+ 覆盖率)
2. ✅ CI/CD Pipeline (基础)
3. ✅ 业务指标埋点
4. ✅ 告警规则配置
5. ✅ Debezium CDC
6. ✅ Flink Job (1-2 个)

### Week 4: P2 任务 (前端与部署)
1. ✅ Web 前端对话界面
2. ✅ 文档管理页面
3. ✅ Helm Charts 完善
4. ✅ E2E 测试 (基础)
5. ✅ Runbook 文档
6. ✅ 部署到开发环境

---

## 📊 完成度追踪

### 按模块

| 模块 | 完成度 | 待办项 | 预计工时 |
|-----|--------|--------|---------|
| 基础设施 | 60% | 8 | 2 周 |
| Go 微服务 | 30% | 40 | 4 周 |
| Python 微服务 | 20% | 50 | 6 周 |
| 事件驱动 | 40% | 10 | 2 周 |
| Flink 流处理 | 15% | 8 | 2 周 |
| 前端 | 10% | 15 | 3 周 |
| 安全认证 | 25% | 12 | 2 周 |
| 可观测性 | 50% | 15 | 2 周 |
| CI/CD | 0% | 8 | 1 周 |
| 测试 | 5% | 12 | 3 周 |
| 部署 | 30% | 20 | 3 周 |
| 文档 | 70% | 8 | 1 周 |
| 数据库 | 40% | 8 | 1 周 |
| Proto/gRPC | 50% | 8 | 1 周 |

**总计**: ~200 个待办项, ~33 周工时 (按 1 人计)

### 按优先级

| 优先级 | 待办项数 | 预计工时 |
|--------|---------|---------|
| 🔥 P0 | 50 | 8 周 |
| ⭐ P1 | 90 | 15 周 |
| 💡 P2 | 60 | 10 周 |

---

## 🎉 结语

本清单对标源项目 https://github.com/haoyunlt/voicehelper，详细列出了所有需要完善的功能点。

**建议**:
1. 优先完成 P0 任务，让系统能跑起来
2. 边开发边写测试，保证质量
3. 参考源项目的具体实现
4. 保持文档同步更新

**进度追踪**: 请在完成时勾选 ✅，并更新完成度百分比。

---

**更新时间**: 2025-10-26  
**维护者**: VoiceHelper Team

