# APISIX → Istio Gateway/Envoy 迁移指南

**版本**: v3.0
**最后更新**: 2025-10-28
**状态**: Ready for Production

## 📋 目录

1. [迁移概述](#迁移概述)
2. [前置条件](#前置条件)
3. [迁移流程](#迁移流程)
4. [配置映射](#配置映射)
5. [金丝雀切换](#金丝雀切换)
6. [监控指标](#监控指标)
7. [回滚方案](#回滚方案)
8. [故障排查](#故障排查)

---

## 迁移概述

### 迁移背景

从 APISIX 集中式网关迁移回 Istio Service Mesh 架构，获得以下优势:

| 维度 | APISIX | Istio + Envoy | 改进 |
|------|--------|---------------|------|
| **架构** | 集中式网关 | Sidecar模式 | 服务级流量控制 |
| **可观测性** | 网关层面 | 服务间全链路 | 完整调用链追踪 |
| **安全** | TLS + WAF | mTLS + RBAC | 服务间零信任 |
| **流量管理** | 路由规则 | VirtualService + DestinationRule | 更细粒度控制 |
| **生态** | 80+插件 | Envoy Filter + 社区生态 | 云原生标准 |
| **性能** | 优秀 | 好 | Sidecar有额外开销 |

### 迁移时间线

- **准备阶段**: 30分钟 - 1小时
- **金丝雀切换**: 4-6小时
- **稳定观察**: 2周
- **清理APISIX**: 1小时
- **总计**: 2周+ (包含观察期)

---

## 前置条件

### 环境要求

- **Kubernetes**: v1.26+
- **Istio**: v1.20.1+
- **kubectl**: v1.26+
- **istioctl**: v1.20.1+
- **Helm**: v3.12+ (可选)

### 资源要求

| 组件 | 副本数 | CPU (Request/Limit) | 内存 (Request/Limit) |
|------|--------|---------------------|----------------------|
| Istio Ingress Gateway | 3-10 (HPA) | 1000m / 2000m | 1Gi / 2Gi |
| Istiod (Control Plane) | 2-5 (HPA) | 500m / 1000m | 2Gi / 4Gi |
| Envoy Sidecar (per Pod) | - | 100m / 2000m | 128Mi / 1Gi |

**估算**:
- APISIX: 3 Gateway Pods × 512MB = 1.5GB
- Istio Gateway: 3 Pods × 1GB = 3GB
- Sidecars: 50 services × 2 replicas × 128MB = ~13GB
- **总计增加**: ~15GB 内存

### 权限要求

```bash
# 需要以下Kubernetes权限
- namespaces: create, get, list
- deployments: create, get, list, patch, delete
- services: create, get, list, patch
- configmaps: create, get, list, patch
- secrets: get, list
- customresourcedefinitions: create, get, list
- gateway.networking.istio.io: create, get, list, patch
- virtualservice.networking.istio.io: create, get, list, patch
```

---

## 迁移流程

### 阶段 1: 准备阶段 (30分钟)

#### 1.1 预检查

```bash
# 运行预检查脚本
./scripts/migrate-apisix-to-istio.sh preflight

# 检查项:
# ✓ kubectl, helm, istioctl 命令可用
# ✓ Kubernetes集群连接正常
# ✓ APISIX运行状态
# ✓ 命名空间存在性
# ✓ 资源配额充足
```

#### 1.2 安装Istio

```bash
# 安装Istio (生产配置)
./scripts/migrate-apisix-to-istio.sh install-istio

# 或手动安装:
istioctl install --set profile=production \
  --set values.gateways.istio-ingressgateway.autoscaleEnabled=true \
  --set values.gateways.istio-ingressgateway.autoscaleMin=3 \
  --set values.gateways.istio-ingressgateway.autoscaleMax=10 \
  -y

# 等待Istio组件就绪
kubectl wait --for=condition=ready pod -l app=istiod -n istio-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=istio-ingressgateway -n istio-system --timeout=300s
```

#### 1.3 部署Istio配置

```bash
# 应用所有Istio配置
./scripts/migrate-apisix-to-istio.sh apply

# 配置文件:
# - gateway.yaml: 入口网关
# - virtual-service.yaml: 路由规则
# - destination-rule.yaml: 流量策略
# - security.yaml: mTLS + 授权
# - telemetry.yaml: 可观测性
# - envoy-filter.yaml: 高级功能
```

#### 1.4 验证Istio健康状态

```bash
# 验证安装
./scripts/migrate-apisix-to-istio.sh verify

# 手动验证:
# 检查Gateway
kubectl get gateway -n istio-system
kubectl get gateway -n voiceassistant-prod

# 检查VirtualService
kubectl get virtualservice -n voiceassistant-prod

# 使用istioctl分析
istioctl analyze -n voiceassistant-prod

# 获取Gateway LoadBalancer IP
kubectl get svc istio-ingressgateway -n istio-system
```

---

### 阶段 2: 金丝雀流量切换 (4-6小时)

#### 2.1 流量切换策略

```bash
# 启动金丝雀切换
./scripts/migrate-apisix-to-istio.sh canary
```

**切换阶段**:

| 阶段 | Istio流量 | APISIX流量 | 观察时间 | 回滚条件 |
|------|-----------|------------|----------|----------|
| 1 | 10% | 90% | 30分钟 | 错误率 > 1% |
| 2 | 25% | 75% | 30分钟 | 错误率 > 1% |
| 3 | 50% | 50% | 1小时 | 错误率 > 0.5% |
| 4 | 75% | 25% | 1小时 | 错误率 > 0.5% |
| 5 | 100% | 0% | 持续监控 | 错误率 > 0.1% |

#### 2.2 DNS权重配置

**方式一: AWS Route53 加权路由**

```bash
# APISIX LoadBalancer
APISIX_LB=$(kubectl get svc apisix-gateway -n apisix -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Istio LoadBalancer
ISTIO_LB=$(kubectl get svc istio-ingressgateway -n istio-system -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# 使用AWS CLI更新Route53权重
# api.voiceassistant.com
aws route53 change-resource-record-sets --hosted-zone-id Z1234567890ABC --change-batch '{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "api.voiceassistant.com",
      "Type": "A",
      "SetIdentifier": "apisix",
      "Weight": 90,
      "AliasTarget": {
        "HostedZoneId": "Z215JYRZR1TBD5",
        "DNSName": "'$APISIX_LB'",
        "EvaluateTargetHealth": false
      }
    }
  }, {
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "api.voiceassistant.com",
      "Type": "A",
      "SetIdentifier": "istio",
      "Weight": 10,
      "AliasTarget": {
        "HostedZoneId": "Z215JYRZR1TBD5",
        "DNSName": "'$ISTIO_LB'",
        "EvaluateTargetHealth": false
      }
    }
  }]
}'
```

**方式二: CloudFlare Load Balancer**

在CloudFlare Dashboard中配置负载均衡池:
- Pool 1 (APISIX): Weight 90
- Pool 2 (Istio): Weight 10

#### 2.3 观察期监控

每个阶段观察以下指标:

```promql
# 1. 错误率 (目标: < 1%)
sum(rate(istio_requests_total{reporter="destination",response_code=~"5.."}[5m]))
/ sum(rate(istio_requests_total{reporter="destination"}[5m])) * 100

# 2. P95延迟 (目标: < 2000ms)
histogram_quantile(0.95,
  sum(rate(istio_request_duration_milliseconds_bucket{reporter="destination"}[5m])) by (le)
)

# 3. 请求速率
sum(rate(istio_requests_total{reporter="destination"}[1m]))

# 4. 可用性 (目标: > 99.9%)
sum(rate(istio_requests_total{reporter="destination",response_code!~"5.."}[5m]))
/ sum(rate(istio_requests_total{reporter="destination"}[5m])) * 100
```

**Grafana Dashboard**:
- Gateway流量对比
- 错误率趋势
- 延迟分布
- 连接数统计

---

### 阶段 3: 稳定运行 (2周+)

#### 3.1 持续监控

```bash
# 查看Gateway日志
kubectl logs -n istio-system -l app=istio-ingressgateway --tail=100 -f

# 查看Istiod日志
kubectl logs -n istio-system -l app=istiod --tail=100 -f

# 查看服务Sidecar日志
kubectl logs -n voiceassistant-prod <pod-name> -c istio-proxy --tail=100
```

#### 3.2 验证功能

**HTTP/REST API**:
```bash
curl -H "Host: api.voiceassistant.com" http://$ISTIO_LB/api/v1/auth/login -d '{"username":"test","password":"test"}'
```

**WebSocket**:
```bash
wscat -c ws://ws.voiceassistant.com/ws/voice/stream \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**gRPC**:
```bash
grpcurl -H "Authorization: Bearer $JWT_TOKEN" \
  grpc.voiceassistant.com:443 \
  identity.v1.Identity/GetUser
```

---

### 阶段 4: 清理APISIX (1小时)

确认Istio稳定运行 ≥ 2周后:

```bash
# 清理APISIX资源
./scripts/migrate-apisix-to-istio.sh cleanup

# 手动清理:
kubectl delete -f deployments/k8s/apisix/
kubectl delete namespace apisix
```

---

## 配置映射

### APISIX → Istio 功能映射表

| APISIX 功能 | Istio 对应 | 配置文件 |
|-------------|-----------|----------|
| APISIX Gateway | Istio Gateway | `gateway.yaml` |
| Route | VirtualService | `virtual-service.yaml` |
| Upstream | DestinationRule | `destination-rule.yaml` |
| Plugin: limit-req | EnvoyFilter (rate limit) | `envoy-filter.yaml` |
| Plugin: jwt-auth | RequestAuthentication | `security.yaml` |
| Plugin: cors | VirtualService.corsPolicy | `virtual-service.yaml` |
| Plugin: prometheus | Telemetry (metrics) | `telemetry.yaml` |
| Plugin: opentelemetry | Telemetry (tracing) | `telemetry.yaml` |
| Plugin: grpc-transcode | VirtualService (gRPC) | `virtual-service.yaml` |
| mTLS Upstream | PeerAuthentication | `security.yaml` |
| RBAC | AuthorizationPolicy | `security.yaml` |
| Health Check | DestinationRule.outlierDetection | `destination-rule.yaml` |

### 路由示例对比

**APISIX Route**:
```yaml
routes:
  - id: identity-service
    uri: /api/v1/auth/*
    upstream:
      nodes:
        identity-service:9000: 1
    plugins:
      limit-req:
        rate: 100
        burst: 50
      jwt-auth: {}
```

**Istio VirtualService + DestinationRule**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: identity-service
spec:
  hosts:
  - "api.voiceassistant.com"
  http:
  - match:
    - uri:
        prefix: "/api/v1/auth"
    route:
    - destination:
        host: identity-service
        port:
          number: 9000
    timeout: 10s
    retries:
      attempts: 3
---
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
spec:
  jwtRules:
  - issuer: "https://identity.voiceassistant.com"
```

---

## 监控指标

### Prometheus查询

```promql
# Gateway错误率
sum(rate(istio_requests_total{reporter="destination",destination_service_name=~"istio-ingressgateway.*",response_code=~"5.."}[5m]))
/ sum(rate(istio_requests_total{reporter="destination",destination_service_name=~"istio-ingressgateway.*"}[5m]))

# Service错误率 (按服务)
sum(rate(istio_requests_total{reporter="destination",response_code=~"5.."}[5m])) by (destination_service)
/ sum(rate(istio_requests_total{reporter="destination"}[5m])) by (destination_service)

# P50/P90/P95/P99延迟
histogram_quantile(0.50, sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le))
histogram_quantile(0.90, sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le))
histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le))
histogram_quantile(0.99, sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le))

# mTLS覆盖率
sum(istio_requests_total{connection_security_policy="mutual_tls"})
/ sum(istio_requests_total)

# Gateway吞吐量
sum(rate(istio_requests_total{reporter="destination",destination_service_name=~"istio-ingressgateway.*"}[1m]))
```

### Grafana Dashboard

导入Istio官方Dashboard:
- **Istio Mesh Dashboard**: Dashboard ID 7639
- **Istio Service Dashboard**: Dashboard ID 7636
- **Istio Workload Dashboard**: Dashboard ID 7630
- **Istio Performance Dashboard**: Dashboard ID 11829

---

## 回滚方案

### 立即回滚 (5分钟内)

```bash
# 方式一: 使用脚本
./scripts/migrate-apisix-to-istio.sh rollback

# 方式二: 手动DNS切换
# 1. 更新DNS将100%流量切回APISIX
# 2. 保留Istio环境用于排查

# 查看APISIX LoadBalancer
kubectl get svc apisix-gateway -n apisix
```

### 回滚检查清单

- [ ] DNS已切回100% APISIX
- [ ] 确认流量恢复正常
- [ ] 收集Istio错误日志
- [ ] 分析问题根因
- [ ] 修复配置后重试

---

## 故障排查

### 常见问题

#### 1. Gateway无法访问

**症状**: `curl: (7) Failed to connect to gateway`

**排查**:
```bash
# 检查Gateway Pod状态
kubectl get pods -n istio-system -l app=istio-ingressgateway

# 查看日志
kubectl logs -n istio-system -l app=istio-ingressgateway --tail=100

# 检查Service
kubectl get svc istio-ingressgateway -n istio-system

# 检查Gateway配置
kubectl get gateway -A
istioctl analyze -n istio-system
```

#### 2. VirtualService路由不生效

**症状**: 404 Not Found

**排查**:
```bash
# 检查VirtualService
kubectl get virtualservice -n voiceassistant-prod

# 查看详细信息
kubectl describe virtualservice api-gateway -n voiceassistant-prod

# 使用istioctl验证
istioctl analyze -n voiceassistant-prod

# 查看Pilot配置分发
istioctl proxy-config route <ingress-gateway-pod> -n istio-system
```

#### 3. mTLS连接失败

**症状**: `503 Service Unavailable`, `upstream connect error`

**排查**:
```bash
# 检查PeerAuthentication
kubectl get peerauthentication -A

# 检查DestinationRule
kubectl get destinationrule -n voiceassistant-prod

# 查看证书
istioctl proxy-config secret <pod-name> -n voiceassistant-prod

# 检查mTLS状态
istioctl authn tls-check <pod-name>.<namespace> <service>.<namespace>.svc.cluster.local
```

#### 4. 高延迟

**症状**: P95 > 2s

**排查**:
```bash
# 查看Envoy统计
kubectl exec -n voiceassistant-prod <pod-name> -c istio-proxy -- \
  curl localhost:15000/stats/prometheus | grep istio_request_duration

# 查看upstream连接池
istioctl proxy-config cluster <pod-name> -n voiceassistant-prod

# 检查DestinationRule连接池配置
kubectl get destinationrule -n voiceassistant-prod -o yaml | grep -A 10 connectionPool
```

#### 5. 限流不生效

**症状**: 未触发429 Too Many Requests

**排查**:
```bash
# 检查EnvoyFilter
kubectl get envoyfilter -n istio-system

# 查看Envoy配置
istioctl proxy-config listener <gateway-pod> -n istio-system -o json | grep -A 20 rate_limit

# 检查Redis连接
kubectl exec -n istio-system <gateway-pod> -- \
  curl localhost:15000/clusters | grep rate_limit
```

---

## 附录

### 参考文档

- [Istio官方文档](https://istio.io/latest/docs/)
- [Envoy Proxy文档](https://www.envoyproxy.io/docs/envoy/latest/)
- [Istio性能与可扩展性](https://istio.io/latest/docs/ops/deployment/performance-and-scalability/)
- [Istio最佳实践](https://istio.io/latest/docs/ops/best-practices/)

### 联系支持

- **Slack**: #istio-migration
- **Wiki**: https://wiki.voiceassistant.com/istio
- **Grafana**: https://grafana.voiceassistant.com/d/istio-gateway
- **Prometheus**: https://prometheus.voiceassistant.com
