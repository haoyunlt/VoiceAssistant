# 📚 VoiceHelper 项目导航

> **快速找到您需要的文档**

---

## 🗂️ 文档结构

```
VoiceAssistant/
├── 📋 规划与进度
│   ├── WEEKLY_PLAN_SUMMARY.md        ⭐ 周计划速查表 (每周更新)
│   ├── DETAILED_WEEK_PLAN.md         📅 详细12周计划 (每天任务)
│   ├── IMPLEMENTATION_STATUS.md       📊 实施状态报告 (每日更新)
│   ├── INCOMPLETE_FEATURES.md         📝 未完成功能清单
│   └── P0_IMPLEMENTATION_COMPLETE.md  ✅ P0完成报告
│
├── 📖 架构与设计
│   ├── .cursorrules                   📐 开发规范 (必读)
│   ├── docs/arch/
│   │   └── microservice-architecture-v2.md  🏗️ 架构设计v2.0
│   ├── docs/migration-checklist.md    🔄 迁移清单
│   └── docs/api/API_OVERVIEW.md        🔌 API总览
│
├── 🚀 快速开始
│   ├── README.md                       👋 项目概览
│   ├── QUICKSTART.md                   ⚡ 快速启动指南
│   └── CONTRIBUTING.md                 🤝 贡献指南
│
└── 📈 其他文档
    ├── CODE_REVIEW_SUMMARY.md          🔍 代码评审总结
    ├── CHANGELOG.md                     📜 变更日志
    └── LICENSE                          📄 许可证
```

---

## 🎯 按场景查找文档

### 💼 项目经理 / Tech Lead

**今天要看什么？**

```
1️⃣ IMPLEMENTATION_STATUS.md       - 查看当前进度
2️⃣ WEEKLY_PLAN_SUMMARY.md         - 查看本周计划
3️⃣ INCOMPLETE_FEATURES.md         - 了解剩余任务
```

**每周一早上**:

- 📊 回顾上周完成度 (`IMPLEMENTATION_STATUS.md`)
- 📅 查看本周任务 (`WEEKLY_PLAN_SUMMARY.md`)
- 🎯 更新里程碑状态

**每周五下午**:

- ✅ 更新任务完成状态
- 📝 记录问题与风险
- 📊 生成周报

---

### 👨‍💻 开发工程师

**开始编码前**:

```
1️⃣ .cursorrules                   - 了解编码规范
2️⃣ WEEKLY_PLAN_SUMMARY.md         - 查看今天的任务
3️⃣ docs/arch/                     - 查看架构设计
```

**遇到问题时**:

- 🏗️ `docs/arch/microservice-architecture-v2.md` - 架构问题
- 🔌 `docs/api/API_OVERVIEW.md` - API 使用
- 📖 `docs/runbook/` - 运维问题
- 🔍 `CODE_REVIEW_SUMMARY.md` - 代码问题

**提交代码前**:

- ✅ 对照`.cursorrules`检查规范
- 🧪 运行单元测试
- 📝 更新相关文档

---

### 🆕 新成员入职

**第 1 天**: 环境搭建

```bash
1. 阅读 README.md
2. 阅读 QUICKSTART.md
3. 搭建开发环境
4. 运行 docker-compose up -d
5. 验证所有服务可启动
```

**第 2 天**: 熟悉项目

```
1. 阅读 .cursorrules (开发规范)
2. 阅读 docs/arch/microservice-architecture-v2.md (架构)
3. 浏览 INCOMPLETE_FEATURES.md (了解全貌)
4. 查看 WEEKLY_PLAN_SUMMARY.md (当前进度)
```

**第 3 天**: 开始贡献

```
1. 领取 WEEKLY_PLAN_SUMMARY.md 中的任务
2. 阅读相关模块的设计文档
3. 编写代码 (参考 .cursorrules)
4. 提交第一个PR
```

---

### 🔍 Code Review

**Reviewer 检查清单**:

```
☑️ 是否符合 .cursorrules 规范？
☑️ 是否更新了相关文档？
☑️ 是否添加了单元测试？
☑️ 是否添加了监控指标？
☑️ 是否有明确的错误处理？
☑️ 是否考虑了性能影响？
☑️ 是否考虑了安全问题？
```

**参考文档**:

- `.cursorrules` - 代码规范
- `CONTRIBUTING.md` - PR 模板
- `docs/arch/` - 架构规范

---

## 📅 文档更新频率

| 文档                       | 更新频率 | 负责人    |
| -------------------------- | -------- | --------- |
| `IMPLEMENTATION_STATUS.md` | 每日     | Tech Lead |
| `WEEKLY_PLAN_SUMMARY.md`   | 每周五   | PM        |
| `DETAILED_WEEK_PLAN.md`    | 按需调整 | PM        |
| `INCOMPLETE_FEATURES.md`   | 每周     | Tech Lead |
| `CHANGELOG.md`             | 每次发布 | Tech Lead |
| `.cursorrules`             | 每月     | Architect |
| 架构文档                   | 每季度   | Architect |

---

## 🔥 本周关注 (Week 1)

