# Istio Gateway/Envoy 配置

**版本**: v3.0
**Istio版本**: 1.20.1+
**最后更新**: 2025-10-28

## 📁 目录结构

```
istio/
├── README.md                    # 本文件
├── MIGRATION_GUIDE.md           # 完整迁移指南
├── gateway.yaml                 # Gateway配置（HTTP/HTTPS/gRPC/WebSocket）
├── virtual-service.yaml         # VirtualService路由规则（15+ 服务）
├── destination-rule.yaml        # DestinationRule流量策略（15+ 服务）
├── security.yaml                # 安全配置（mTLS/JWT/AuthorizationPolicy）
├── telemetry.yaml               # 可观测性配置（Tracing/Metrics/Logging）
├── envoy-filter.yaml            # EnvoyFilter高级功能（限流/压缩/日志）
├── namespace.yaml               # 命名空间配置
├── traffic-management.yaml      # 流量管理（A/B测试/金丝雀）
└── ...
```

## 🚀 快速开始

### 前置条件

- Kubernetes v1.26+
- kubectl v1.26+
- istioctl v1.20.1+
- Helm v3.12+ (可选)

### 安装步骤

#### 1. 安装Istio

```bash
# 使用迁移脚本（推荐）
./scripts/migrate-apisix-to-istio.sh install-istio

# 或手动安装
istioctl install --set profile=production -y

# 等待Istio就绪
kubectl wait --for=condition=ready pod -l app=istiod -n istio-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=istio-ingressgateway -n istio-system --timeout=300s
```

#### 2. 启用Sidecar自动注入

```bash
# 标记应用命名空间
kubectl label namespace voiceassistant-prod istio-injection=enabled --overwrite

# 验证标签
kubectl get namespace voiceassistant-prod --show-labels
```

#### 3. 部署配置

```bash
# 使用脚本部署所有配置
./scripts/migrate-apisix-to-istio.sh apply

# 或手动部署
kubectl apply -f deployments/k8s/istio/namespace.yaml
kubectl apply -f deployments/k8s/istio/gateway.yaml
kubectl apply -f deployments/k8s/istio/virtual-service.yaml
kubectl apply -f deployments/k8s/istio/destination-rule.yaml
kubectl apply -f deployments/k8s/istio/security.yaml
kubectl apply -f deployments/k8s/istio/telemetry.yaml
kubectl apply -f deployments/k8s/istio/envoy-filter.yaml
```

#### 4. 验证安装

```bash
# 使用脚本验证
./scripts/migrate-apisix-to-istio.sh verify

# 或手动验证
kubectl get gateway,virtualservice,destinationrule -n voiceassistant-prod
istioctl analyze -n voiceassistant-prod

# 查看Gateway LoadBalancer
kubectl get svc istio-ingressgateway -n istio-system
```

---

## 📝 配置文件说明

### gateway.yaml

定义外部流量入口点。

**特性**:
- HTTP/HTTPS/gRPC/WebSocket 支持
- TLS 1.2/1.3 配置
- 多域名支持（api/ws/grpc.voiceassistant.com）
- mTLS 服务间通信

**示例**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: voiceassistant-gateway
  namespace: istio-system
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    hosts:
    - "api.voiceassistant.com"
    tls:
      mode: SIMPLE
      credentialName: voiceassistant-tls-cert
```

### virtual-service.yaml

定义路由规则。

**特性**:
- 15+ 服务路由配置
- HTTP/gRPC/WebSocket 路由
- 超时和重试策略
- CORS 配置
- 基于 URI/Header 匹配

**主要路由**:
- `/api/v1/auth` → Identity Service
- `/api/v1/conversations` → Conversation Service
- `/api/v1/ai` → AI Orchestrator
- `/ws/voice` → Voice Engine (WebSocket)
- gRPC 服务路由

### destination-rule.yaml

定义流量策略。

**特性**:
- 负载均衡策略（ROUND_ROBIN/LEAST_REQUEST/Consistent Hash）
- 连接池配置（HTTP/1.1 + HTTP/2）
- 熔断策略（OutlierDetection）
- 服务版本管理（subsets）

**示例**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: ai-orchestrator
spec:
  host: ai-orchestrator
  trafficPolicy:
    loadBalancer:
      simple: LEAST_REQUEST  # AI服务使用最少请求
    connectionPool:
      tcp:
        maxConnections: 500
      http:
        http2MaxRequests: 500
    outlierDetection:
      consecutiveErrors: 2
      interval: 10s
```

### security.yaml

安全配置。

**特性**:
- PeerAuthentication: 服务间 mTLS（STRICT 模式）
- RequestAuthentication: JWT 验证（多 Issuer）
- AuthorizationPolicy: 细粒度授权（24+ 策略）
- Deny by Default + 显式授权
- 租户隔离

**关键策略**:
- 默认拒绝外部未认证访问
- 允许 Ingress Gateway 访问
- 服务间 mTLS 强制
- 基于 JWT Claims 的授权
- IP 黑白名单
- 审计日志策略

### telemetry.yaml

可观测性配置。

**特性**:
- OpenTelemetry 全链路追踪
  - 全局 10% 采样率
  - AI 服务 50% 采样率
  - WebSocket 100% 采样率
- Prometheus 指标采集
  - Request Count/Duration/Size
  - gRPC 指标
  - TCP 连接指标
  - 自定义标签（tenant_id, user_id, ai_model）
- 访问日志
  - JSON 格式
  - 包含租户/用户/会话 ID
  - 错误请求过滤

### envoy-filter.yaml

高级功能配置。

**特性**:
- 全局限流（IP 限流 + Redis 分布式限流）
- 安全响应头（X-Frame-Options, CSP, HSTS）
- 请求ID生成和追踪
- CORS 全局策略
- 请求体大小限制
- 连接管理和超时
- WebSocket 升级支持
- gzip 压缩
- 结构化访问日志

