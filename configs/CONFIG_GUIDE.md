# VoiceHelper 统一配置管理指南

> **更新日期**: 2025-11-01
> **版本**: v1.0

---

## 📋 配置文件总览

### 核心配置文件

| 文件 | 用途 | 适用服务 |
|------|------|----------|
| `services.yaml` | 服务端点统一配置（Go gRPC + Python HTTP） | 所有服务 |
| `services-client.yaml` | gRPC 客户端配置（重试、熔断、连接池） | Go 后端服务 |
| `services-integration.yaml` | 服务集成架构文档（调用关系、职责边界） | 架构参考 |
| `models.yaml` | 模型配置 | model-router |
| `observability.yaml` | 可观测性配置 | 所有服务 |
| `resilience.yaml` | 弹性配置 | 所有服务 |

### 服务专用配置

| 文件 | 服务 | 说明 |
|------|------|------|
| `ai-orchestrator.yaml` | AI 编排服务 | |
| `agent-engine.yaml` | Agent 引擎 | |
| `conversation-service.yaml` | 对话服务 | 增强版（包含JWT、限流、幂等性等） |
| `identity-service.yaml` | 认证服务 | |
| `model-router.yaml` | 模型路由 | |
| `analytics-service.yaml` | 分析服务 | |
| `notification-service.yaml` | 通知服务 | |
| `rag-engine.yaml` | RAG 引擎 | v2.0（支持多种检索策略） |

---

## 🎯 配置优先级

配置加载优先级（从高到低）：

1. **环境变量** (最高优先级)
2. **命令行参数**
3. **本地配置文件** (`configs/*.yaml`)
4. **Nacos/Consul** (生产环境)
5. **默认值** (代码中硬编码)

### 示例

```bash
# 1. 环境变量（优先级最高）
export MODEL_ADAPTER_URL=http://custom:8005
export RETRIEVAL_SERVICE_URL=http://custom:8012

# 2. 本地配置
# configs/algo-services.yaml

# 3. 运行时覆盖
./ai-orchestrator --model-adapter-url=http://override:8005
```

---

## 📐 标准配置格式

### 服务端点配置

```yaml
# configs/services.yaml
http_services:
  service-name:
    url: "http://localhost:PORT"      # 服务 URL
    timeout: 30s                       # 超时时间
    description: "服务描述"            # 说明
```

### 环境变量映射

```yaml
service-name:
  url: "http://localhost:8010"
  timeout: 60s
```

对应环境变量：
```bash
SERVICE_NAME_URL=http://localhost:8010
SERVICE_NAME_TIMEOUT=60s
```

---

## 🔧 超时配置标准

### 推荐超时值

| 服务类型 | 超时时间 | 原因 |
|---------|---------|------|
| 向量检索 | 10-30s | 快速查询 |
| 混合检索 + 重排 | 30s | 多步骤处理 |
| LLM 生成 | 60s | 长文本生成 |
| Agent 执行 | 60-120s | 多步骤推理 |
| 文档索引 | 300s | 大文件处理 |
| 模型调用 | 60s | 默认 LLM 超时 |

### 配置示例

```yaml
# configs/services.yaml
http_services:
  retrieval-service:
    url: "http://localhost:8012"
    timeout: 30s                    # 混合检索+重排
    description: "混合检索服务（Vector + BM25 + Rerank）"

  agent-engine:
    url: "http://localhost:8010"
    timeout: 60s                    # Agent 执行
    description: "智能Agent执行引擎"

  model-adapter:
    url: "http://localhost:8005"
    timeout: 60s                    # LLM 生成
    description: "统一LLM/Embedding调用入口"

  indexing-service:
    url: "http://localhost:8011"
    timeout: 300s                   # 文档索引
    description: "文档索引流水线"
```

---

## 🌐 多环境配置

### 开发环境（localhost）

```yaml
# configs/services.yaml
http_services:
  agent-engine:
    url: "http://localhost:8010"
    timeout: 60s
```

### Docker Compose 环境

```yaml
# configs/services.yaml (Docker 部分)
docker_services:
  http:
    agent-engine: "http://agent-engine:8010"
    retrieval-service: "http://retrieval-service:8012"
```

### Kubernetes 环境

```yaml
# configs/services.yaml (K8s 部分)
kubernetes_services:
  http:
    agent-engine: "http://agent-engine.voicehelper.svc.cluster.local:8010"
```

### 环境变量切换

```bash
# 设置环境
export DEPLOY_ENV=docker  # 或 kubernetes, local

# Go 服务自动选择配置
if [ "$DEPLOY_ENV" == "docker" ]; then
  export AGENT_ENGINE_URL=http://agent-engine:8010
else
  export AGENT_ENGINE_URL=http://localhost:8010
fi
```

---

## 🔍 配置验证

### 验证脚本

```bash
# 验证所有配置文件
./scripts/validate-config.sh

# 验证特定配置
./scripts/validate-config.sh configs/services.yaml
```

### Python 配置验证

```python
# scripts/validate_config.py
import yaml
from pathlib import Path

def validate_services_config(config_file: str):
    """验证服务配置"""
    with open(config_file) as f:
        config = yaml.safe_load(f)

    # 验证必需字段
    assert "http_services" in config, "Missing http_services"

    for service, settings in config["http_services"].items():
        assert "url" in settings, f"{service}: missing url"
        assert "timeout" in settings, f"{service}: missing timeout"

        # 验证 URL 格式
        url = settings["url"]
        assert url.startswith("http://") or url.startswith("https://"), \
            f"{service}: invalid URL format"

        # 验证端口唯一性
        # ...

    print("✅ Configuration valid")

if __name__ == "__main__":
    validate_services_config("configs/services.yaml")
```

