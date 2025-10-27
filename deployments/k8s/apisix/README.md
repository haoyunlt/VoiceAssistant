# APISIX Gateway 部署文档

## 概述

本目录包含从 Istio/Envoy 迁移到 APISIX 网关的完整配置文件。

## 文件说明

```
apisix/
├── deployment.yaml      # APISIX 核心部署（Deployment, Service, ConfigMap, RBAC, HPA）
├── routes.yaml          # 路由和上游配置（对应 Istio VirtualService + DestinationRule）
├── security.yaml        # 安全策略（mTLS, JWT, RBAC, WAF, PII脱敏）
├── observability.yaml   # 可观测性（OpenTelemetry, Prometheus, Grafana）
└── README.md           # 本文档
```

## 架构对比

### Istio/Envoy 架构
```
外部流量 → Istio Ingress Gateway (Envoy) → Service Mesh (Envoy Sidecar) → 后端服务
```

### APISIX 架构
```
外部流量 → APISIX Gateway → 后端服务（无 Sidecar）
```

## 功能对等映射

| Istio 组件 | APISIX 对应 | 说明 |
|-----------|------------|------|
| Gateway | APISIX Deployment + SSL | 入口网关 |
| VirtualService | APISIX Routes | 路由规则 |
| DestinationRule | APISIX Upstreams | 负载均衡、连接池、健康检查 |
| PeerAuthentication | mTLS Upstreams | 服务间 mTLS |
| AuthorizationPolicy | RBAC Plugin | 访问控制 |
| RequestAuthentication | JWT Plugin | JWT 认证 |
| Telemetry | OpenTelemetry + Prometheus | 可观测性 |
| EnvoyFilter | Custom Plugins | 自定义逻辑 |

## 部署步骤

### 前置条件

1. **Kubernetes 集群**: 1.23+
2. **etcd**: APISIX 使用 etcd 作为配置中心
3. **证书**: TLS 证书（存储在 Secret）
4. **监控**: Prometheus + Grafana（可选）

### 快速部署

```bash
# 1. 查看迁移计划
./scripts/migrate-istio-to-apisix.sh plan

# 2. 执行迁移（包含备份、部署、验证）
./scripts/migrate-istio-to-apisix.sh apply

# 3. 验证部署
./scripts/migrate-istio-to-apisix.sh verify

# 4. 金丝雀发布（逐步切换流量）
./scripts/migrate-istio-to-apisix.sh canary

# 5. 清理 Istio（可选，建议稳定运行一周后）
./scripts/migrate-istio-to-apisix.sh cleanup
```

### 手动部署

如果需要更精细的控制，可以手动执行：

```bash
# 1. 创建 namespace
kubectl create namespace apisix

# 2. 创建 Secrets（替换为实际值）
kubectl create secret generic apisix-secrets \
  --from-literal=admin-key='your-admin-key' \
  --from-literal=jwt-secret='your-jwt-secret' \
  -n apisix

# 3. 部署 APISIX 核心
kubectl apply -f deployments/k8s/apisix/deployment.yaml

# 4. 等待 Pods 就绪
kubectl wait --for=condition=ready pod -l app=apisix -n apisix --timeout=300s

# 5. 配置路由和上游
kubectl apply -f deployments/k8s/apisix/routes.yaml

# 6. 配置安全策略
kubectl apply -f deployments/k8s/apisix/security.yaml

# 7. 配置可观测性
kubectl apply -f deployments/k8s/apisix/observability.yaml

# 8. 验证部署
kubectl get pods,svc -n apisix
kubectl logs -n apisix -l app=apisix --tail=50
```

## 流量切换策略

### 方案 1: DNS 切换（推荐）

```bash
# 1. 降低 DNS TTL（切换前 24 小时）
# api.voiceassistant.com TTL: 300 → 60

# 2. 获取 APISIX LoadBalancer 地址
kubectl get svc apisix-gateway -n apisix

# 3. 更新 DNS A/CNAME 记录
# api.voiceassistant.com → <APISIX-LB-IP>
# ws.voiceassistant.com → <APISIX-LB-IP>
# grpc.voiceassistant.com → <APISIX-LB-IP>

# 4. 监控指标，确认无异常

# 5. DNS 缓存过期后，流量自然切换到 APISIX
```

