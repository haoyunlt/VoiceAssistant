# VoiceHelper 团队协作指南

> **适用对象**: 全体开发团队 (4 人核心 + 兼职支持)
> **更新日期**: 2025-10-26
> **版本**: v1.0

---

## 👥 团队结构

### 核心团队

| 角色                    | 人数 | 主要职责            | 技术栈                              |
| ----------------------- | ---- | ------------------- | ----------------------------------- |
| **Backend Engineer**    | 2    | Go 微服务开发       | Go, Kratos, gRPC, PostgreSQL        |
| **AI Engineer**         | 2    | Python 算法服务开发 | Python, FastAPI, LangChain, PyTorch |
| **SRE Engineer** (兼职) | 0.5  | 基础设施与部署      | K8s, Helm, APISIX, Prometheus       |
| **QA Engineer** (兼职)  | 0.5  | 测试与质量保证      | pytest, Playwright, k6              |

### 团队分工

**Backend Engineer 1** (Go 后端负责人):

- 领域: Knowledge Service, AI Orchestrator, Model Router
- 次要: Gateway 配置, Identity Service 完善

**Backend Engineer 2** (Go 后端):

- 领域: Gateway 配置, Notification Service
- 次要: Conversation Service 完善, Analytics Service

**AI Engineer 1** (Python 算法负责人):

- 领域: RAG Engine, Model Adapter
- 次要: Agent Engine 工具系统

**AI Engineer 2** (Python 算法):

- 领域: Agent Engine, Voice Engine, Multimodal Engine
- 次要: Retrieval Service 优化

---

## 📅 每日工作流程

### 早上 10:00 - 每日站会 (15 分钟)

**地点**: 会议室 / 线上会议

**议程**:

1. **轮流分享** (每人 3 分钟):

   - 昨天完成了什么
   - 今天计划做什么
   - 有什么阻碍或需要帮助

2. **快速讨论** (5 分钟):
   - 识别阻碍并指定解决人
   - 协调跨团队依赖
   - 调整优先级 (如必要)

**注意事项**:

- ⏰ 准时开始，严格控制时间
- 🎯 只讨论重点，细节会后沟通
- 📝 记录阻碍和行动项

### 工作时间 10:15-12:00 & 14:00-18:00

**专注开发时间**:

- 🔕 减少打扰，专注编码
- 💬 异步沟通为主 (Slack/企业微信)
- 🆘 紧急问题可同步沟通

**午休**: 12:00-14:00

**下午茶时间**: 15:30-16:00 (可选)

- 轻松交流技术话题
- 分享学习资源
- 团队建设

### 每周五 17:00 - 周回顾与演示 (1 小时)

**Part 1: 演示 (30 分钟)**

1. **Demo 新功能** (每人 5-8 分钟):

   - 展示本周完成的功能
   - 演示关键技术点
   - 分享遇到的挑战和解决方案

2. **指标回顾** (10 分钟):
   - 查看本周完成度
   - 对比预期 vs 实际
   - 识别偏差原因

**Part 2: 回顾 (30 分钟)**

1. **What went well** (做得好的):

   - 表扬团队成员贡献
   - 记录成功实践

2. **What could be improved** (可改进的):

   - 识别问题和瓶颈
   - 讨论改进措施

3. **Action items** (行动项):
   - 明确下周计划
   - 分配责任人
   - 设定验收标准

---

## 💬 沟通规范

### 沟通渠道

| 渠道                  | 用途                   | 响应时间   |
| --------------------- | ---------------------- | ---------- |
| **Slack / 企业微信**  | 日常异步沟通           | 2 小时内   |
| **GitHub Issues**     | Bug 报告、功能请求     | 1 工作日内 |
| **GitHub PR**         | 代码评审               | 4 小时内   |
| **会议室 / 视频会议** | 紧急问题、技术方案讨论 | 即时       |
| **邮件**              | 正式通知、周报         | 1 工作日内 |

### Slack 频道设置

```
#voicehelper-general     - 通用讨论
#voicehelper-backend     - Go 后端团队
#voicehelper-ai          - Python 算法团队
#voicehelper-devops      - 部署与基础设施
#voicehelper-qa          - 测试与质量
#voicehelper-alerts      - 告警通知 (自动)
#voicehelper-deploys     - 部署通知 (自动)
#voicehelper-random      - 闲聊娱乐
```

### 沟通礼仪

**提问时**:

- ✅ 先自己尝试解决 (搜索文档、查看代码)
- ✅ 提供完整上下文 (错误信息、环境、已尝试方案)
- ✅ 描述预期行为 vs 实际行为
- ❌ 不要只说 "不 work" 或 "有问题"

**回答时**:

- ✅ 及时响应，即使只是说 "我稍后回复"
- ✅ 提供具体解决方案或参考文档
- ✅ 必要时安排面对面讨论
- ❌ 不要忽略他人求助

**异步沟通**:

- ✅ 使用 Thread 保持讨论集中
- ✅ 重要结论做摘要发主频道
- ✅ 使用 Emoji 表达态度 (👍 🎉 🤔)
- ❌ 不要 @channel / @here (除非紧急)

---

## 📝 代码协作规范

### Git 工作流

**分支策略**:

```
main (protected)
  └── develop
      ├── feature/backend-1/knowledge-service-minio
      ├── feature/ai-1/rag-engine-query-rewriter
      ├── bugfix/backend-2/conversation-cache-issue
      └── refactor/ai-2/agent-engine-langgraph
```

**分支命名**:

```
feature/<role>/<description>   - 新功能
bugfix/<role>/<description>    - Bug 修复
refactor/<role>/<description>  - 重构
hotfix/<description>           - 紧急修复
```

**Commit 规范**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**:

- `feat`: 新功能
- `fix`: Bug 修复
- `refactor`: 重构 (不改变功能)
- `docs`: 文档更新
- `test`: 测试相关
- `chore`: 构建/工具相关
- `perf`: 性能优化

**示例**:

```
feat(knowledge): implement MinIO file upload

- Add MinIO client initialization
- Implement upload/download methods
- Add virus scanning integration
- Publish document.uploaded event to Kafka

Closes #123
```

### Pull Request (PR) 流程

**1. 创建 PR**

- ✅ 使用 PR 模板 (自动填充)
- ✅ 填写变更说明和测试证据
- ✅ 关联 GitHub Issue
- ✅ 添加 Reviewer (至少 1 人)
- ✅ 添加标签 (area/_, priority/_)

**2. Code Review**

**Reviewer 职责**:

- 🔍 检查代码质量和规范
- 🐛 识别潜在 Bug
- 💡 提出改进建议
- ⚡ 4 小时内完成首次 Review

**Review 评论规范**:

```
[必须修改] 这里有个空指针风险
[建议] 可以考虑用 sync.Pool 优化性能
[疑问] 为什么选择这种方案?
[表扬] 这段代码写得很优雅! 👍
```

**3. 修改与讨论**

- 💬 及时回复 Review 评论
- ✅ 修改后重新请求 Review
- 🤝 有分歧时面对面讨论

**4. 合并**

- ✅ 所有 CI 检查通过
- ✅ 至少 1 个 Approve
- ✅ 解决所有冲突
- ✅ Squash and merge (保持历史清晰)

### Code Review 清单

**功能性**:

- [ ] 功能是否符合需求
- [ ] 边界条件是否考虑
- [ ] 错误处理是否完善

**代码质量**:

- [ ] 命名是否清晰
- [ ] 是否有重复代码
- [ ] 复杂度是否合理
- [ ] 注释是否必要且准确

**性能**:

- [ ] 是否有性能瓶颈
- [ ] 资源使用是否合理
- [ ] 并发安全性

**测试**:

- [ ] 单元测试是否充分
- [ ] 测试用例是否覆盖边界
- [ ] Mock 是否合理

**文档**:

- [ ] API 文档是否更新
- [ ] Runbook 是否更新
- [ ] 重要决策是否记录

---

## 🧪 测试规范

### 测试金字塔

```
       /\
      /E2E\        10% (关键路径)
     /------\
    /Integ  \      20% (服务间集成)
   /----------\
  /   Unit     \   70% (单元测试)
 /--------------\
```

### 单元测试规范

**Go 测试**:

```go
// knowledge_service_test.go
func TestUploadDocument(t *testing.T) {
    // Arrange
    mockMinIO := &MockMinIOClient{}
    mockKafka := &MockKafkaProducer{}
    service := NewKnowledgeService(mockMinIO, mockKafka)

    // Act
    doc, err := service.UploadDocument(context.Background(), file)

    // Assert
    assert.NoError(t, err)
    assert.NotEmpty(t, doc.ID)
    mockMinIO.AssertCalled(t, "Upload", mock.Anything)
    mockKafka.AssertCalled(t, "Publish", mock.Anything)
}
```

**Python 测试**:

```python
# test_rag_engine.py
def test_query_rewriter():
    # Arrange
    rewriter = QueryRewriter()
    query = "什么是 GraphRAG?"

    # Act
    rewritten_queries = rewriter.rewrite(query)

    # Assert
    assert len(rewritten_queries) >= 2
    assert all(isinstance(q, str) for q in rewritten_queries)
```

### 测试覆盖率要求

| 代码类型         | 覆盖率要求 |
| ---------------- | ---------- |
| **核心业务逻辑** | ≥ 80%      |
| **数据层**       | ≥ 70%      |
| **API 层**       | ≥ 60%      |
| **工具函数**     | ≥ 90%      |

