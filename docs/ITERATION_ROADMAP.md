# VoiceHelper 后续迭代计划

> **制定日期**: 2025-10-26
> **当前版本**: v2.0.0 (开发中)
> **总体完成度**: 30%
> **预计完成时间**: 8-10 周 (4 人团队)

---

## 📊 当前状态总览

### ✅ 已完成 (Week 1-2)

**完成度**: 100% 🎉

| 模块                     | 状态        | 完成内容                                 |
| ------------------------ | ----------- | ---------------------------------------- |
| **Gateway (APISIX)**     | ✅ 基础完成 | 基础配置、docker-compose 集成            |
| **Identity Service**     | ✅ 80%      | Kratos 框架、JWT 认证、RBAC、多租户      |
| **Conversation Service** | ✅ 75%      | 会话管理、消息管理、Kafka 事件           |
| **Indexing Service**     | ✅ 完整实现 | 7 种解析器、BGE-M3 向量化、Milvus、Neo4j |
| **Retrieval Service**    | ✅ 完整实现 | 向量检索、BM25、RRF 混合、重排序、缓存   |

**代码统计**:

- 新增代码: ~11,600 行
- 新增文件: 42 个
- 效率提升: 92% (2.2 天完成 27.5 天工作)

---

## 🎯 后续迭代计划

### 迭代一: P0 阻塞项清理 (Week 3-4, 10 工作日)

**目标**: 打通端到端核心流程,系统可运行基本功能

#### Go 微服务团队 (2 人)

**Week 3: Knowledge Service 完整实现** (5 天)

- [ ] **T1.1 MinIO 集成** (2 天) `#存储` `#P0`

  ```
  文件: internal/infrastructure/storage/minio_client.go
  功能: Upload, Download, Delete, PresignedURL
  验收: 文件上传下载正常
  ```

- [ ] **T1.2 文档上传完整流程** (3 天) `#核心` `#P0`
  ```
  流程: 验证 → 病毒扫描 → MinIO 上传 → PostgreSQL 元数据 → Kafka 事件
  验收: 端到端流程测试通过
  负责人: Backend Engineer 1
  ```

**Week 4: AI Orchestrator 核心实现** (5 天)

- [ ] **T1.3 任务路由器** (2 天) `#编排` `#P0`

  ```
  文件: internal/application/task_router.go
  功能: 根据任务类型路由到 Agent/RAG/Voice Engine
  验收: 路由逻辑正确
  负责人: Backend Engineer 2
  ```

- [ ] **T1.4 流程编排器** (2 天) `#编排` `#P0`

  ```
  文件: internal/application/orchestration_service.go
  支持: 串行、并行、条件分支
  验收: 工作流执行正常
  ```

- [ ] **T1.5 gRPC 服务实现** (1 天) `#服务` `#P0`
  ```
  API: ExecuteTask, ExecuteWorkflow
  验收: gRPC 接口正常调用
  ```

**交付物**:

- ✅ Knowledge Service 完全可用
- ✅ AI Orchestrator 基础编排能力
- ✅ 文档上传 → 索引 → 检索完整链路

---

#### Python 微服务团队 (2 人)

**Week 3: RAG Engine 完整实现** (5 天)

- [ ] **T2.1 查询改写** (1 天) `#RAG` `#P0`

  ```
  文件: algo/rag-engine/app/core/query_rewriter.py
  方法: HyDE, Multi-Query, Step-back
  负责人: AI Engineer 1
  ```

- [ ] **T2.2 上下文构建** (1 天) `#RAG` `#P0`

  ```
  文件: algo/rag-engine/app/core/context_builder.py
  功能: 组装检索结果、截断、添加来源
  ```

- [ ] **T2.3 答案生成** (2 天) `#RAG` `#P0`

  ```
  文件: algo/rag-engine/app/core/answer_generator.py
  模式: 非流式 + 流式
  调用: Model Router gRPC
  ```

- [ ] **T2.4 引用来源** (1 天) `#RAG` `#P0`
  ```
  文件: algo/rag-engine/app/core/citation_generator.py
  格式: [1] 文档名 (页码/位置)
  ```

**Week 4: Agent Engine 核心实现** (5 天)

- [ ] **T2.5 LangGraph 工作流** (3 天) `#Agent` `#P0`

  ```
  文件: algo/agent-engine/app/core/agent/workflow.py
  节点: Planner → Executor → Reflector
  模式: ReAct
  负责人: AI Engineer 2
  ```

