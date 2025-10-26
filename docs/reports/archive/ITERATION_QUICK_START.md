# VoiceHelper 迭代快速启动指南

> **快速参考**: 10 周开发计划核心要点
> **详细版本**: 见 [ITERATION_ROADMAP.md](ITERATION_ROADMAP.md)

---

## 🎯 核心目标

**8-10 周内完成**: P0 (100%) + P1 (100%) + P2 (30%)

当前完成度: **30%** → 目标: **85%+**

---

## 📅 10 周时间线

```
Week 1-2: ✅ 已完成 (基础架构 + 索引检索)
Week 3-4: 🔥 P0 阻塞项 (RAG + Agent + Orchestrator)
Week 5-6: 🔥 P0 模型路由 (Router + Adapter + Gateway)
Week 7-8: ⭐ P1 重要功能 (完善核心服务)
Week 9-10: ⭐ P1 测试与分析 (Analytics + 测试覆盖)
```

---

## 👥 团队配置 (4 人)

- **Backend Engineer × 2** (Go 微服务)
- **AI Engineer × 2** (Python 算法服务)

---

## 🚀 Week 3-4: P0 阻塞项

### Go 团队

**Week 3**: Knowledge Service

- MinIO 集成 + 文档上传流程 + 病毒扫描
- **交付**: 文档可上传并触发索引

**Week 4**: AI Orchestrator

- 任务路由 + 流程编排 + gRPC 服务
- **交付**: 任务可编排并路由到各引擎

### Python 团队

**Week 3**: RAG Engine

- 查询改写 + 上下文构建 + 答案生成 + 引用
- **交付**: 问答功能可用

**Week 4**: Agent Engine

- LangGraph 工作流 + 工具注册表 + 工具调用
- **交付**: Agent 可执行基础任务

### Milestone 1: 核心流程打通 ✅

```
用户上传文档 → 自动索引 → 提问 → RAG 答案
发起 Agent 任务 → 工具调用 → 返回结果
```

---

## 🎯 Week 5-6: P0 模型路由

### Go 团队

**Week 5**: Model Router

- 路由决策 + 成本优化 + 降级管理
- **交付**: 模型可智能路由

**Week 6**: Gateway 完善

- 完整路由配置 + JWT + 限流 + 监控
- **交付**: Gateway 生产就绪

### Python 团队

**Week 5**: Model Adapter

- OpenAI + Claude + Zhipu 适配器 + 协议转换
- **交付**: 支持 3+ LLM 提供商

**Week 6**: Voice Engine

- Whisper ASR + Silero VAD + Edge TTS
- **交付**: 基础语音能力

### Milestone 2: LLM 链路打通 ✅

```
压测: 500 并发, P95 < 300ms, 错误率 < 0.1%
功能: 智能模型选择 + 成本追踪 + 降级策略
```

---

## ⭐ Week 7-8: P1 重要功能

### Go 团队

**Week 7**: Identity + Conversation 完善

- Redis 缓存 + OAuth 2.0 + SSE/WebSocket
- **交付**: 核心服务完全可用

**Week 8**: Notification Service

- 邮件/短信/Push + Kafka 消费 + 模板引擎
- **交付**: 通知系统完全可用

### Python 团队

**Week 7**: Agent Engine 完善

- MCP 集成 + 长期记忆 + 记忆衰减
- **交付**: Agent 功能完整

**Week 8**: Multimodal Engine

- Paddle OCR + GPT-4V + 视频处理
- **交付**: 多模态能力

### Milestone 3: 功能完整 ✅

```
所有核心功能可用:
✅ 认证授权 ✅ 文档管理 ✅ RAG 问答
✅ Agent 任务 ✅ 语音对话 ✅ 多模态
✅ 通知推送
```

---

## 📊 Week 9-10: 测试与分析

### 全团队协作

**Week 9**: Analytics + 单元测试

- ClickHouse 客户端 + 实时统计
- Go/Python 单元测试 (覆盖率 >70%)
- **交付**: 数据分析 + 测试覆盖

**Week 10**: 集成测试 + 压测

- 集成测试 + E2E 测试 + k6 压测
- **交付**: 测试完整 + 性能达标

### Milestone 4: 生产就绪 ✅

```
压测: 1000 并发通过
测试: 单元 + 集成 + E2E 完整
SLA: 可用性 99.9%, P95 < 500ms
```

---

## 📋 关键任务清单

### Week 3 (本周) - 立即启动

**Go 团队 (Backend Engineer 1 & 2)**:

```
□ T1.1 MinIO 集成 (2天)
□ T1.2 文档上传流程 (3天)
□ T1.3 ClamAV 病毒扫描 (1天)
```

**Python 团队 (AI Engineer 1 & 2)**:

```
□ T2.1 RAG 查询改写 (1天)
□ T2.2 RAG 上下文构建 (1天)
□ T2.3 RAG 答案生成 (2天)
□ T2.4 RAG 引用来源 (1天)
```

**每日站会**: 10:00 AM
**周五演示**: 5:00 PM

---

## 💰 资源预算

| 项目             | 成本       |
| ---------------- | ---------- |
| 人力 (47 人周)   | $94,000    |
| 基础设施 (10 周) | $5,750     |
| **总计**         | **~$100k** |

---

## ⚠️ 风险提示

| 风险                 | 缓解措施               |
| -------------------- | ---------------------- |
| **LangGraph 复杂度** | 参考源项目，分步开发   |
| **Kafka 事件驱动**   | 充分测试，保留同步备份 |
| **LLM API 限流**     | 降级策略，自建模型备用 |

---

## 📈 成功指标

### 技术指标

- ✅ P0 功能完成 100%
- ✅ P1 功能完成 100%
- ✅ 单元测试覆盖率 >70%
- ✅ P95 延迟 <500ms
- ✅ 并发能力 ≥1000 RPS

### 业务指标

- ✅ 核心场景可演示
- ✅ 可支撑 10k+ DAU

---

## 🔗 相关文档

- **详细计划**: [ITERATION_ROADMAP.md](ITERATION_ROADMAP.md)
- **完成报告**: [WEEK1_2_COMPLETION_REPORT.md](WEEK1_2_COMPLETION_REPORT.md)
- **功能清单**: [FEATURE_CHECKLIST.md](FEATURE_CHECKLIST.md)
- **架构文档**: [docs/arch/microservice-architecture-v2.md](docs/arch/microservice-architecture-v2.md)

---

## 🎬 立即行动

### 今天 (Day 1)

**Backend Engineers**:

1. 熟悉 MinIO Go SDK
2. 设计文档上传 API
3. 配置 docker-compose 中的 ClamAV

**AI Engineers**:

1. 熟悉 RAG Engine 代码结构
2. 研究 HyDE 查询改写方法
3. 准备 BGE-M3 Embedder 测试

### 本周目标

**团队目标**: 打通文档上传 → RAG 问答完整链路

**具体指标**:

- 文档上传成功率 100%
- 索引速度 <10s/文档
- RAG 问答延迟 <3s

---

**下一步**: 开始 Week 3 任务！🚀
