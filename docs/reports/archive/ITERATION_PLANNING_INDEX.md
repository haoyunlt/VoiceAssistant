# VoiceHelper 迭代规划文档索引

> **文档集合**: 后续 10 周迭代计划完整指南
> **创建日期**: 2025-10-26
> **当前阶段**: Week 3 准备开始

---

## 📚 文档导航

### 🎯 核心规划文档

| 文档                                                           | 用途                 | 适用对象  | 详细程度   |
| -------------------------------------------------------------- | -------------------- | --------- | ---------- |
| [**ITERATION_ROADMAP.md**](ITERATION_ROADMAP.md)               | 完整的 10 周迭代计划 | 全员      | ⭐⭐⭐⭐⭐ |
| [**ITERATION_QUICK_START.md**](ITERATION_QUICK_START.md)       | 快速启动指南         | 新成员    | ⭐⭐⭐     |
| [**WEEKLY_PLAN_TRACKER.md**](WEEKLY_PLAN_TRACKER.md)           | 周计划跟踪表         | Tech Lead | ⭐⭐⭐⭐   |
| [**TEAM_COLLABORATION_GUIDE.md**](TEAM_COLLABORATION_GUIDE.md) | 团队协作规范         | 全员      | ⭐⭐⭐⭐   |

### 📊 进度与总结文档

| 文档                                                             | 用途              | 更新频率 |
| ---------------------------------------------------------------- | ----------------- | -------- |
| [**WEEK1_2_COMPLETION_REPORT.md**](WEEK1_2_COMPLETION_REPORT.md) | Week 1-2 完成报告 | 已完成   |
| [**FEATURE_CHECKLIST.md**](FEATURE_CHECKLIST.md)                 | 功能完成清单      | 每周更新 |
| [**SERVICE_TODO_TRACKER.md**](SERVICE_TODO_TRACKER.md)           | 服务任务跟踪      | 每周更新 |
| [**SERVICE_COMPLETION_REVIEW.md**](SERVICE_COMPLETION_REVIEW.md) | 服务完成度审查    | 双周更新 |

### 🏗️ 架构与技术文档

| 文档                                                                                       | 用途                |
| ------------------------------------------------------------------------------------------ | ------------------- |
| [**docs/arch/microservice-architecture-v2.md**](docs/arch/microservice-architecture-v2.md) | 微服务架构设计 v2.0 |
| [**docs/migration-checklist.md**](docs/migration-checklist.md)                             | 架构迁移清单        |
| [**README.md**](README.md)                                                                 | 项目总览            |
| [**QUICKSTART.md**](QUICKSTART.md)                                                         | 快速开始指南        |

---

## 🚀 如何使用这些文档

### 对于新加入的团队成员

**第 1 天**:

1. 阅读 [README.md](README.md) - 了解项目概况
2. 阅读 [ITERATION_QUICK_START.md](ITERATION_QUICK_START.md) - 了解当前迭代计划
3. 阅读 [TEAM_COLLABORATION_GUIDE.md](TEAM_COLLABORATION_GUIDE.md) - 了解团队协作规范

**第 1 周**:

1. 详细阅读 [ITERATION_ROADMAP.md](ITERATION_ROADMAP.md) - 了解完整计划
2. 查看 [WEEKLY_PLAN_TRACKER.md](WEEKLY_PLAN_TRACKER.md) - 了解本周任务
3. 参考 [FEATURE_CHECKLIST.md](FEATURE_CHECKLIST.md) - 了解待完成功能

### 对于 Tech Lead / Project Manager

**每周一上午**:

1. 更新 [WEEKLY_PLAN_TRACKER.md](WEEKLY_PLAN_TRACKER.md) - 规划本周任务
2. 查看 [SERVICE_TODO_TRACKER.md](SERVICE_TODO_TRACKER.md) - 检查服务进度
3. 与团队同步本周目标

**每周五下午**:

1. 更新 [WEEKLY_PLAN_TRACKER.md](WEEKLY_PLAN_TRACKER.md) - 记录本周完成情况
2. 更新 [FEATURE_CHECKLIST.md](FEATURE_CHECKLIST.md) - 勾选完成功能
3. 准备下周计划

**双周回顾**:

1. 更新 [SERVICE_COMPLETION_REVIEW.md](SERVICE_COMPLETION_REVIEW.md) - 服务完成度审查
2. 评估 [ITERATION_ROADMAP.md](ITERATION_ROADMAP.md) - 调整迭代计划 (如需要)

### 对于开发工程师

**每天早上**:

1. 查看 [WEEKLY_PLAN_TRACKER.md](WEEKLY_PLAN_TRACKER.md) - 了解今日任务
2. 参加每日站会 (参考 [TEAM_COLLABORATION_GUIDE.md](TEAM_COLLABORATION_GUIDE.md))

**编码前**:

1. 查看 [SERVICE_TODO_TRACKER.md](SERVICE_TODO_TRACKER.md) - 了解任务详情
2. 参考 [FEATURE_CHECKLIST.md](FEATURE_CHECKLIST.md) - 了解功能需求
3. 参考 [docs/arch/](docs/arch/) - 了解架构设计

**提交代码时**:

1. 遵循 [TEAM_COLLABORATION_GUIDE.md](TEAM_COLLABORATION_GUIDE.md) - Commit 和 PR 规范
2. 更新相关文档

---

## 📊 当前状态一览

### 总体进度

```
┌─────────────────────────────────────────────────────────┐
│  Week 1-2: ████████████████████████ 100% (已完成)       │
│  Week 3-4: ░░░░░░░░░░░░░░░░░░░░░░░░   0% (本周开始)    │
│  Week 5-6: ░░░░░░░░░░░░░░░░░░░░░░░░   0% (未开始)      │
│  Week 7-8: ░░░░░░░░░░░░░░░░░░░░░░░░   0% (未开始)      │
│ Week 9-10: ░░░░░░░░░░░░░░░░░░░░░░░░   0% (未开始)      │
├─────────────────────────────────────────────────────────┤
│  总体进度: ████░░░░░░░░░░░░░░░░░░░░  20%               │
└─────────────────────────────────────────────────────────┘
```

### Week 1-2 完成成果

✅ **Gateway (APISIX)**: 基础配置完成 (40%)
✅ **Identity Service**: Kratos 框架集成完成 (80%)
✅ **Conversation Service**: 会话管理基础完成 (75%)
✅ **Indexing Service**: 完整实现 (100%) 🎉
✅ **Retrieval Service**: 完整实现 (100%) 🎉

**代码统计**:

- 新增代码: ~11,600 行
- 新增文件: 42 个
- 效率提升: 92%

### Week 3 当前任务

**Go 团队**:

- 🚧 Knowledge Service MinIO 集成
- 🚧 文档上传完整流程
- 🚧 ClamAV 病毒扫描

**Python 团队**:

- 🚧 RAG Engine 查询改写
- 🚧 RAG Engine 答案生成
- 🚧 RAG Engine 引用来源

---

## 🎯 关键里程碑

### Milestone 1: 核心流程打通 (Week 4 结束)

**目标**: 文档上传 → 索引 → RAG 问答完整链路

**验收标准**:

- [ ] 用户可以上传文档
- [ ] 文档自动索引到向量数据库
- [ ] 用户可以提问并得到 RAG 答案
- [ ] Agent 可以执行基础工具调用

### Milestone 2: LLM 链路打通 (Week 6 结束)

**目标**: 模型路由与调用完整链路

**验收标准**:

- [ ] Model Router 可以智能路由
- [ ] 支持 3+ LLM 提供商
- [ ] 成本追踪正常工作
- [ ] Gateway 认证限流正常

### Milestone 3: 功能完整 (Week 8 结束)

**目标**: 所有核心功能完全可用

