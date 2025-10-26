# Model Router Service

模型路由服务 - 智能模型选择、负载均衡、成本优化

## 功能特性

### 1. 智能路由

- 根据请求类型自动选择最优模型
- 成本优先 / 性能优先 / 平衡模式
- 自定义路由规则

### 2. 负载均衡

- Round Robin
- Weighted Round Robin
- Least Connections
- 基于响应时间的动态负载均衡

### 3. 降级策略

- 自动降级到备用模型
- 熔断机制
- 重试策略

### 4. 成本优化

- 实时成本追踪
- Token 消耗统计
- 预算告警

### 5. 健康检查

- 模型可用性检测
- 自动剔除不健康节点
- 自动恢复机制

## API 接口

### POST /api/v1/route

路由请求到最优模型

**请求**:

```json
{
  "prompt": "用户输入",
  "mode": "balanced", // cost/performance/balanced
  "max_tokens": 2000,
  "temperature": 0.7
}
```

**响应**:

```json
{
  "model": "gpt-4-turbo-preview",
  "provider": "openai",
  "endpoint": "https://api.openai.com/v1/chat/completions",
  "estimated_cost": 0.06
}
```

### GET /api/v1/models

列出所有可用模型

### GET /api/v1/models/:name/health

检查模型健康状态

### GET /api/v1/load

获取负载统计

### GET /api/v1/cost

获取成本统计

## 配置

```yaml
models:
  - name: gpt-4-turbo-preview
    provider: openai
    endpoint: https://api.openai.com/v1/chat/completions
    cost_per_1k_tokens: 0.03
    weight: 1.0
    max_concurrent: 100

  - name: gpt-3.5-turbo
    provider: openai
    endpoint: https://api.openai.com/v1/chat/completions
    cost_per_1k_tokens: 0.002
    weight: 2.0
    max_concurrent: 200

routing:
  strategy: balanced
  fallback_enabled: true
  retry_times: 3
  circuit_breaker:
    threshold: 50%
    timeout: 60s
```

## 部署

### Docker

```bash
docker build -t model-router:latest .
docker run -p 9004:9004 model-router:latest
```

### Kubernetes

```bash
kubectl apply -f deployments/k8s/model-router.yaml
```

## 监控

Prometheus 指标暴露在 `/metrics`：

- `model_router_requests_total` - 总请求数
- `model_router_request_duration_seconds` - 请求延迟
- `model_router_model_health` - 模型健康状态
- `model_router_cost_dollars_total` - 总成本

## 开发

### 编译

```bash
go build -o model-router ./cmd/model-router
```

### 运行

```bash
./model-router
```

### 测试

```bash
go test ./...
```