- [ ] **T2.6 工具注册表** (1 天) `#Agent` `#P0`

  ```
  文件: algo/agent-engine/app/core/tools/registry.py
  内置工具: Search, Calculator, CodeInterpreter, WebScraper
  ```

- [ ] **T2.7 工具调用系统** (1 天) `#Agent` `#P0`
  ```
  文件: algo/agent-engine/app/core/tools/executor.py
  安全: 白名单、参数验证、超时控制
  ```

**交付物**:

- ✅ RAG Engine 完全可用
- ✅ Agent Engine 基础 ReAct 能力
- ✅ 问答和智能任务执行功能

---

### 迭代二: P0 模型路由与基础设施 (Week 5-6, 10 工作日)

**目标**: 完成模型调用链路,完善网关配置

#### Go 微服务团队

**Week 5: Model Router 实现** (5 天)

- [ ] **T3.1 路由决策引擎** (2 天) `#路由` `#P0`

  ```
  文件: cmd/model-router/internal/application/routing_service.go
  策略: 成本优先、延迟优先、可用性优先
  配置: models.yaml
  负责人: Backend Engineer 1
  ```

- [ ] **T3.2 成本优化器** (1 天) `#成本` `#P0`

  ```
  功能: Token 计费、模型选择、成本预警
  ```

- [ ] **T3.3 降级管理器** (1 天) `#容错` `#P0`

  ```
  降级链: GPT-4 → GPT-3.5 → Qianwen → 本地模型
  ```

- [ ] **T3.4 gRPC 服务** (1 天) `#服务` `#P0`

**Week 6: Gateway 完善** (5 天)

- [ ] **T3.5 完整路由配置** (2 天) `#网关` `#P0`

  ```
  文件: configs/gateway/apisix-routes.yaml
  配置: 14 个服务的完整路由
  负责人: Backend Engineer 2
  ```

- [ ] **T3.6 JWT 认证插件** (1 天) `#安全` `#P0`

  ```
  集成: Vault 密钥管理
  验证: user_id, tenant_id claims
  ```

- [ ] **T3.7 限流插件** (1 天) `#性能` `#P0`

  ```
  策略: 用户级、IP 级、租户级
  存储: Redis
  ```

- [ ] **T3.8 监控配置** (1 天) `#监控` `#P0`
  ```
  插件: prometheus, opentelemetry
  ```

**交付物**:

- ✅ Model Router 完全可用
- ✅ API Gateway 生产就绪
- ✅ 统一认证和限流

---

#### Python 微服务团队

**Week 5: Model Adapter 实现** (5 天)

- [ ] **T4.1 OpenAI 适配器** (1 天) `#适配器` `#P0`

  ```
  文件: algo/model-adapter/app/adapters/openai_adapter.py
  模型: GPT-4, GPT-3.5
  负责人: AI Engineer 1
  ```

- [ ] **T4.2 Claude 适配器** (1 天) `#适配器` `#P0`

  ```
  模型: Claude 3 Opus/Sonnet
  ```

- [ ] **T4.3 Zhipu 适配器** (1 天) `#适配器` `#P0`

  ```
  模型: GLM-4
  ```

- [ ] **T4.4 协议转换器** (1 天) `#转换` `#P0`

  ```
  功能: 统一消息格式 ↔ 各厂商格式
  ```

- [ ] **T4.5 gRPC 服务** (1 天) `#服务` `#P0`

**Week 6: Voice Engine 核心实现** (5 天)

- [ ] **T4.6 Whisper ASR** (2 天) `#ASR` `#P1`

  ```
  文件: algo/voice-engine/app/core/asr/whisper_asr.py
  模式: 文件转写 + 流式转写
  负责人: AI Engineer 2
  ```

- [ ] **T4.7 Silero VAD** (1 天) `#VAD` `#P1`

  ```
  功能: 语音活动检测
  ```

- [ ] **T4.8 Edge TTS** (2 天) `#TTS` `#P1`
  ```
  语音: zh-CN-XiaoxiaoNeural
  模式: 文件 + 流式
  ```

**交付物**:

- ✅ Model Adapter 支持主流 LLM
- ✅ Voice Engine 基础语音能力
- ✅ 完整的 LLM 调用链路

---

### 迭代三: P1 重要功能 (Week 7-8, 10 工作日)

**目标**: 完善核心服务功能,提升系统可用性

#### Go 微服务团队

**Week 7: Identity & Conversation 完善** (5 天)

- [ ] **T5.1 Redis 缓存完善** (1 天) `#Identity` `#P1`

  ```
  缓存: 用户信息、Token、权限
  TTL: 1h / 24h / 10min
  负责人: Backend Engineer 1
  ```