---

## 📊 端口分配表

### 已分配端口

| 端口 | 服务 | 协议 | 状态 |
|------|------|------|------|
| 50051 | identity-service | gRPC | ✅ |
| 50052 | conversation-service | gRPC | ✅ |
| 50054 | ai-orchestrator | gRPC | ✅ |
| 50055 | model-router | gRPC | ✅ |
| 50056 | analytics-service | gRPC | ✅ |
| 50057 | notification-service | gRPC | ✅ |
| 8004 | voice-engine | HTTP | ✅ |
| 8005 | model-adapter | HTTP | ✅ |
| 8006 | knowledge-service | HTTP | ✅ |
| 8008 | multimodal-engine | HTTP | ✅ |
| 8009 | vector-store-adapter | HTTP | ✅ |
| 8010 | agent-engine | HTTP | ✅ |
| 8011 | indexing-service | HTTP | ✅ |
| 8012 | retrieval-service | HTTP | ✅ |

### 端口冲突检查

```bash
# 检查端口占用
for port in 8004 8005 8006 8008 8009 8010 8011 8012; do
  lsof -i :$port || echo "Port $port is free"
done
```

---

## 🔐 敏感配置管理

### 不应提交到代码库的配置

- ❌ API Keys (OpenAI, Anthropic, etc.)
- ❌ 数据库密码
- ❌ Redis 密码
- ❌ JWT Secret
- ❌ 加密密钥

### 使用环境变量

```bash
# .env.example (提交到代码库)
OPENAI_API_KEY=your-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/db

# .env (不提交，添加到 .gitignore)
OPENAI_API_KEY=sk-xxxxx
DATABASE_URL=postgresql://prod:xxxx@prod-db:5432/voicehelper
```

### 使用 Secret 管理

**Kubernetes Secrets**:
```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: voicehelper-secrets
type: Opaque
data:
  openai-api-key: <base64-encoded>
  database-url: <base64-encoded>
```

**Vault/AWS Secrets Manager**:
```bash
# 从 Vault 读取密钥
export OPENAI_API_KEY=$(vault kv get -field=api_key secret/voicehelper/openai)
```

---

## 🚀 配置最佳实践

### 1. 分层配置

```
configs/
├── base/              # 基础配置（所有环境通用）
│   ├── services.yaml
│   └── models.yaml
├── dev/               # 开发环境
│   └── overrides.yaml
├── staging/           # 预发环境
│   └── overrides.yaml
└── production/        # 生产环境
    └── overrides.yaml
```

### 2. 配置合并

```go
// pkg/config/loader.go
func LoadConfig(env string) (*Config, error) {
    // 1. 加载基础配置
    baseConfig, _ := loadYAML("configs/base/services.yaml")

    // 2. 加载环境配置
    envConfig, _ := loadYAML(fmt.Sprintf("configs/%s/overrides.yaml", env))

    // 3. 合并配置
    config := mergeConfig(baseConfig, envConfig)

    // 4. 环境变量覆盖
    config = applyEnvOverrides(config)

    return config, nil
}
```

### 3. 配置热更新

**使用 Nacos**:
```go
// pkg/config/nacos.go
func WatchConfig(namespace, dataID string, onChange func(*Config)) {
    client, _ := clients.NewNacosClient(...)

    client.ListenConfig(vo.ConfigParam{
        DataID: dataID,
        Group:  namespace,
        OnChange: func(data string) {
            config, _ := parseYAML(data)
            onChange(config)
        },
    })
}
```

### 4. 配置文档化

每个配置项都应该有注释：

```yaml
services:
  http:
    agent-engine:
      url: "http://localhost:8010"
      # 超时配置：Agent 执行可能需要较长时间
      # - 简单任务: 10-30s
      # - 复杂多步骤任务: 60-120s
      # 推荐值: 60s
      timeout: 60s

      # 服务描述
      description: "Agent执行引擎 - ReAct模式、工具调用、记忆管理"
```

---

## 🔄 配置迁移

### 从旧配置迁移

```bash
# 迁移脚本
./scripts/migrate-config.sh old-config.yaml new-config.yaml
```

### 配置版本管理

```yaml
# configs/services.yaml
version: "v1.0"  # 配置版本
last_updated: "2025-11-01"
schema_version: "2"

services:
  # ...
```

---

## 📞 故障排查

### 常见问题

**问题 1: 端口冲突**
```bash
# 症状: 服务启动失败
Error: bind: address already in use

# 解决
lsof -i :8010  # 查找占用端口的进程
kill -9 <PID>  # 杀死进程
```

**问题 2: 配置未生效**
```bash
# 检查配置加载顺序
export DEBUG_CONFIG=true
./service-name

# 输出应显示：
# Loaded config from: configs/services.yaml
# Env overrides: MODEL_ADAPTER_URL=http://custom:8005
```

**问题 3: 超时设置不合理**
```bash
# 症状: 请求频繁超时
Error: context deadline exceeded

# 解决: 根据服务特性调整超时
# 检索服务: 30s
# LLM调用: 60s
# Agent执行: 120s
```

---

## ✅ 配置检查清单

发布前检查：

- [ ] 所有端口配置一致
- [ ] 超时时间合理
- [ ] 没有硬编码的密钥
- [ ] 配置文件通过验证
- [ ] 环境变量已设置
- [ ] Docker/K8s 配置更新
- [ ] 文档已更新

---

## 📚 相关文档

- [服务交互审查报告](../docs/arch/service-interaction-review.md)
- [API 协议指南](../api/API-PROTOCOL-GUIDE.md)
- [部署指南](../docs/deployment/README.md)

---

**维护者**: VoiceHelper DevOps Team
**最后更新**: 2025-11-01