---

## 🔧 常用操作

### 查看配置

```bash
# 查看所有Gateway
kubectl get gateway -A

# 查看VirtualService
kubectl get virtualservice -n voiceassistant-prod

# 查看DestinationRule
kubectl get destinationrule -n voiceassistant-prod

# 查看AuthorizationPolicy
kubectl get authorizationpolicy -n voiceassistant-prod

# 使用istioctl分析
istioctl analyze -n voiceassistant-prod
```

### 查看流量配置

```bash
# 查看Gateway Envoy配置
istioctl proxy-config listener <gateway-pod> -n istio-system
istioctl proxy-config route <gateway-pod> -n istio-system
istioctl proxy-config cluster <gateway-pod> -n istio-system

# 查看服务Sidecar配置
istioctl proxy-config all <pod-name> -n voiceassistant-prod
```

### 查看日志

```bash
# Gateway日志
kubectl logs -n istio-system -l app=istio-ingressgateway --tail=100 -f

# Istiod日志
kubectl logs -n istio-system -l app=istiod --tail=100 -f

# 服务Sidecar日志
kubectl logs -n voiceassistant-prod <pod-name> -c istio-proxy --tail=100
```

### 调试

```bash
# 查看Pilot配置分发状态
istioctl proxy-status

# 验证mTLS状态
istioctl authn tls-check <pod-name>.<namespace> <service>.<namespace>.svc.cluster.local

# 查看证书
istioctl proxy-config secret <pod-name> -n voiceassistant-prod

# 触发配置重载
istioctl proxy-config cluster <pod-name> -n voiceassistant-prod --fqdn <service-fqdn>
```

### 性能分析

```bash
# 查看Envoy统计
kubectl exec -n voiceassistant-prod <pod-name> -c istio-proxy -- \
  curl localhost:15000/stats/prometheus

# 查看连接池状态
kubectl exec -n voiceassistant-prod <pod-name> -c istio-proxy -- \
  curl localhost:15000/clusters

# 查看监听器状态
kubectl exec -n voiceassistant-prod <pod-name> -c istio-proxy -- \
  curl localhost:15000/listeners
```

---

## 📊 监控指标

### Prometheus 查询

```promql
# Gateway错误率
sum(rate(istio_requests_total{destination_service_name=~"istio-ingressgateway.*",response_code=~"5.."}[5m]))
/ sum(rate(istio_requests_total{destination_service_name=~"istio-ingressgateway.*"}[5m]))

# Service错误率
sum(rate(istio_requests_total{response_code=~"5.."}[5m])) by (destination_service)
/ sum(rate(istio_requests_total[5m])) by (destination_service)

# P95延迟
histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le))

# mTLS覆盖率
sum(istio_requests_total{connection_security_policy="mutual_tls"})
/ sum(istio_requests_total)

# Gateway吞吐量
sum(rate(istio_requests_total{destination_service_name=~"istio-ingressgateway.*"}[1m]))
```

### Grafana Dashboard

导入Istio官方Dashboard:
- **Istio Mesh Dashboard**: ID 7639
- **Istio Service Dashboard**: ID 7636
- **Istio Workload Dashboard**: ID 7630
- **Istio Performance Dashboard**: ID 11829

---

## 🔐 安全最佳实践

### mTLS 配置

```bash
# 检查mTLS状态
istioctl authn tls-check <pod> <service>

# 确保STRICT模式
kubectl get peerauthentication -n voiceassistant-prod
```

### JWT 认证

JWT Issuer: `https://identity.voiceassistant.com`
JWKS URI: `https://identity.voiceassistant.com/.well-known/jwks.json`

### 授权策略

- Deny by Default
- 显式ALLOW规则
- 基于Namespace隔离
- 基于ServiceAccount授权
- 基于JWT Claims授权（tenant_id, user_id, role）

---

## 🚨 故障排查

详见 [MIGRATION_GUIDE.md - 故障排查章节](./MIGRATION_GUIDE.md#故障排查)

常见问题:
- Gateway无法访问 → 检查Pod状态、Service、Gateway配置
- VirtualService不生效 → 使用 `istioctl analyze`
- mTLS连接失败 → 检查PeerAuthentication、证书
- 高延迟 → 检查连接池、OutlierDetection
- 限流不生效 → 检查EnvoyFilter、Redis连接

---

## 📚 参考文档

- [完整迁移指南](./MIGRATION_GUIDE.md)
- [Istio官方文档](https://istio.io/latest/docs/)
- [Envoy Proxy文档](https://www.envoyproxy.io/docs/)
- [架构概览](../../../docs/arch/overview.md)
- [迁移脚本](../../../scripts/migrate-apisix-to-istio.sh)

---

## 📞 联系支持

- **Slack**: #istio-migration
- **Wiki**: https://wiki.voiceassistant.com/istio
- **Grafana**: https://grafana.voiceassistant.com/d/istio-gateway
- **Prometheus**: https://prometheus.voiceassistant.com

---

## 📝 变更日志

### v3.0 (2025-10-28)
- ✅ 从 APISIX 迁移到 Istio Gateway/Envoy
- ✅ 完整的 Gateway/VirtualService/DestinationRule 配置
- ✅ 安全配置（mTLS + JWT + AuthorizationPolicy）
- ✅ 可观测性配置（OpenTelemetry + Prometheus）
- ✅ EnvoyFilter 高级功能（限流、压缩、日志）
- ✅ 迁移脚本和完整文档

### v2.0 (2025-10-26)
- 使用 APISIX 集中式网关

### v1.0 (2025-10-20)
- 初始 Istio 配置