- [ ] **T5.2 Consul 服务注册** (1 天) `#Identity` `#P1`

  ```
  功能: 自动注册、健康检查
  ```

- [ ] **T5.3 OAuth 2.0 集成** (3 天) `#Identity` `#P1`
  ```
  支持: Google, GitHub, Microsoft
  流程: Authorization Code Flow
  ```

**Week 7: Conversation 流式响应** (同步进行)

- [ ] **T5.4 SSE 流式响应** (2 天) `#Conversation` `#P1`

  ```
  路由: /api/v1/conversation/{id}/stream
  负责人: Backend Engineer 2
  ```

- [ ] **T5.5 WebSocket 支持** (2 天) `#Conversation` `#P1`

  ```
  功能: 双向通信、连接池管理
  ```

- [ ] **T5.6 会话分享** (1 天) `#Conversation` `#P1`

**Week 8: Notification Service** (5 天)

- [ ] **T5.7 邮件/短信/Push** (3 天) `#Notification` `#P1`

  ```
  渠道: Email, SMS, FCM, APNs
  负责人: Backend Engineer 1
  ```

- [ ] **T5.8 Kafka 消费者** (1 天) `#Notification` `#P1`

  ```
  订阅: conversation.events, document.events
  ```

- [ ] **T5.9 模板引擎** (1 天) `#Notification` `#P1`

**交付物**:

- ✅ Identity Service 完全可用
- ✅ Conversation Service 完全可用
- ✅ Notification Service 完全可用

---

#### Python 微服务团队

**Week 7: Agent Engine 完善** (5 天)

- [ ] **T6.1 MCP 集成** (2 天) `#Agent` `#P1`

  ```
  协议: Model Context Protocol
  负责人: AI Engineer 1
  ```

- [ ] **T6.2 长期记忆** (1 天) `#Agent` `#P1`

  ```
  存储: FAISS Index
  ```

- [ ] **T6.3 记忆衰减** (1 天) `#Agent` `#P1`

  ```
  策略: 时间衰减 (factor=0.9)
  ```

- [ ] **T6.4 对话历史** (1 天) `#Agent` `#P1`
  ```
  功能: Add, Get, Summarize
  ```

**Week 8: Multimodal Engine** (5 天)

- [ ] **T6.5 Paddle OCR** (2 天) `#Multimodal` `#P1`

  ```
  文件: algo/multimodal-engine/app/core/ocr/paddle_ocr.py
  功能: 文本识别、表格识别
  负责人: AI Engineer 2
  ```

- [ ] **T6.6 GPT-4V 集成** (2 天) `#Multimodal` `#P1`

  ```
  功能: 图像分析、实体提取
  ```

- [ ] **T6.7 视频处理** (1 天) `#Multimodal` `#P1`
  ```
  功能: 帧提取、视频分析
  ```

**交付物**:

- ✅ Agent Engine 完全可用
- ✅ Multimodal Engine 完全可用
- ✅ 多模态能力支持

---

### 迭代四: P1 数据分析与测试 (Week 9-10, 10 工作日)

**目标**: 数据分析能力,测试覆盖率 >70%

#### 全团队

**Week 9: Analytics Service + 单元测试** (5 天)

- [ ] **T7.1 ClickHouse 客户端** (1 天) `#Analytics` `#P1`

  ```
  负责人: Backend Engineer 1
  ```

- [ ] **T7.2 实时指标查询** (2 天) `#Analytics` `#P1`

  ```
  指标: 今日用量、7 天趋势、Top 10 租户
  ```

- [ ] **T7.3 Go 服务单元测试** (2 天) `#测试` `#P1`

  ```
  覆盖率: 70%+
  负责人: Backend Engineer 2
  工具: testify, gomock
  ```

- [ ] **T7.4 Python 服务单元测试** (2 天) `#测试` `#P1`
  ```
  覆盖率: 70%+
  负责人: AI Engineer 1, 2
  工具: pytest
  ```

**Week 10: 集成测试与压力测试** (5 天)

- [ ] **T7.5 集成测试** (2 天) `#测试` `#P1`

  ```
  工具: dockertest
  场景: 完整业务流程
  负责人: 全团队
  ```

- [ ] **T7.6 E2E 测试** (2 天) `#测试` `#P2`

  ```
  工具: Playwright
  场景: 用户登录 → 对话 → 上传文档
  ```

- [ ] **T7.7 k6 压力测试** (1 天) `#测试` `#P2`
  ```
  目标: 1000 并发, P95 < 500ms
  ```

