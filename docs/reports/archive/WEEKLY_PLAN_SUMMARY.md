# 周计划速查表

> **快速参考版本** - 详细计划见 `DETAILED_WEEK_PLAN.md`

---

## 📅 12 周概览

| 周          | 日期       | 主要任务                             | 交付物                       | 状态        |
| ----------- | ---------- | ------------------------------------ | ---------------------------- | ----------- |
| **Week 1**  | 10/28-11/1 | Wire 依赖注入 + Model Router/Adapter | 所有服务可编译，模型路由可用 | 🔜 即将开始 |
| **Week 2**  | 11/4-8     | AI Orchestrator + 端到端集成         | P0 任务 100%完成             | ⏳ 待开始   |
| **Week 3**  | 11/11-15   | Flink 流处理 + Debezium CDC          | 实时数据流工作               | ⏳ 待开始   |
| **Week 4**  | 11/18-22   | Agent Engine + Notification Service  | Agent 可执行任务             | ⏳ 待开始   |
| **Week 5**  | 11/25-29   | Voice Engine 实现                    | 语音对话可用                 | ⏳ 待开始   |
| **Week 6**  | 12/2-6     | Multimodal Engine + Analytics 完善   | 多模态识别可用               | ⏳ 待开始   |
| **Week 7**  | 12/9-13    | 前端核心页面开发                     | 登录/对话页面                | ⏳ 待开始   |
| **Week 8**  | 12/16-20   | 前端功能完善                         | 知识库/分析页面              | ⏳ 待开始   |
| **Week 9**  | 12/23-27   | OpenTelemetry + Vault + Grafana      | 可观测性完整                 | ⏳ 待开始   |
| **Week 10** | 12/30-1/3  | CI/CD + 单元测试                     | 自动化就绪                   | ⏳ 待开始   |
| **Week 11** | 1/6-10     | 集成测试 + E2E 测试                  | 测试覆盖完整                 | ⏳ 待开始   |
| **Week 12** | 1/13-17    | 压力测试 + 安全 + 文档               | 生产就绪                     | ⏳ 待开始   |

---

## 🎯 关键里程碑

### M1: P0 核心服务就绪 (Week 2 末 - 11 月 8 日)

**验收标准**:

- ✅ 所有 Go 服务可独立启动
- ✅ Wire 依赖注入完成
- ✅ Model Router 可路由请求
- ✅ Model Adapter 支持 3 个 Provider
- ✅ AI Orchestrator 可编排任务
- ✅ 端到端对话流程跑通

---

### M2: 数据流与实时分析 (Week 3 末 - 11 月 15 日)

**验收标准**:

- ✅ Flink 3 个 Job 正常运行
- ✅ ClickHouse 有实时数据
- ✅ Debezium CDC 工作正常
- ✅ Analytics Service API 可查询

---

### M3: AI 引擎完整 (Week 6 末 - 12 月 6 日)

**验收标准**:

- ✅ Agent Engine 可执行任务
- ✅ Voice Engine ASR/TTS/VAD 可用
- ✅ Multimodal Engine OCR/视觉理解可用
- ✅ Notification Service 可发送通知

---

### M4: 用户界面完成 (Week 8 末 - 12 月 20 日)

**验收标准**:

- ✅ 登录/注册可用
- ✅ 对话界面完整 (含流式)
- ✅ 知识库管理可用
- ✅ 分析看板展示数据

---

### M5: 可观测性与安全 (Week 9 末 - 12 月 27 日)

**验收标准**:

- ✅ 全链路追踪可视化
- ✅ Grafana Dashboard 完整
- ✅ 告警规则生效
- ✅ Vault 密钥管理就绪

---

### M6: 生产就绪 (Week 12 末 - 1 月 17 日)

**验收标准**:

- ✅ CI/CD 自动化工作
- ✅ 单元测试覆盖率 ≥70%
- ✅ E2E 测试通过
- ✅ 压力测试达标 (1k RPS)
- ✅ 安全扫描通过
- ✅ 文档齐全

---

## 📋 每周任务速查

### Week 1: P0 基础 (10/28-11/1)

```
✓ Wire依赖注入生成 (0.5天)
→ Model Router实现 (3天)
  - 模型注册表
  - 路由决策引擎
  - 成本优化器
→ Model Adapter实现 (3天)
  - OpenAI适配器
  - Claude适配器
  - 智谱AI适配器
```

### Week 2: P0 完成 (11/4-8)

```
→ AI Orchestrator (4天)
  - 任务路由器
  - 流程编排器
  - 结果聚合器
✓ 端到端集成测试 (1天)
```

### Week 3: 数据流 (11/11-15)

```
→ Flink Jobs (4天)
  - Message Stats Job
  - User Behavior Job
  - Document Analysis Job
→ Debezium CDC配置 (1天)
```

### Week 4: Agent (11/18-22)

