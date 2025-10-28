# 配置管理 - Nacos 集成指南

## 概述

所有服务支持两种配置模式：

- **本地配置模式** (`CONFIG_MODE=local`)：从本地 YAML 文件读取配置
- **Nacos 配置中心模式** (`CONFIG_MODE=nacos`)：从 Nacos 配置中心读取配置

## 快速开始

### 1. 本地配置模式（默认）

```bash
# Go 服务示例
cd cmd/conversation-service
export CONFIG_MODE=local
export CONFIG_PATH=./configs/conversation-service.yaml
./conversation-service

# Python 服务示例
cd algo/agent-engine
export CONFIG_MODE=local
export CONFIG_PATH=./configs/agent-engine.yaml
python main_with_nacos.py
```

### 2. Nacos 配置中心模式

#### 步骤 1：启动 Nacos

```bash
# 使用 Docker
docker run -d \
  --name nacos \
  -p 8848:8848 \
  -e MODE=standalone \
  nacos/nacos-server:v2.3.0

# 访问控制台: http://localhost:8848/nacos
# 账号/密码: nacos/nacos
```

#### 步骤 2：在 Nacos 中创建配置

1. 登录 Nacos 控制台
2. 进入"配置管理" -> "配置列表"
3. 点击"+"创建配置：
   - **Data ID**: `conversation-service.yaml` 或 `agent-engine.yaml`
   - **Group**: `VoiceHelper`
   - **配置格式**: `YAML`
   - **配置内容**: 复制 `configs/*.yaml` 的内容（去掉 nacos 配置块）

#### 步骤 3：启动服务

```bash
# Go 服务
export CONFIG_MODE=nacos
export CONFIG_PATH=./configs/conversation-service.yaml  # Nacos 连接配置
export NACOS_SERVER_ADDR=localhost
export NACOS_SERVER_PORT=8848
export NACOS_GROUP=VoiceHelper
export NACOS_DATA_ID=conversation-service.yaml
./conversation-service

# Python 服务
export CONFIG_MODE=nacos
export CONFIG_PATH=./configs/agent-engine.yaml
export NACOS_SERVER_ADDR=localhost
python main_with_nacos.py
```

## 环境变量

### 通用环境变量

| 变量名        | 说明                         | 默认值   |
| ------------- | ---------------------------- | -------- |
| `CONFIG_MODE` | 配置模式：`local` 或 `nacos` | `local`  |
| `CONFIG_PATH` | 配置文件路径                 | 服务特定 |

### Nacos 环境变量

| 变量名              | 说明             | 默认值          |
| ------------------- | ---------------- | --------------- |
| `NACOS_SERVER_ADDR` | Nacos 服务器地址 | `localhost`     |
| `NACOS_SERVER_PORT` | Nacos 服务器端口 | `8848`          |
| `NACOS_NAMESPACE`   | 命名空间 ID      | `""` (public)   |
| `NACOS_GROUP`       | 配置分组         | `DEFAULT_GROUP` |
| `NACOS_DATA_ID`     | 配置 DataID      | `{服务名}.yaml` |
| `NACOS_USERNAME`    | 认证用户名       | `""`            |
| `NACOS_PASSWORD`    | 认证密码         | `""`            |

## 多环境配置

### 方案 1：使用 Nacos Namespace（推荐）

```bash
# 开发环境
export NACOS_NAMESPACE=dev
export NACOS_GROUP=VoiceHelper

# 测试环境
export NACOS_NAMESPACE=test
export NACOS_GROUP=VoiceHelper

# 生产环境
export NACOS_NAMESPACE=prod
export NACOS_GROUP=VoiceHelper
```

### 方案 2：使用不同的 Group

```bash
# 开发环境
export NACOS_GROUP=VoiceHelper-Dev

# 生产环境
export NACOS_GROUP=VoiceHelper-Prod
```

## Docker 部署

```bash
# 本地配置模式
docker-compose -f deployments/docker/docker-compose.nacos.yml --profile local up -d

# Nacos 配置中心模式
docker-compose -f deployments/docker/docker-compose.nacos.yml --profile nacos up -d
```

## Kubernetes 部署

```bash
# 创建命名空间
kubectl create namespace voice-assistant

# 应用配置
kubectl apply -f deployments/k8s/nacos-config.yaml

# 查看服务状态
kubectl get pods -n voice-assistant

# 切换配置模式
kubectl patch configmap nacos-config -n voice-assistant \
  -p '{"data":{"CONFIG_MODE":"local"}}'
kubectl rollout restart deployment/conversation-service -n voice-assistant
```