**交付物**:

- ✅ Analytics Service 完全可用
- ✅ 单元测试覆盖率 >70%
- ✅ 集成测试和 E2E 测试
- ✅ 性能基准测试

---

## 📋 详细任务依赖关系

### 关键路径 (Critical Path)

```
Knowledge Service (Week 3)
    ↓
Indexing Service (已完成) → Retrieval Service (已完成)
    ↓
RAG Engine (Week 3)
    ↓
AI Orchestrator (Week 4)
    ↓
Model Router (Week 5) → Model Adapter (Week 5)
    ↓
端到端测试 (Week 10)
```

### 并行任务

**可同时进行**:

- Identity Service 完善 ∥ Conversation Service 完善
- Agent Engine ∥ Voice Engine
- Notification Service ∥ Analytics Service

---

## 🎯 里程碑与验收标准

### Milestone 1: 核心流程打通 (Week 4 结束)

**验收标准**:

- [ ] 用户可以上传文档
- [ ] 文档自动索引到向量数据库
- [ ] 用户可以提问并得到 RAG 答案
- [ ] Agent 可以执行基础工具调用
- [ ] AI Orchestrator 可以编排任务

**Demo 场景**:

```
1. 用户注册登录
2. 上传 PDF 文档
3. 等待索引完成 (5-10秒)
4. 提问: "文档的主要内容是什么?"
5. 系统返回 RAG 答案 + 引用来源
6. 发起 Agent 任务: "搜索相关资料"
7. Agent 调用 Search 工具并返回结果
```

---

### Milestone 2: LLM 调用链路 (Week 6 结束)

**验收标准**:

- [ ] Model Router 可以根据策略选择模型
- [ ] Model Adapter 支持 3+ LLM 提供商
- [ ] 成本追踪正常工作
- [ ] 降级策略正常触发
- [ ] API Gateway 认证和限流正常

**压测指标**:

- 并发 500 用户
- P95 延迟 < 300ms
- 错误率 < 0.1%

---

### Milestone 3: 完整功能 (Week 8 结束)

**验收标准**:

- [ ] 所有 P0 + P1 功能完成
- [ ] 单元测试覆盖率 >70%
- [ ] 核心服务稳定运行 48h+
- [ ] 监控和告警正常工作

**功能清单**:

- ✅ 用户注册/登录 (OAuth)
- ✅ 文档管理 (上传/下载/删除/版本)
- ✅ RAG 问答 (流式响应)
- ✅ Agent 任务 (工具调用)
- ✅ 语音对话 (ASR + TTS)
- ✅ 多模态 (OCR + 图像理解)
- ✅ 通知推送 (邮件/短信/Push)
- ✅ 数据分析 (实时统计)

---

### Milestone 4: 生产就绪 (Week 10 结束)

**验收标准**:

- [ ] 压力测试通过 (1000 并发)
- [ ] 集成测试和 E2E 测试通过
- [ ] 安全测试通过 (无高危漏洞)
- [ ] 文档完整 (API + Runbook)
- [ ] CI/CD 流水线正常

**SLA 目标**:

- 可用性 ≥ 99.9%
- P95 延迟 < 500ms
- P99 延迟 < 2s
- 错误率 < 0.5%

---

## 💰 资源与成本估算

### 人力成本

| 角色                   | 人数 | 周数 | 人周 | 成本 (估算) |
| ---------------------- | ---- | ---- | ---- | ----------- |
| **后端工程师 (Go)**    | 2    | 10   | 20   | $40,000     |
| **AI 工程师 (Python)** | 2    | 10   | 20   | $40,000     |
| **SRE 工程师** (兼职)  | 0.5  | 10   | 5    | $10,000     |
| **测试工程师** (兼职)  | 0.5  | 4    | 2    | $4,000      |
| **总计**               | 5    | -    | 47   | **$94,000** |

### 基础设施成本 (开发环境)

| 资源                        | 月费用 | 10 周成本  |
| --------------------------- | ------ | ---------- |
| Kubernetes 集群 (6 节点)    | $1,200 | $3,000     |
| PostgreSQL RDS              | $300   | $750       |
| Redis Sentinel              | $150   | $375       |
| Milvus 集群                 | $200   | $500       |
| Kafka 集群                  | $250   | $625       |
| MinIO 存储                  | $100   | $250       |
| 监控 (Prometheus + Grafana) | $100   | $250       |
| **总计**                    | $2,300 | **$5,750** |

### 总成本

- 人力: $94,000
- 基础设施: $5,750
- **总计: $99,750** (约 $100k)