**检查命令**:

```bash
# Go
go test ./... -coverprofile=coverage.out
go tool cover -html=coverage.out

# Python
pytest --cov=algo --cov-report=html
```

---

## 📚 文档规范

### 必须文档

| 文档类型               | 负责人              | 更新时机        |
| ---------------------- | ------------------- | --------------- |
| **README.md**          | Service Owner       | 功能变更时      |
| **API 文档**           | Backend/AI Engineer | API 变更时      |
| **Runbook**            | Service Owner       | 部署/运维变更时 |
| **ADR (架构决策记录)** | Tech Lead           | 重大技术决策时  |
| **周报**               | 全员                | 每周五          |

### README.md 模板

```markdown
# Service Name

## 功能概述

简要描述服务职责和核心功能。

## 技术栈

- 框架: Kratos / FastAPI
- 数据库: PostgreSQL
- 消息队列: Kafka

## 快速开始

### 本地开发

\`\`\`bash

# 安装依赖

make install

# 运行服务

make run

# 运行测试

make test
\`\`\`

### Docker 运行

\`\`\`bash
docker-compose up
\`\`\`

## API 文档

详见 [API 文档](docs/api/)

## 配置说明

详见 [配置文档](configs/)

## 故障排查

详见 [Runbook](docs/runbook/)
```

### 代码注释规范

**Go 注释**:

```go
// UploadDocument 上传文档到 MinIO 并发布事件
//
// 参数:
//   - ctx: 上下文
//   - file: 文件内容
//   - metadata: 文档元数据
//
// 返回:
//   - Document: 文档信息
//   - error: 错误信息
//
// 流程:
//   1. 病毒扫描
//   2. 上传到 MinIO
//   3. 保存元数据到 PostgreSQL
//   4. 发布 document.uploaded 事件
func (s *KnowledgeService) UploadDocument(
    ctx context.Context,
    file io.Reader,
    metadata *DocumentMetadata,
) (*Document, error) {
    // 实现...
}
```

**Python 注释**:

```python
def rewrite_query(self, query: str) -> List[str]:
    """使用多种策略改写查询以提升检索效果

    Args:
        query: 原始查询文本

    Returns:
        改写后的查询列表 (包含原查询)

    Methods:
        - HyDE: 生成假设性文档
        - Multi-Query: 生成相关查询变体
        - Step-back: 生成更抽象的查询

    Example:
        >>> rewriter = QueryRewriter()
        >>> queries = rewriter.rewrite("什么是 GraphRAG?")
        >>> len(queries)
        3
    """
    # 实现...
```

---

## 🐛 Bug 处理流程

### 1. Bug 报告

**创建 GitHub Issue**:

```markdown
Title: [Bug] Knowledge Service 文件上传失败

**环境**:

- 服务: knowledge-service v1.0.0
- 环境: Dev
- 浏览器: Chrome 120

**重现步骤**:

1. 登录系统
2. 上传 10MB PDF 文件
3. 观察错误

**预期行为**:
文件上传成功

**实际行为**:
返回 500 错误: "MinIO connection timeout"

**错误日志**:
\`\`\`
2025-10-26 10:30:45 ERROR [knowledge-service] MinIO.Upload failed: context deadline exceeded
\`\`\`

**影响范围**:
阻塞所有文件上传功能

**优先级**: P0 (阻塞)
```

### 2. Bug 分类

| 优先级 | 响应时间 | 修复时间 | 说明               |
| ------ | -------- | -------- | ------------------ |
| **P0** | 30 分钟  | 4 小时   | 阻塞核心功能       |
| **P1** | 2 小时   | 1 天     | 影响重要功能       |
| **P2** | 1 天     | 1 周     | 次要功能或体验问题 |
| **P3** | 1 周     | 2 周     | 优化改进           |

### 3. Bug 修复流程

1. **分析**: 理解根因，评估影响范围
2. **修复**: 创建 bugfix 分支，编写修复代码
3. **测试**: 单元测试 + 回归测试
4. **Review**: 代码评审
5. **部署**: 合并并部署到受影响环境
6. **验证**: 验证 Bug 已修复
7. **总结**: 记录根因和改进措施

---

## 🚀 部署规范

### 部署环境

| 环境           | 用途       | 部署频率  | 审批流程            |
| -------------- | ---------- | --------- | ------------------- |
| **Dev**        | 开发测试   | 随时      | 无需审批            |
| **Staging**    | 预生产验证 | 每天      | Tech Lead 审批      |
| **Production** | 生产环境   | 每周/按需 | Tech Lead + PM 审批 |

### 部署检查清单

**部署前**:

- [ ] 所有 CI 检查通过
- [ ] Code Review 完成
- [ ] 单元测试覆盖率达标
- [ ] 集成测试通过
- [ ] 数据库迁移脚本准备
- [ ] Runbook 更新
- [ ] 回滚计划明确

**部署中**:

- [ ] 通知团队 (Slack #voicehelper-deploys)
- [ ] 执行数据库迁移
- [ ] 灰度发布 (如适用)
- [ ] 监控关键指标

**部署后**:

- [ ] 冒烟测试通过
- [ ] 监控指标正常
- [ ] 无错误告警
- [ ] 更新部署记录

---

## 📊 每周报告

### 个人周报模板

```markdown
# 个人周报 - Week X

**姓名**: [你的名字]
**角色**: Backend Engineer / AI Engineer
**日期**: 2025-10-XX ~ 2025-10-XX

## 本周完成

### 主要工作

1. ✅ [任务 1] Knowledge Service MinIO 集成 (2 天)

   - 实现文件上传/下载功能
   - 集成 ClamAV 病毒扫描
   - PR: #123

2. ✅ [任务 2] 文档上传完整流程 (3 天)
   - 端到端流程测试
   - Kafka 事件发布
   - 性能优化: 上传速度提升 50%

### 其他贡献

- 🔍 Code Review: 5 个 PR
- 📝 文档: 更新 Knowledge Service README
- 🐛 Bug 修复: #456 MinIO 连接超时问题

## 本周学习

- 📚 深入学习 MinIO Go SDK
- 💡 了解 Kafka 事件驱动最佳实践
- 🔧 掌握 ClamAV TCP 协议集成

## 下周计划

1. [ ] 开始 AI Orchestrator 任务路由器 (2 天)
2. [ ] 协助集成测试 (1 天)
3. [ ] 代码重构: 优化错误处理 (1 天)
4. [ ] 学习 gRPC 客户端开发

## 遇到的问题

- ⚠️ MinIO 在高并发下偶尔连接超时
  - 解决方案: 增加连接池大小，添加重试机制

## 需要的支持

- 🆘 需要 SRE 协助配置 MinIO 生产环境
- 💬 希望与 AI Engineer 讨论 Kafka 事件 Schema 设计
```

---

## 🎉 团队文化

### 价值观

1. **透明沟通**: 主动分享信息，及时同步进展
2. **相互帮助**: 遇到困难主动求助，看到困难主动帮忙
3. **持续学习**: 分享技术心得，共同成长
4. **追求卓越**: 代码质量第一，不妥协基本原则
5. **Work-Life Balance**: 高效工作，享受生活

### 团队活动

**技术分享** (双周五 18:00-19:00):

- 轮流分享技术主题
- 可以是新学的技术、踩过的坑、开源项目等

**Team Building** (每月):

- 团建活动 (聚餐、运动、游戏等)
- 放松身心，增进感情

**Code Review Club** (每周三 16:00-17:00):

- 一起 Review 有争议或复杂的 PR
- 讨论最佳实践
- 统一编码风格

---

## 📞 联系方式

### 紧急联系

| 角色             | 姓名 | Slack         | 电话 | 邮箱                     |
| ---------------- | ---- | ------------- | ---- | ------------------------ |
| **Tech Lead**    | TBD  | @tech-lead    | xxx  | tech-lead@example.com    |
| **Backend Lead** | TBD  | @backend-lead | xxx  | backend-lead@example.com |
| **AI Lead**      | TBD  | @ai-lead      | xxx  | ai-lead@example.com      |
| **SRE**          | TBD  | @sre          | xxx  | sre@example.com          |

### On-call 排班

生产环境问题 7x24 响应 (轮值制):

| 周     | Primary            | Secondary          |
| ------ | ------------------ | ------------------ |
| Week 3 | Backend Engineer 1 | AI Engineer 1      |
| Week 4 | Backend Engineer 2 | AI Engineer 2      |
| Week 5 | AI Engineer 1      | Backend Engineer 1 |
| Week 6 | AI Engineer 2      | Backend Engineer 2 |

**On-call 职责**:

- 响应生产告警 (15 分钟内)
- 紧急问题排查和修复
- 升级重大问题给 Tech Lead

---

## ✅ 入职清单

**新成员第一天**:

- [ ] 获取所有系统账号 (GitHub, Slack, 云平台)
- [ ] Clone 代码仓库
- [ ] 配置本地开发环境
- [ ] 阅读架构文档和迭代计划
- [ ] 加入所有 Slack 频道
- [ ] 与团队成员一一认识

**新成员第一周**:

- [ ] 完成第一个小 PR (文档或小功能)
- [ ] 参加每日站会和周五演示
- [ ] 理解整体架构和核心流程
- [ ] 熟悉开发和部署流程

---

**祝合作愉快! 🚀**

有任何问题，随时在 Slack 提问！
