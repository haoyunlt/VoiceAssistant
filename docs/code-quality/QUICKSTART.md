# 代码质量检测快速入门

5 分钟快速上手未使用代码检测工具。

## ⚡ 快速开始

### 1. 安装工具（首次使用）

```bash
# Go 工具
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Python 工具
pip install ruff vulture
```

### 2. 运行检测

```bash
# 使用 Makefile（推荐）
make check-unused

# 或直接运行脚本
./scripts/check-unused-code.sh
```

### 3. 查看结果

```bash
# 查看摘要报告
cat .reports/unused-summary-*.md | tail -100

# 或生成详细报告
make analyze-unused
cat unused-code-report.md
```

## 📝 常用命令

### 检测命令

```bash
# 基本检测
make check-unused

# 自动修复（仅安全修复）
make check-unused-fix

# 详细分析
make analyze-unused

# 只检查 Go 代码
make lint-go

# 只检查 Python 代码
make lint-python
```

### 检查特定服务

```bash
# Go 服务
golangci-lint run --enable=unused cmd/conversation-service/...

# Python 服务
ruff check algo/rag-engine/ --select F401,F841,ARG
```

## 🎯 解读结果

### Go 代码示例

```
cmd/service/internal/biz/handler.go:45:1:
  func `ProcessRequest` is unused (unused)
```

**含义**: 函数 `ProcessRequest` 在第 45 行定义但未被使用

**处理**:

1. 搜索代码确认是否真的未使用
2. 如果未使用：删除函数
3. 如果是预留功能：添加 `// RESERVED: ...` 注释

### Python 代码示例

```
algo/service/app/utils.py:10:5: F841
  Local variable `result` is assigned to but never used
```

**含义**: 变量 `result` 被赋值但从未使用

**处理**:

1. 检查是否是调试代码
2. 删除未使用的变量
3. 或使用 `_result` 表示有意忽略

## ⚠️ 常见问题

### Q: Wire 构造函数被标记为未使用？

**A**: 这些函数在 `wire.go` 中使用，配置已自动排除。

### Q: 测试辅助函数被标记？

**A**: 测试文件已自动排除。如果是共享测试工具，移到 `testutil` 包。

### Q: 如何跳过某个文件？

**A**: 编辑 `.golangci.yml`:

```yaml
issues:
  exclude-rules:
    - path: internal/feature/special.go
      linters:
        - unused
```

## 🚀 CI/CD 集成

### 查看 CI 结果

1. 访问 GitHub Actions
2. 找到 "Unused Code Detection" workflow
3. 下载 Artifacts 查看详细报告

### PR 检查

每次提交 PR 时会自动：

- ✅ 运行检测
- ✅ 在 PR 中评论结果
- ✅ 生成详细报告

## 📊 示例输出

### 检测摘要

```
================================
未使用代码检测工具
================================

检查必要工具...
✓ golangci-lint
✓ ruff
✓ vulture

🔍 分析 Go 代码...
⚠️  Go 代码：发现 45 个问题

🔍 分析 Python 代码...
✅ Python 代码：未发现未使用代码

================================
⚠️  检测完成：发现 45 个问题
================================

查看详细报告:
  - Go:     .reports/unused-go-20241027.txt
  - Python: .reports/unused-python-20241027.txt
  - 摘要:   .reports/unused-summary-20241027.md
```

## 🔧 自动修复

某些问题可以自动修复：

```bash
# 自动删除未使用的导入
make check-unused-fix

# 或手动指定
golangci-lint run --fix --enable=unused
ruff check algo/ --fix --select F401
```

## 📚 下一步

- **详细文档**: [未使用代码检测指南](./UNUSED_CODE_DETECTION.md)
- **完整报告**: [代码审查报告](../../CODE_REVIEW_UNUSED_FUNCTIONS.md)
- **配置说明**: [代码质量工具](./README.md)

## 💡 最佳实践

### 开发阶段

```bash
# 提交前检查
make check-unused

# 修复安全问题
make check-unused-fix

# 提交代码
git add .
git commit -m "fix: remove unused code"
```

### 代码审查

在 PR Review 时检查：

- [ ] 新增函数是否被调用？
- [ ] 是否有未使用的参数？
- [ ] 导入是否都被使用？

### 定期清理

```bash
# 每周运行一次
make analyze-unused

# 查看趋势
ls -lt .reports/ | head -10
```

## 🎓 学习资源

- **5 分钟教程**: 本文档
- **30 分钟教程**: [详细指南](./UNUSED_CODE_DETECTION.md)
- **工具文档**:
  - [golangci-lint](https://golangci-lint.run/)
  - [Ruff](https://docs.astral.sh/ruff/)

---

**快速反馈**: 如有问题，请提交 [GitHub Issue](https://github.com/your-org/your-repo/issues)
