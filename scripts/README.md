# 运维脚本

本目录包含 VoiceAssistant 项目的运维和部署脚本。

## 📜 脚本清单

### 部署脚本

#### `deploy-k8s.sh`

一键部署所有服务到 Kubernetes 集群。

**用法**:

```bash
# 完整部署
./deploy-k8s.sh

# 跳过 Istio 安装
./deploy-k8s.sh --skip-istio

# 跳过基础设施部署
./deploy-k8s.sh --skip-infra

# 仅验证部署状态
./deploy-k8s.sh --verify-only
```

**功能**:

- 检查依赖工具（kubectl, helm, istioctl）
- 安装 Istio 服务网格
- 部署基础设施服务
- 配置 Istio 路由和安全
- 部署应用服务
- 验证部署状态

---

### 监控脚本

#### `monitoring-dashboard.sh`

快速访问所有监控面板。

**用法**:

```bash
# 启动所有面板
./monitoring-dashboard.sh all

# 启动单个面板
./monitoring-dashboard.sh grafana
./monitoring-dashboard.sh kiali
./monitoring-dashboard.sh jaeger
./monitoring-dashboard.sh prometheus
./monitoring-dashboard.sh nacos

# 停止所有端口转发
./monitoring-dashboard.sh stop
```

**访问地址**:

- Grafana: http://localhost:3000
- Kiali: http://localhost:20001
- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Nacos: http://localhost:8848

---

### 备份恢复

#### `backup-restore.sh`

数据库和配置的备份恢复。

**用法**:

```bash
# 全量备份
./backup-restore.sh backup-all

# 备份单个服务
./backup-restore.sh backup-postgres
./backup-restore.sh backup-redis
./backup-restore.sh backup-nacos
./backup-restore.sh backup-k8s

# 恢复
./backup-restore.sh restore-postgres backups/postgres_20240127.sql.gz

# 列出备份
./backup-restore.sh list

# 清理旧备份（保留 30 天）
./backup-restore.sh cleanup 30
```

**备份内容**:

- PostgreSQL 数据库
- Redis 数据
- Nacos 配置
- Kubernetes 配置（ConfigMap, Secret, Deployment 等）

**备份目录**: `../backups/`

---

### 测试脚本

#### `test-services.sh`

测试所有服务的连通性和健康状态。

**用法**:

```bash
./test-services.sh
```

**检查项目**:

- 服务健康检查端点
- 数据库连接
- Redis 连接
- API 响应时间
- gRPC 服务状态

---

#### `test-auth.sh`

测试认证和授权功能。

**用法**:

```bash
./test-auth.sh
```

**测试场景**:

- 用户注册
- 用户登录
- Token 验证
- 权限检查

---

### 配置脚本

#### `nacos-setup.sh`

初始化 Nacos 配置中心。

**用法**:

```bash
./nacos-setup.sh
```

**功能**:

- 创建命名空间
- 导入配置文件
- 配置服务发现
- 验证配置

---

### 构建脚本

#### `build.sh`

构建所有服务的 Docker 镜像。

**用法**:

```bash
# 构建所有服务
./build.sh

# 构建单个服务
./build.sh identity-service
./build.sh agent-engine

# 指定版本
./build.sh --version 1.0.1
```

**镜像命名**: `ghcr.io/voiceassistant/<service>:<version>`

---

#### `proto-gen.sh`

生成 gRPC 代码。

**用法**:

```bash
./proto-gen.sh
```

**输出**:

- Go: `pkg/grpc/pb/`
- Python: `algo/common/grpc/pb/`

---

### 监控脚本

#### `start-monitoring.sh`

启动本地监控栈。

**用法**:

```bash
./start-monitoring.sh
```

启动服务:

- Prometheus
- Grafana
- Alertmanager

---

#### `stop-monitoring.sh`

停止本地监控栈。

**用法**:

```bash
./stop-monitoring.sh
```

---

### 优化脚本

#### `optimize-cursor.sh`

优化 Cursor AI 编辑器性能。

**用法**:

```bash
./optimize-cursor.sh
```

**优化内容**:

- 清理缓存
- 优化索引
- 配置忽略文件

---

#### `check-cursor-performance.sh`

检查 Cursor 性能指标。

**用法**:

```bash
./check-cursor-performance.sh
```

---

#### `clean-caches.sh`

清理项目缓存。

**用法**:

```bash
./clean-caches.sh
```

清理内容:

- Python `__pycache__`
- Go build cache
- Node `node_modules`
- Docker 未使用镜像

---

### 验证脚本

#### `verify-integration.sh`

验证服务集成。

**用法**:

```bash
./verify-integration.sh
```

**验证项目**:

- Nacos 连接
- 服务注册
- 配置加载
- 服务间通信

---

#### `verify-optimization.sh`

验证系统优化效果。

**用法**:

```bash
./verify-optimization.sh
```

---

#### `todo-scan.sh`

扫描代码中的 TODO 注释。

**用法**:

```bash
./todo-scan.sh
```

**输出**: 所有 TODO、FIXME、HACK 注释

---

### 代码质量脚本

#### `check-unused-code.sh`

检测未使用的代码（函数、变量、参数）。

**用法**:

```bash
# 基本检测
./check-unused-code.sh

# 详细输出
./check-unused-code.sh --verbose

# 自动修复（仅安全修复）
./check-unused-code.sh --fix
```

**检测内容**:

- Go: 未使用的函数、变量、参数、结构体字段
- Python: 未使用的导入、变量、参数、死代码

**输出**:

- 详细报告保存在 `.reports/` 目录
- 控制台显示摘要信息

**CI 集成**:

- PR 检测：每次 PR 自动运行
- 定期扫描：每周一自动扫描
- 查看 `.github/workflows/unused-code-check.yml`

**相关文档**: [未使用代码检测指南](../docs/code-quality/UNUSED_CODE_DETECTION.md)

---

#### `analyze-unused-code.py`

生成详细的未使用代码分析报告（Python 脚本）。

**用法**:

```bash
# 生成报告并打印到控制台
python3 ./analyze-unused-code.py

# 保存到文件
python3 ./analyze-unused-code.py unused-report.md
```

**功能**:

- 集成 golangci-lint 和 ruff/vulture
- 生成 Markdown 格式的详细报告
- 按文件和类别分组显示问题
- 提供清理建议

**依赖**:

```bash
# Go 工具
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Python 工具
pip install ruff vulture
```

---

## 🔧 脚本开发规范

### 通用约定

1. **Shebang**: 使用 `#!/usr/bin/env bash`
2. **错误处理**: `set -euo pipefail`
3. **日志函数**: 使用 `log_info`, `log_warn`, `log_error`
4. **颜色输出**: 使用 ANSI 颜色码
5. **帮助信息**: 提供 `--help` 选项

### 示例模板

```bash
#!/usr/bin/env bash
set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助
show_help() {
    cat << EOF
用法: $0 [选项]

选项:
    --help    显示帮助信息
EOF
}

# 主函数
main() {
    log_info "开始执行脚本..."
    # 实现逻辑
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

main "$@"
```

## 📚 相关文档

- [部署指南](../deployments/k8s/README.md)
- [运维手册](../docs/runbook/index.md)
- [架构概览](../docs/arch/overview.md)

## 🆘 获取帮助

如有问题，请联系:

- DevOps: devops@voiceassistant.com
- SRE: sre@voiceassistant.com
