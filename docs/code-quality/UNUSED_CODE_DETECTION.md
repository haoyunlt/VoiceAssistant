# 未使用代码检测指南

本文档介绍如何使用静态分析工具检测和清理项目中的未使用代码。

## 🎯 目标

- 自动检测未使用的函数、变量、参数
- 发现死代码（永远不会执行的代码）
- 提高代码质量，减少技术债
- 降低代码维护成本

## 🛠️ 工具概览

### Go 代码分析

我们使用 **golangci-lint** 集成多个检测器：

- `unused`: 检测未使用的常量、变量、函数和类型
- `deadcode`: 检测死代码
- `unparam`: 检测未使用的函数参数
- `ineffassign`: 检测无效的赋值
- `varcheck`: 检测未使用的全局变量和常量
- `structcheck`: 检测未使用的结构体字段

### Python 代码分析

我们使用多个工具组合：

- **Ruff**: 检测未使用的导入 (F401)、变量 (F841)、参数 (ARG)
- **Vulture**: 专门的死代码检测工具
- **MyPy**: 类型检查（可选）

## 📦 工具安装

### Go 工具

```bash
# 安装 golangci-lint
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# 验证安装
golangci-lint --version
```

### Python 工具

```bash
# 使用 pip 安装
pip install ruff vulture pylint

# 或使用 pyproject.toml
pip install -e ".[dev]"
```

## 🚀 快速开始

### 1. 本地检测

使用我们提供的脚本快速检测：

```bash
# 基本检测
./scripts/check-unused-code.sh

# 详细输出
./scripts/check-unused-code.sh --verbose

# 自动修复（仅安全修复）
./scripts/check-unused-code.sh --fix
```

### 2. 检测特定服务

#### Go 服务

```bash
# 检测单个服务
golangci-lint run --enable=unused,deadcode,unparam cmd/conversation-service/...

# 只检测 internal 目录
golangci-lint run --enable=unused cmd/conversation-service/internal/...
```

#### Python 服务

```bash
# 使用 Ruff
ruff check algo/rag-engine/ --select F401,F841,ARG

# 使用 Vulture
vulture algo/rag-engine/ --min-confidence 80
```

### 3. CI/CD 自动检测

项目已配置自动检测流程：

- **PR 检测**: 每次提交 PR 时自动运行
- **定期扫描**: 每周一早上 8 点自动扫描
- **手动触发**: 在 GitHub Actions 页面手动运行

查看结果：

1. 访问 GitHub Actions 页面
2. 查找 "Unused Code Detection" workflow
3. 下载 Artifacts 查看详细报告

## 📊 理解检测结果

### Go 代码示例

```bash
cmd/conversation-service/internal/biz/export_usecase.go:45:1:
  func `ExportConversation` is unused (unused)
```

**解读**:

- 文件: `cmd/conversation-service/internal/biz/export_usecase.go`
- 行号: 45
- 问题: 函数 `ExportConversation` 未被使用
- 检测器: `unused`

### Python 代码示例

```bash
algo/rag-engine/app/core/config.py:10:5: F841
  Local variable `unused_var` is assigned to but never used
```

**解读**:

- 文件: `algo/rag-engine/app/core/config.py`
- 行号: 10
- 错误码: F841 (未使用的变量)
- 问题: 局部变量被赋值但从未使用

## 🔍 常见误报情况

### 1. Wire 依赖注入

**问题**: 构造函数 `New*` 被标记为未使用

```go
// 实际上在 wire.go 中被使用
func NewUserService(repo UserRepo) *UserService {
    return &UserService{repo: repo}
}
```

**解决方案**:

- 检查 `wire.go` 文件
- 在 `.golangci.yml` 中排除 `wire.go`（已配置）

### 2. 反射调用

**问题**: HTTP/gRPC handler 被标记为未使用

```go
// 通过框架注册，使用反射调用
func (s *Service) HandleRequest(ctx context.Context, req *Request) error {
    // ...
}
```

**解决方案**:

- 确认是否在路由或服务注册中使用
- 如果确实被使用，添加注释说明
- 考虑添加显式调用或测试