**验收标准**:

- [ ] 所有 P0 + P1 功能完成
- [ ] 单元测试覆盖率 >70%
- [ ] 核心服务稳定运行 48h+

### Milestone 4: 生产就绪 (Week 10 结束)

**目标**: 系统可上线生产环境

**验收标准**:

- [ ] 压力测试通过 (1000 并发)
- [ ] 集成测试和 E2E 测试通过
- [ ] 安全测试通过
- [ ] 文档完整

---

## 💰 资源预算

| 项目         | 预算       | 说明                 |
| ------------ | ---------- | -------------------- |
| **人力成本** | $94,000    | 4 人核心团队 × 10 周 |
| **基础设施** | $5,750     | 开发环境 10 周       |
| **总计**     | **~$100k** | -                    |

---

## ⚠️ 风险与应对

| 风险                   | 概率 | 影响 | 缓解措施               |
| ---------------------- | ---- | ---- | ---------------------- |
| LangGraph Agent 复杂度 | 中   | 高   | 参考源项目，分步开发   |
| Kafka 事件驱动架构     | 中   | 高   | 充分测试，保留同步备份 |
| LLM API 限流           | 高   | 中   | 降级策略，自建模型备用 |
| 团队学习曲线           | 中   | 中   | 提前培训，文档完善     |

---

## 📞 联系与支持

### 团队沟通

- **Slack**: #voicehelper-general
- **每日站会**: 10:00 AM
- **周五演示**: 17:00 PM

### 文档维护

| 文档                        | 负责人    | 更新频率 |
| --------------------------- | --------- | -------- |
| ITERATION_ROADMAP.md        | Tech Lead | 按需更新 |
| WEEKLY_PLAN_TRACKER.md      | Tech Lead | 每周五   |
| FEATURE_CHECKLIST.md        | Tech Lead | 每周五   |
| TEAM_COLLABORATION_GUIDE.md | Tech Lead | 按需更新 |

### 问题反馈

**文档问题或建议**:

1. 在 Slack #voicehelper-general 提出
2. 或创建 GitHub Issue

---

## 🎓 学习资源

### 必读资料

**微服务架构**:

- [Kratos 框架文档](https://go-kratos.dev/)
- [微服务设计模式](https://microservices.io/patterns/)

**AI 相关**:

- [LangChain 文档](https://python.langchain.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [BGE Embeddings](https://github.com/FlagOpen/FlagEmbedding)

**基础设施**:

- [APISIX 文档](https://apisix.apache.org/docs/)
- [Milvus 文档](https://milvus.io/docs/)
- [Kafka 文档](https://kafka.apache.org/documentation/)

### 源项目参考

- **GitHub**: https://github.com/haoyunlt/voicehelper
- **版本**: v0.9.2

---

## 📝 版本历史

| 版本 | 日期       | 更新内容     |
| ---- | ---------- | ------------ |
| v1.0 | 2025-10-26 | 创建初始版本 |
| -    | -          | -            |

---

## 🎉 快速开始

**如果你只有 5 分钟**:

1. 阅读 [ITERATION_QUICK_START.md](ITERATION_QUICK_START.md)
2. 查看 [WEEKLY_PLAN_TRACKER.md](WEEKLY_PLAN_TRACKER.md) 本周任务

**如果你有 30 分钟**:

1. 详细阅读 [ITERATION_ROADMAP.md](ITERATION_ROADMAP.md)
2. 浏览 [TEAM_COLLABORATION_GUIDE.md](TEAM_COLLABORATION_GUIDE.md)
3. 查看 [FEATURE_CHECKLIST.md](FEATURE_CHECKLIST.md)

**如果你有 2 小时**:

1. 阅读所有规划文档
2. 查看架构设计文档
3. 配置本地开发环境
4. 熟悉代码结构

---

**祝开发顺利! 🚀**

有任何问题，随时查阅相关文档或在 Slack 提问！