---

## 🚨 风险管理

### 高风险项

| 风险                       | 概率 | 影响 | 缓解措施                  |
| -------------------------- | ---- | ---- | ------------------------- |
| **LangGraph Agent 复杂度** | 中   | 高   | 参考源项目实现,分步骤开发 |
| **Kafka 事件驱动架构**     | 中   | 高   | 充分测试,保留同步调用备份 |
| **向量数据库性能**         | 低   | 中   | 压力测试,优化索引配置     |
| **LLM API 限流**           | 高   | 中   | 降级策略,自建模型备用     |
| **团队学习曲线**           | 中   | 中   | 提前培训,文档完善         |

### 应对策略

1. **技术风险**:

   - 提前 POC (Proof of Concept)
   - 分步骤实现
   - 充分测试

2. **进度风险**:

   - 每周同步进度
   - 及时调整优先级
   - 必要时缩减 P2 功能

3. **质量风险**:
   - Code Review
   - 单元测试强制要求
   - 集成测试覆盖核心流程

---

## 📝 执行建议

### 团队协作

**每日站会** (15 分钟):

- 昨天完成了什么
- 今天计划做什么
- 有什么阻碍

**每周回顾** (1 小时):

- 本周完成情况
- 遇到的问题
- 下周计划

**双周演示** (1 小时):

- 向 Stakeholder 演示进展
- 收集反馈
- 调整优先级

### 技术规范

**代码规范**:

- Go: `golangci-lint`
- Python: `ruff`
- TypeScript: `eslint` + `prettier`

**Git 规范**:

- Commit 格式: `<type>(<scope>): <subject>`
- 分支策略: feature/xxx, bugfix/xxx
- PR 模板必填

**文档规范**:

- 每个服务有 Runbook
- API 文档自动生成
- 架构决策记录 (ADR)

### 质量保证

**测试金字塔**:

```
        /\
       /E2E\        10%
      /------\
     /Integ  \      20%
    /----------\
   /   Unit     \   70%
  /--------------\
```

**CI/CD**:

- PR 触发: Lint + Unit Test
- Merge 到 main: Build + Integration Test
- Tag 发布: Deploy to Dev

---

## 📚 参考资源

### 内部文档

- [架构设计 v2.0](docs/arch/microservice-architecture-v2.md)
- [Week 1-2 完成报告](WEEK1_2_COMPLETION_REPORT.md)
- [功能清单](FEATURE_CHECKLIST.md)
- [服务 TODO](SERVICE_TODO_TRACKER.md)
- [服务完成度审查](SERVICE_COMPLETION_REVIEW.md)

### 源项目参考

- https://github.com/haoyunlt/voicehelper
- 源项目版本: v0.9.2

### 技术文档

- [Kratos 框架文档](https://go-kratos.dev/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [APISIX 文档](https://apisix.apache.org/docs/)
- [Milvus 文档](https://milvus.io/docs/)

---

## 🎉 成功标准

### 技术指标

- ✅ 所有 P0 功能完成 (100%)
- ✅ 所有 P1 功能完成 (100%)
- ✅ 单元测试覆盖率 >70%
- ✅ 系统可用性 ≥99.9%
- ✅ P95 延迟 <500ms
- ✅ 并发能力 ≥1000 RPS

### 业务指标

- ✅ 核心用户场景可完整演示
- ✅ 产品经理验收通过
- ✅ 可支撑 10k+ 日活用户

### 团队指标

- ✅ 团队成员熟悉新架构
- ✅ 文档完整可维护
- ✅ On-call 流程建立

---

**制定人**: AI Coding Assistant
**审核**: 待定
**下次更新**: 每周五

---

## 快速行动清单

### 本周 (Week 3) 启动项

**Go 团队**:

1. [ ] Knowledge Service MinIO 集成
2. [ ] 文档上传完整流程
3. [ ] ClamAV 病毒扫描集成

**Python 团队**:

1. [ ] RAG Engine 查询改写
2. [ ] RAG Engine 答案生成 (流式)
3. [ ] RAG Engine 引用来源

**全团队**:

1. [ ] 每日站会 (10:00 AM)
2. [ ] 周五演示 (5:00 PM)

### 下周 (Week 4) 预热

**Go 团队**:

1. [ ] 熟悉 AI Orchestrator 架构
2. [ ] 学习 gRPC 客户端开发

**Python 团队**:

1. [ ] 学习 LangGraph 框架
2. [ ] 准备工具注册表设计

---

**让我们开始吧! 🚀**