### 必读文档

1. 📅 `WEEKLY_PLAN_SUMMARY.md` - Week 1 任务
2. 📖 `DETAILED_WEEK_PLAN.md` - Day 1-5 详细任务
3. 📐 `.cursorrules` - Go/Python 编码规范

### 关键任务

```
Day 1 (周一):  Wire依赖注入生成
Day 2-3:      Model Router基础实现
Day 4-5:      Model Adapter完善
```

---

## 🎯 快速命令

### 查看今天的任务

```bash
# 打开周计划
open WEEKLY_PLAN_SUMMARY.md

# 或使用grep查找本周任务
grep "Week 1" DETAILED_WEEK_PLAN.md -A 100
```

### 更新进度

```bash
# 1. 编辑文档
code IMPLEMENTATION_STATUS.md

# 2. 更新任务状态 (⏳ → 🔄 → ✅)

# 3. 提交
git add IMPLEMENTATION_STATUS.md
git commit -m "docs: update day 1 progress"
git push
```

### 查看剩余任务

```bash
# 查看所有未完成的P0任务
grep "⏳" WEEKLY_PLAN_SUMMARY.md | grep "P0"

# 查看所有进行中的任务
grep "🔄" IMPLEMENTATION_STATUS.md
```

---

## 📞 获取帮助

### 技术问题

1. 🔍 搜索相关文档 (`docs/`)
2. 💬 在 Slack #voicehelper-dev 提问
3. 👨‍💻 @相关模块负责人

### 流程问题

1. 📖 查看 `CONTRIBUTING.md`
2. 💬 在 Slack #voicehelper-general 提问
3. 📧 联系 PM

### 紧急问题

1. 🚨 影响线上: PagerDuty
2. ⚠️ 阻塞开发: @Tech Lead
3. ❓ 其他问题: Slack

---

## 🌟 最佳实践

### 每天开始前

```
1. git pull (拉取最新代码)
2. 查看 IMPLEMENTATION_STATUS.md (了解当前进度)
3. 查看 WEEKLY_PLAN_SUMMARY.md (确认今日任务)
4. 更新任务状态为 🔄 (开始工作)
```

### 每天结束时

```
1. git push (提交代码)
2. 更新 IMPLEMENTATION_STATUS.md
   - 完成的任务标记为 ✅
   - 遇到的问题记录下来
3. 准备明天的任务
```

### 每周五下午

```
1. Demo演示本周成果
2. 更新 WEEKLY_PLAN_SUMMARY.md
3. 记录问题与改进
4. 规划下周任务
```

---

## 📊 文档优先级

### ⭐⭐⭐ 必读 (每天)

- `WEEKLY_PLAN_SUMMARY.md` - 周计划速查
- `IMPLEMENTATION_STATUS.md` - 当前状态
- `.cursorrules` - 开发规范

### ⭐⭐ 重要 (每周)

- `DETAILED_WEEK_PLAN.md` - 详细计划
- `INCOMPLETE_FEATURES.md` - 未完成功能
- `docs/arch/microservice-architecture-v2.md` - 架构

### ⭐ 参考 (按需)

- `CODE_REVIEW_SUMMARY.md` - 代码评审
- `CHANGELOG.md` - 变更历史
- `docs/runbook/` - 运维手册

---

## 🔄 文档演进

### 阶段 1: 规划阶段 (当前)

**核心文档**:

- ✅ `WEEKLY_PLAN_SUMMARY.md`
- ✅ `DETAILED_WEEK_PLAN.md`
- ✅ `IMPLEMENTATION_STATUS.md`
- ✅ `INCOMPLETE_FEATURES.md`

### 阶段 2: 开发阶段 (Week 1-9)

**新增文档**:

- [ ] `docs/api/` - API 文档完善
- [ ] `docs/runbook/` - 运维手册
- [ ] `tests/` - 测试文档

### 阶段 3: 优化阶段 (Week 10-12)

**新增文档**:

- [ ] `docs/nfr/` - 性能报告
- [ ] `docs/threat-model/` - 安全威胁
- [ ] `docs/adr/` - 架构决策记录

---

## 🎨 文档约定

### 状态图标

- ✅ 已完成
- 🔄 进行中
- ⏳ 待开始
- ⚠️ 有风险
- ❌ 已阻塞
- 🔜 即将开始

### 优先级标记

- 🔥 紧急且重要
- ⚡ 紧急不重要
- ⭐ 重要不紧急
- 💡 不紧急不重要

### 文档类型

- 📋 计划类
- 📊 报告类
- 📖 设计类
- 🚀 指南类
- 🔧 手册类

---

## 📝 反馈与改进

### 文档有问题？

1. 在 GitHub 提 Issue
2. 在 Slack #voicehelper-docs 反馈
3. 直接提 PR 改进

### 建议新文档？

1. 在 Slack 提出需求
2. 讨论必要性
3. 分配负责人
4. 创建并维护

---

**导航更新**: 2025-10-26
**维护者**: Tech Lead + PM
**反馈渠道**: Slack #voicehelper-docs