### 方案 2: 金丝雀发布（使用 Istio 权重路由）

```bash
# 使用迁移脚本的金丝雀功能
./scripts/migrate-istio-to-apisix.sh canary

# 或手动调整权重
# 10% → 25% → 50% → 75% → 100%
```

### 方案 3: 蓝绿部署

```bash
# 1. APISIX 作为绿色环境部署
# 2. 内部测试验证
# 3. 一次性切换全部流量
# 4. 保留 Istio 作为蓝色环境备用
```

## 验证清单

### 功能验证

```bash
# 1. 健康检查
curl -i http://<APISIX-LB>/health

# 2. API 路由测试
curl -i -H "Authorization: Bearer <JWT>" \
  https://api.voiceassistant.com/api/v1/conversations

# 3. WebSocket 测试
wscat -c wss://ws.voiceassistant.com/ws/voice \
  -H "Authorization: Bearer <JWT>"

# 4. gRPC 测试
grpcurl -H "Authorization: Bearer <JWT>" \
  grpc.voiceassistant.com:443 \
  identity.IdentityService/GetUser
```

### 性能验证

```bash
# 1. 压力测试
cd tests/load
k6 run --vus 100 --duration 5m api-gateway.js

# 2. 查看 Prometheus 指标
kubectl port-forward -n apisix svc/apisix-admin 9091:9091
curl http://localhost:9091/apisix/prometheus/metrics

# 3. 查看 Grafana Dashboard
# 导入 observability.yaml 中的 Dashboard
```

### 安全验证

```bash
# 1. JWT 认证
curl -i https://api.voiceassistant.com/api/v1/ai/chat  # 应返回 401

# 2. 限流测试
for i in {1..200}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer <JWT>" \
    https://api.voiceassistant.com/api/v1/ai/chat
done
# 应有部分请求返回 429

# 3. CORS 测试
curl -i -X OPTIONS \
  -H "Origin: https://app.voiceassistant.com" \
  -H "Access-Control-Request-Method: POST" \
  https://api.voiceassistant.com/api/v1/conversations

# 4. mTLS 验证（内部服务）
# 应使用客户端证书成功连接
```

## 监控指标

### 关键 SLI

```promql
# 1. 可用性
sum(rate(apisix_http_requests_total[5m])) - sum(rate(apisix_http_requests_total{status=~"5.."}[5m]))
/ sum(rate(apisix_http_requests_total[5m])) * 100

# 2. P95 延迟
histogram_quantile(0.95,
  sum(rate(apisix_http_request_duration_seconds_bucket[5m])) by (le, route)
)

# 3. 错误率
sum(rate(apisix_http_requests_total{status=~"5.."}[5m]))
/ sum(rate(apisix_http_requests_total[5m])) * 100

# 4. QPS
sum(rate(apisix_http_requests_total[1m]))
```

### SLO 目标

| 指标 | 目标 | 告警阈值 |
|------|------|---------|
| 可用性 | ≥ 99.9% | < 99% |
| P95 延迟 (API Gateway) | < 200ms | > 500ms |
| P95 延迟 (端到端) | < 2.5s | > 5s |
| 错误率 | < 0.1% | > 1% |
| QPS 基线 | ≥ 1000 | N/A |

## 回滚方案

### 触发条件

1. 关键指标超出告警阈值
2. 出现 P0/P1 故障
3. 业务方明确要求回滚

### 回滚步骤

```bash
# 自动回滚（使用脚本）
./scripts/migrate-istio-to-apisix.sh rollback

# 或手动回滚
# 1. 恢复 DNS 指向 Istio Gateway
# 2. 验证 Istio 工作正常
# 3. 保留 APISIX 用于问题排查
kubectl get svc istio-ingressgateway -n istio-system

# 4. 调查 APISIX 问题
kubectl logs -n apisix -l app=apisix --tail=1000

# 5. 修复后重新发布
```

### RTO/RPO

- **RTO (恢复时间目标)**: < 5 分钟
- **RPO (数据丢失目标)**: 0（无状态网关）

## 故障排查

### APISIX Pods 无法启动