```
→ Agent Engine (5天)
  - LangGraph工作流
  - ReAct模式
  - 工具注册表 (10个工具)
  - 长期记忆
```

### Week 5: Voice (11/25-29)

```
→ Voice Engine (5天)
  - ASR (Whisper)
  - TTS (Edge-TTS)
  - VAD (Silero-VAD)
  - WebRTC集成
```

### Week 6: Multimodal (12/2-6)

```
→ Multimodal Engine (5天)
  - OCR (PaddleOCR)
  - 视觉理解 (GPT-4V)
  - 表格识别
  - 文档布局分析
```

### Week 7-8: 前端 (12/9-20)

```
→ 核心页面 (10天)
  - 登录/注册
  - 对话界面 (流式)
  - 知识库管理
  - 分析看板
  - 设置页面
```

### Week 9: 可观测性 (12/23-27)

```
→ OpenTelemetry完善 (2天)
→ Loki日志集成 (1天)
→ Vault集成 (1天)
→ Grafana + AlertManager (1天)
```

### Week 10: CI/CD (12/30-1/3)

```
→ GitHub Actions (2天)
  - CI Pipeline
  - Docker构建
→ 单元测试补充 (3天)
  - 目标覆盖率70%+
```

### Week 11: 测试 (1/6-10)

```
→ 集成测试 (3天)
→ E2E测试 (2天)
  - Playwright配置
  - 关键流程测试
```

### Week 12: 优化 (1/13-17)

```
→ 压力测试 (2天)
  - k6脚本
  - 性能优化
→ 安全完善 (2天)
  - OAuth 2.0
  - MFA
→ 文档与复盘 (1天)
```

---

## 👥 团队分工

### Go Team (2 人)

**主要职责**:

- Week 1-2: Model Router, AI Orchestrator
- Week 3: Analytics Service, Debezium
- Week 4-5: Notification Service
- Week 9: OpenTelemetry, Vault
- Week 10-12: 测试与优化

### Python Team (2 人)

**主要职责**:

- Week 1: Model Adapter
- Week 3: Flink Jobs
- Week 4: Agent Engine
- Week 5: Voice Engine
- Week 6: Multimodal Engine
- Week 9: 可观测性
- Week 10-12: 测试与优化

### Frontend (Week 7-8 全员转前端)

**主要职责**:

- Week 7: 核心组件 + 登录/对话页面
- Week 8: 知识库/分析页面

---

## 🚨 每日站会 (15 分钟)

**时间**: 每天上午 10:00

**议程**:

1. 昨天完成了什么？(5 分钟)
2. 今天计划做什么？(5 分钟)
3. 有什么阻塞？(5 分钟)

---

## 📊 进度追踪

### 更新方式

```bash
# 每天更新进度
git pull
# 编辑 WEEKLY_PLAN_SUMMARY.md
# 更新任务状态: ⏳ → 🔄 → ✅

git add WEEKLY_PLAN_SUMMARY.md
git commit -m "docs: update week N progress"
git push
```

### 状态标记

- 🔜 即将开始
- ⏳ 待开始
- 🔄 进行中
- ✅ 已完成
- ⚠️ 有风险
- ❌ 已阻塞

---

## 🔧 常用命令

### 启动开发环境

```bash
# 启动所有依赖服务
docker-compose up -d postgres redis kafka minio milvus clickhouse

# 启动Go服务 (示例)
cd cmd/knowledge-service
go run main.go

# 启动Python服务 (示例)
cd algo/rag-engine
source venv/bin/activate
python main.py

# 启动前端
cd platforms/web
npm run dev
```

### 运行测试

```bash
# Go单元测试
go test ./... -v -cover

# Python单元测试
pytest -v --cov=app

# 前端测试
npm test

# E2E测试
npx playwright test
```

### 查看日志

```bash
# Kubernetes
kubectl logs -f deployment/knowledge-service -n voicehelper

# Docker Compose
docker-compose logs -f knowledge-service
```

---

## 📞 紧急联系

### 阻塞升级流程

1. **技术问题**: 在 Slack #voicehelper-dev 提问
2. **阻塞超过 4 小时**: @Tech Lead
3. **影响里程碑**: 立即 escalate

### 周末支持

- **紧急故障**: PagerDuty
- **非紧急问题**: Slack (周一处理)

---

## 📚 参考资料

### 必读文档

1. `.cursorrules` - 开发规范
2. `docs/arch/microservice-architecture-v2.md` - 架构设计
3. `docs/migration-checklist.md` - 迁移清单
4. `INCOMPLETE_FEATURES.md` - 未完成功能清单
5. `P0_IMPLEMENTATION_COMPLETE.md` - P0 完成报告

### 外部资源

- [Kratos 文档](https://go-kratos.dev/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Flink PyFlink 文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/)
- [Next.js 文档](https://nextjs.org/docs)

---

**最后更新**: 2025-10-26
**下次更新**: 每周五 17:00
**维护者**: 项目经理 + Tech Lead