### 3. 预留功能

**问题**: 为未来功能预留的函数

```go
// TODO(future): OAuth integration
func LoginWithGoogle(ctx context.Context) error {
    // 预留实现
}
```

**解决方案**:

- 添加 `// TODO(future): ...` 注释
- 在文档中说明预留功能
- 考虑是否真的需要预留

### 4. 测试辅助函数

**问题**: 测试文件中的辅助函数未被其他测试使用

**解决方案**:

- 在 `.golangci.yml` 中已排除 `*_test.go`
- 如果是公共测试工具，考虑移到 `testutil` 包

## ✅ 最佳实践

### 1. 定期检测

```bash
# 每周运行一次
./scripts/check-unused-code.sh

# 或设置 cron job
0 8 * * 1 cd /path/to/project && ./scripts/check-unused-code.sh
```

### 2. PR Review 检查清单

在代码审查时：

- [ ] 新增的公开函数是否被调用？
- [ ] 是否有未使用的参数？
- [ ] 是否有遗留的调试代码？
- [ ] 导入是否都被使用？

### 3. 清理流程

1. **确认**: 检查函数是否真的未使用
2. **沟通**: 与团队确认是否为预留功能
3. **文档**: 如果是预留功能，添加文档说明
4. **删除**: 确认后删除不需要的代码
5. **测试**: 运行测试确保没有破坏功能
6. **提交**: 创建 PR，说明删除原因

### 4. 避免误报

#### 在代码中标记预留功能

```go
// RESERVED: 为未来的 OAuth 集成预留
// Roadmap: Q2 2024
// Issue: #123
func LoginWithOAuth(provider string) error {
    panic("not implemented")
}
```

#### 在配置中排除特定文件

编辑 `.golangci.yml`:

```yaml
issues:
  exclude-rules:
    - path: internal/feature/reserved.go
      linters:
        - unused
```

## 📈 度量指标

### 跟踪代码质量

定期检查以下指标：

- **未使用代码总数**: 目标 < 50 个
- **未使用导出函数**: 目标 < 20 个
- **未使用参数**: 目标 < 30 个

### 生成趋势报告

```bash
# 生成详细分析报告
python3 scripts/analyze-unused-code.py comprehensive-report.md

# 查看历史趋势（需要保存历史数据）
ls -lt .reports/unused-summary-*.md | head -5
```

## 🔧 配置文件

### `.golangci.yml`

关键配置：

```yaml
linters:
  enable:
    - unused
    - deadcode
    - unparam

linters-settings:
  unused:
    check-exported: true # 检查导出的函数
```

### `pyproject.toml`

关键配置：

```toml
[tool.ruff.lint]
select = [
    "F401",  # unused imports
    "F841",  # unused variables
    "ARG",   # unused arguments
]
```

## 🐛 故障排除

### 问题: golangci-lint 运行很慢

**解决方案**:

```bash
# 使用缓存
golangci-lint cache clean

# 只分析变更的文件
golangci-lint run --new-from-rev=HEAD~1
```

### 问题: 检测到太多误报

**解决方案**:

1. 调整配置文件中的 `exclude-rules`
2. 使用 `nolint` 注释（谨慎使用）
3. 提高置信度阈值

```go
//nolint:unused // Wire 依赖注入使用
func NewService() *Service {
    return &Service{}
}
```

### 问题: CI 检测失败但本地正常

**解决方案**:

1. 确保本地和 CI 使用相同版本的工具
2. 检查配置文件是否已提交
3. 清理缓存后重试

## 📚 相关资源

- [golangci-lint 文档](https://golangci-lint.run/)
- [Ruff 文档](https://docs.astral.sh/ruff/)
- [Vulture 文档](https://github.com/jendrikseipp/vulture)
- [项目代码审查报告](../../CODE_REVIEW_UNUSED_FUNCTIONS.md)

## 🆘 获取帮助

遇到问题？

1. 查看 [GitHub Issues](https://github.com/your-org/your-repo/issues)
2. 联系团队技术负责人
3. 查阅项目 Wiki

---

**最后更新**: 2025-10-27
**维护者**: AI 客服平台团队