```bash
# 1. 查看 Pod 状态
kubectl describe pod -n apisix -l app=apisix

# 2. 查看日志
kubectl logs -n apisix -l app=apisix --tail=100

# 常见问题:
# - etcd 连接失败: 检查 etcd Service 是否可达
# - ConfigMap 格式错误: 检查 YAML 格式
# - Secret 不存在: 创建必需的 Secrets
```

### 路由不工作

```bash
# 1. 检查路由配置
kubectl exec -n apisix <apisix-pod> -- \
  curl http://127.0.0.1:9180/apisix/admin/routes \
  -H "X-API-KEY: <admin-key>"

# 2. 检查上游健康状态
kubectl exec -n apisix <apisix-pod> -- \
  curl http://127.0.0.1:9180/apisix/admin/upstreams \
  -H "X-API-KEY: <admin-key>"

# 3. 检查后端服务
kubectl get svc -n voiceassistant-prod
```

### 性能问题

```bash
# 1. 检查资源使用
kubectl top pods -n apisix

# 2. 检查 HPA 状态
kubectl get hpa -n apisix

# 3. 查看 Prometheus 指标
# - 连接数
# - 请求队列
# - upstream 延迟

# 4. 调整配置
# - 增加副本数
# - 调整 worker_processes
# - 调整连接池大小
```

### 认证失败

```bash
# 1. 验证 JWT Secret
kubectl get secret apisix-secrets -n apisix -o yaml

# 2. 检查 JWT 插件配置
kubectl get configmap apisix-security-plugins -n apisix -o yaml

# 3. 测试 JWT 生成
# 使用在线 JWT 调试工具验证 token
```

## 最佳实践

### 1. 安全

- ✅ 使用强密钥（admin-key, jwt-secret）
- ✅ 启用 mTLS 加密服务间通信
- ✅ 配置 WAF 规则防护常见攻击
- ✅ 实施 PII 数据脱敏
- ✅ 定期更新证书和密钥
- ✅ 使用 RBAC 限制 Admin API 访问

### 2. 性能

- ✅ 根据流量调整副本数（HPA）
- ✅ 配置合理的连接池大小
- ✅ 启用 keepalive 长连接
- ✅ 使用 Redis 集群作为限流存储
- ✅ 调整 Nginx worker 参数

### 3. 可靠性

- ✅ 配置健康检查（主动 + 被动）
- ✅ 设置合理的超时和重试策略
- ✅ 使用 PodDisruptionBudget 保证最小副本
- ✅ 多可用区部署（Pod Anti-Affinity）
- ✅ 定期备份 etcd 配置

### 4. 可观测性

- ✅ 接入 OpenTelemetry 全链路追踪
- ✅ 配置 Prometheus 监控和告警
- ✅ 导入 Grafana Dashboard
- ✅ 启用访问日志（Kafka/SLS）
- ✅ 设置合理的 SLO 和告警阈值

## 成本优化

### 资源使用对比

| 组件 | Istio | APISIX | 节省 |
|------|-------|--------|-----|
| 控制平面 | 3 个 Pods (istiod) | 无 | -3 Pods |
| 数据平面 | 每个 Pod 1 Sidecar | 共享 Gateway | ~70% |
| 内存 | ~150MB/Sidecar | ~512MB/Gateway | 取决于 Pod 数量 |

**示例**: 100 个微服务 Pods
- Istio: 100 Sidecars × 150MB = 15GB
- APISIX: 3 Gateway Pods × 512MB = 1.5GB
- **节省**: ~90% 内存

## 参考资料

- [APISIX 官方文档](https://apisix.apache.org/docs/apisix/getting-started/)
- [APISIX Kubernetes 部署](https://apisix.apache.org/docs/ingress-controller/getting-started/)
- [从 Istio 迁移到 APISIX](https://apisix.apache.org/blog/2022/07/08/istio-to-apisix/)
- [APISIX 插件中心](https://apisix.apache.org/docs/apisix/plugins/limit-req/)

## 支持

如有问题，请联系:
- Platform Team: platform@voiceassistant.com
- Slack: #apisix-migration
- Wiki: https://wiki.voiceassistant.com/apisix