## 配置热更新

Nacos 模式下，配置变更会自动推送到服务：

```bash
# 在 Nacos 控制台修改配置后，服务会自动重新加载
# 日志中会显示：
# 🔄 Config changed: VoiceHelper/conversation-service.yaml
# ✅ Config reloaded successfully
```

## 故障排查

### 1. 无法连接 Nacos

```bash
# 检查 Nacos 是否运行
curl http://localhost:8848/nacos/

# 检查网络连接
telnet localhost 8848
```

### 2. 配置未找到

```bash
# 验证配置是否存在
curl "http://localhost:8848/nacos/v1/cs/configs?dataId=conversation-service.yaml&group=VoiceHelper"

# 检查环境变量
env | grep NACOS
```

### 3. 回退到本地配置

```bash
# 设置环境变量即可切换
export CONFIG_MODE=local
# 重启服务
```

## 最佳实践

1. **本地开发使用本地配置**，生产环境使用 Nacos
2. **敏感信息**（密码、密钥）通过环境变量传递，不要放在配置文件中
3. **使用 Namespace** 隔离不同环境的配置
4. **定期备份** Nacos 配置到 Git（通过 Nacos Open API）
5. **配置变更记录**：Nacos 自动保存配置历史
6. **灰度发布**：先在一个实例上测试新配置，确认无误后推送到其他实例

## 配置文件结构

### 服务配置文件

所有服务配置文件都应包含 `nacos` 配置块：

```yaml
# Nacos 配置中心连接配置
nacos:
  server_addr: 'localhost'
  server_port: 8848
  namespace: ''
  group: 'VoiceHelper'
  data_id: 'service-name.yaml'
  username: ''
  password: ''

# 服务实际配置
service:
  name: 'service-name'
  # ...
```

### 统一基础配置文件

为了消除跨语言（Python/Go）的功能重复，新增以下统一配置文件：

#### 1. `resilience.yaml` - 弹性机制配置

包含熔断器、重试、超时、限流等统一配置：

```yaml
circuit_breaker:
  default:
    failure_threshold: 5
    recovery_timeout: 60
    max_requests: 3
    success_threshold: 2

retry:
  default:
    max_attempts: 3
    initial_delay: 100
    max_delay: 10
    backoff_multiplier: 2.0
```

**使用方式：**
- Python: `from algo.common.config import load_config`
- Go: `import "voice-assistant/pkg/config"`
- Nacos DataID: `resilience.yaml`
- Nacos Group: `VoiceHelper-Common`

#### 2. `observability.yaml` - 可观测性配置

包含OpenTelemetry追踪、Prometheus指标、日志等统一配置：

```yaml
tracing:
  enabled: true
  service:
    name: "service-name"  # 各服务需覆盖
    version: "1.0.0"
    environment: "development"
  exporter:
    endpoint: "localhost:4317"
    insecure: true
  sampling:
    rate: 1.0  # 生产环境建议0.1-0.5
```

**使用方式：**
- Python: `from algo.common.telemetry import init_tracing, TracingConfig`
- Go: `import "voice-assistant/pkg/observability"`
- Nacos DataID: `observability.yaml`
- Nacos Group: `VoiceHelper-Common`

### Nacos 配置组织结构

```
命名空间: public (或 dev/staging/prod)
├── Group: VoiceHelper (服务配置)
│   ├── conversation-service.yaml
│   ├── agent-engine.yaml
│   ├── model-router.yaml
│   └── ...
└── Group: VoiceHelper-Common (公共配置)
    ├── resilience.yaml
    ├── observability.yaml
    └── services-integration.yaml
```

## Go 服务集成

```go
import "github.com/VoiceHelper/pkg/config"

// 创建配置管理器
cfgManager := config.NewManager()
err := cfgManager.LoadConfig("./configs/service.yaml", "service-name")
defer cfgManager.Close()

// 读取配置
port := cfgManager.GetString("server.port")
```

## Python 服务集成

```python
from nacos_config import init_config, get_config

# 初始化配置
config_data = init_config("./configs/service.yaml", "service-name")

# 读取配置
port = get_config("service.port", 8080)
```

## 相关文件

- `configs/nacos.yaml` - Nacos 连接配置模板
- `pkg/config/config.go` - Go 服务配置管理器
- `algo/common/nacos_config.py` - Python 服务配置管理器
- `deployments/docker/docker-compose.nacos.yml` - Docker 部署配置
- `deployments/k8s/nacos-config.yaml` - Kubernetes 部署配置
