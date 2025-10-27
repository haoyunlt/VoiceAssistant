# 代码质量工具和指南

本目录包含代码质量相关的工具、配置和文档。

## 📚 文档索引

### 未使用代码检测

- **[未使用代码检测指南](./UNUSED_CODE_DETECTION.md)** - 完整的使用指南
- **工具配置**:
  - Go: `/.golangci.yml`
  - Python: `/pyproject.toml`
- **CI 配置**: `/.github/workflows/unused-code-check.yml`
- **本地脚本**:
  - `/scripts/check-unused-code.sh` - 快速检测脚本
  - `/scripts/analyze-unused-code.py` - 详细分析脚本

### 代码审查报告

- **[未使用函数完整报告](../../CODE_REVIEW_UNUSED_FUNCTIONS.md)** - 当前项目的完整分析报告

## 🛠️ 快速开始

### 检测未使用代码

```bash
# 快速检测
./scripts/check-unused-code.sh

# 详细分析
python3 scripts/analyze-unused-code.py
```

### 查看历史报告

```bash
# 查看最近的报告
ls -lt .reports/unused-summary-*.md | head -5

# 查看完整代码审查报告
cat CODE_REVIEW_UNUSED_FUNCTIONS.md
```

## 📊 质量指标

项目当前状态（2025-10-27）:

- **Go 未使用函数**: 309 个
  - 未使用构造函数: 74 个
  - 完全未使用函数: 235 个
- **Python 未使用函数**: 16 个
- **总计**: 325 个

目标:

- Q1 2025: 减少到 < 200 个
- Q2 2025: 减少到 < 100 个
- Q3 2025: 减少到 < 50 个

## 🔄 工作流程

### 1. 定期检测（每周）

```bash
# 运行检测
./scripts/check-unused-code.sh

# 查看报告
cat .reports/unused-summary-$(date +%Y%m%d)*.md
```

### 2. PR 检查

每次提交 PR 时，CI 会自动：

1. 运行未使用代码检测
2. 在 PR 中评论检测结果
3. 生成详细报告（Artifacts）

### 3. 清理流程

1. **识别**: 运行检测工具
2. **分类**: 区分真正的死代码和误报
3. **确认**: 与团队沟通确认
4. **清理**: 删除确认的死代码
5. **测试**: 运行测试确保功能正常
6. **提交**: 创建 PR

## 🎯 清理优先级

### P0 - 立即清理（预计 ~100 个）

- ✅ 明确不需要的第三方集成
- ✅ 确认不使用的完整功能模块
- ✅ Python 未使用的工具函数

### P1 - 短期清理（预计 ~80 个）

- 🔄 上下文压缩相关（如不使用）
- 🔄 病毒扫描集成
- 🔄 服务注册与发现（如使用 K8s）

### P2 - 长期清理（预计 ~60 个）

- 📋 高级缓存操作
- 📋 批处理操作
- 📋 Domain 模型的高级方法

## 🔍 常见问题

### Q: Wire 依赖注入的构造函数被标记为未使用？

A: 这些函数在 `wire.go` 中被使用，不应删除。配置文件已排除 `wire.go`。

### Q: 如何标记预留功能？

A: 使用以下注释格式：

```go
// RESERVED: 为 OAuth 集成预留
// Roadmap: Q2 2024
// Issue: #123
func LoginWithOAuth() error {
    panic("not implemented")
}
```

### Q: 检测报告太长，如何筛选？

A: 使用 grep 过滤：

```bash
# 只看 conversation-service
./scripts/check-unused-code.sh 2>&1 | grep conversation-service

# 只看导出函数
./scripts/check-unused-code.sh 2>&1 | grep "^func [A-Z]"
```

## 📈 持续改进

### 自动化

- [x] CI/CD 集成
- [x] 每周自动扫描
- [x] PR 自动评论
- [ ] 自动创建清理 Issue
- [ ] 趋势分析和可视化

### 工具增强

- [x] golangci-lint 配置
- [x] Ruff + Vulture 集成
- [ ] 自定义检测规则
- [ ] 更智能的误报过滤

### 流程优化

- [x] 详细文档
- [x] 快速检测脚本
- [ ] 清理任务看板
- [ ] 定期回顾会议

## 🔗 相关资源

### 内部资源

- [运维手册](../runbook/index.md)
- [架构文档](../arch/overview.md)
- [SLO 指标](../nfr/slo.md)

### 外部工具

- [golangci-lint](https://golangci-lint.run/)
- [Ruff](https://docs.astral.sh/ruff/)
- [Vulture](https://github.com/jendrikseipp/vulture)

## 📝 贡献指南

### 添加新的检测规则

1. 编辑 `.golangci.yml` 或 `pyproject.toml`
2. 测试新规则
3. 更新文档
4. 提交 PR

### 改进检测脚本

1. 修改 `scripts/check-unused-code.sh` 或 `scripts/analyze-unused-code.py`
2. 添加测试用例
3. 更新文档
4. 提交 PR

## 🆘 获取帮助

- **技术支持**: 查看 [未使用代码检测指南](./UNUSED_CODE_DETECTION.md)
- **GitHub Issues**: [创建 Issue](https://github.com/your-org/your-repo/issues/new)
- **团队联系**: tech-lead@voiceassistant.com

---

**最后更新**: 2025-10-27
**维护者**: AI 客服平台团队
