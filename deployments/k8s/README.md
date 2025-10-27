# VoiceAssistant Kubernetes 部署

VoiceAssistant 完整的 Kubernetes + Istio 部署配置，包含所有微服务和基础设施。

## 📁 目录结构

```
k8s/
├── README.md                 # 本文件
├── deploy-all.yaml          # 基础配置（命名空间、RBAC、资源配额等）
├── istio/                   # Istio 服务网格配置
│   ├── namespace.yaml       # 命名空间（启用 Istio 注入）
│   ├── gateway.yaml         # Istio Gateway 入口
│   ├── virtual-service.yaml # 路由规则
│   ├── destination-rule.yaml# 流量策略
│   ├── security.yaml        # mTLS、JWT、授权策略
│   ├── telemetry.yaml       # 可观测性配置
│   └── traffic-management.yaml # 熔断、限流、超时
├── services/                # 应用服务配置
│   ├── go/                  # Go 微服务
│   │   ├── identity-service.yaml
│   │   ├── conversation-service.yaml
│   │   ├── knowledge-service.yaml
│   │   ├── ai-orchestrator.yaml
│   │   ├── notification-service.yaml
│   │   └── analytics-service.yaml
│   └── python/              # Python AI 服务
│       ├── agent-engine.yaml
│       ├── rag-engine.yaml
│       ├── voice-engine.yaml
│       ├── model-adapter.yaml
│       ├── retrieval-service.yaml
│       ├── indexing-service.yaml
│       ├── multimodal-engine.yaml
│       └── vector-store-adapter.yaml
└── infrastructure/          # 基础设施服务
    ├── README.md            # 基础设施详细文档
    ├── postgres.yaml
    ├── redis.yaml
    ├── nacos.yaml
    ├── milvus.yaml
    ├── elasticsearch.yaml
    ├── clickhouse.yaml
    ├── kafka.yaml
    ├── minio-standalone.yaml
    ├── prometheus-grafana.yaml
    ├── jaeger.yaml
    └── alertmanager.yaml
```

## 🚀 快速开始

### 前置要求

- Kubernetes 1.25+
- kubectl 配置完成
- Istio 1.19+ （可选，脚本会自动安装）
- 至少 3 个节点，每个节点 8 核 CPU / 16 GB 内存
- 持久化存储支持（StorageClass）

### 一键部署

```bash
# 克隆项目
cd VoiceAssistant

# 执行部署脚本
./scripts/deploy-k8s.sh

# 查看部署状态
kubectl get pods -n voiceassistant-prod
kubectl get pods -n voiceassistant-infra
```

部署脚本会自动完成以下步骤：

1. 检查依赖工具（kubectl、helm、istioctl）
2. 安装 Istio（如果未安装）
3. 创建命名空间和基础配置
4. 部署基础设施服务
5. 配置 Istio 路由和安全策略
6. 部署应用服务
7. 验证部署状态

### 选项参数

```bash
# 跳过 Istio 安装（如果已安装）
./scripts/deploy-k8s.sh --skip-istio

# 跳过基础设施部署（如果已部署）
./scripts/deploy-k8s.sh --skip-infra

# 仅验证部署状态
./scripts/deploy-k8s.sh --verify-only
```

## 📦 分步部署

如果需要更精细的控制，可以分步部署：

### 1. 部署基础配置

```bash
kubectl apply -f deploy-all.yaml
kubectl apply -f istio/namespace.yaml
```

### 2. 部署基础设施

```bash
# 核心存储
kubectl apply -f infrastructure/postgres.yaml
kubectl apply -f infrastructure/redis.yaml
kubectl apply -f infrastructure/nacos.yaml
kubectl apply -f infrastructure/milvus.yaml

# 可选：搜索和分析
kubectl apply -f infrastructure/elasticsearch.yaml
kubectl apply -f infrastructure/clickhouse.yaml

# 可选：消息队列
kubectl apply -f infrastructure/kafka.yaml

# 可选：监控
kubectl apply -f infrastructure/prometheus-grafana.yaml
kubectl apply -f infrastructure/jaeger.yaml
kubectl apply -f infrastructure/alertmanager.yaml

# 等待基础设施就绪
kubectl wait --for=condition=ready pod -l app=postgres -n voiceassistant-infra --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n voiceassistant-infra --timeout=300s
kubectl wait --for=condition=ready pod -l app=nacos -n voiceassistant-infra --timeout=300s
```

### 3. 配置 Istio

```bash
kubectl apply -f istio/gateway.yaml
kubectl apply -f istio/virtual-service.yaml
kubectl apply -f istio/destination-rule.yaml
kubectl apply -f istio/security.yaml
kubectl apply -f istio/telemetry.yaml
kubectl apply -f istio/traffic-management.yaml
```

### 4. 部署应用服务

```bash
# Go 服务
kubectl apply -f services/go/identity-service.yaml
kubectl apply -f services/go/conversation-service.yaml
kubectl apply -f services/go/knowledge-service.yaml
kubectl apply -f services/go/ai-orchestrator.yaml
kubectl apply -f services/go/notification-service.yaml
kubectl apply -f services/go/analytics-service.yaml

# Python AI 服务
kubectl apply -f services/python/agent-engine.yaml
kubectl apply -f services/python/rag-engine.yaml
kubectl apply -f services/python/voice-engine.yaml
kubectl apply -f services/python/model-adapter.yaml
kubectl apply -f services/python/retrieval-service.yaml
kubectl apply -f services/python/indexing-service.yaml
kubectl apply -f services/python/multimodal-engine.yaml
kubectl apply -f services/python/vector-store-adapter.yaml
```

## 🔍 验证部署

### 检查服务状态

```bash
# 查看所有服务
kubectl get all -n voiceassistant-prod
kubectl get all -n voiceassistant-infra

# 查看 Istio 配置
kubectl get gateway,virtualservice,destinationrule -n voiceassistant-prod

# 查看 HPA 状态
kubectl get hpa -n voiceassistant-prod
```

### 测试服务连通性

```bash
# 获取 Ingress Gateway 地址
export INGRESS_HOST=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export INGRESS_PORT=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.spec.ports[?(@.name=="http2")].port}')

# 测试健康检查
curl http://${INGRESS_HOST}:${INGRESS_PORT}/health

# 测试 API
curl http://${INGRESS_HOST}:${INGRESS_PORT}/api/v1/health
```

### 访问监控面板

```bash
# 使用脚本一键启动所有面板
./scripts/monitoring-dashboard.sh all

# 或单独启动
./scripts/monitoring-dashboard.sh grafana    # http://localhost:3000
./scripts/monitoring-dashboard.sh kiali      # http://localhost:20001
./scripts/monitoring-dashboard.sh jaeger     # http://localhost:16686
./scripts/monitoring-dashboard.sh prometheus # http://localhost:9090
./scripts/monitoring-dashboard.sh nacos      # http://localhost:8848
```

## ⚙️ 配置管理

### 更新配置

```bash
# 修改 ConfigMap
kubectl edit configmap agent-engine-config -n voiceassistant-prod

# 重启服务应用配置
kubectl rollout restart deployment agent-engine -n voiceassistant-prod
```

### 更新 Secret

```bash
# 修改 Secret
kubectl edit secret agent-engine-secret -n voiceassistant-prod

# 重启服务
kubectl rollout restart deployment agent-engine -n voiceassistant-prod
```

## 🔄 升级和回滚

### 滚动升级

```bash
# 更新镜像
kubectl set image deployment/agent-engine \
  agent-engine=ghcr.io/voiceassistant/agent-engine:1.1.0 \
  -n voiceassistant-prod

# 查看升级进度
kubectl rollout status deployment/agent-engine -n voiceassistant-prod
```

### 回滚

```bash
# 查看历史版本
kubectl rollout history deployment/agent-engine -n voiceassistant-prod

# 回滚到上一版本
kubectl rollout undo deployment/agent-engine -n voiceassistant-prod

# 回滚到指定版本
kubectl rollout undo deployment/agent-engine --to-revision=2 -n voiceassistant-prod
```

## 📊 扩缩容

### 手动扩容

```bash
# 扩容到 5 个副本
kubectl scale deployment agent-engine --replicas=5 -n voiceassistant-prod
```

### 自动扩容（HPA）

```bash
# 查看 HPA 状态
kubectl get hpa -n voiceassistant-prod

# 修改 HPA 配置
kubectl edit hpa agent-engine-hpa -n voiceassistant-prod
```

## 🔐 安全配置

### 更新 TLS 证书

```bash
# 创建 TLS Secret
kubectl create secret tls voiceassistant-tls-cert \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem \
  -n voiceassistant-prod
```

### 配置 Network Policy

所有服务已配置默认的 Network Policy，限制跨命名空间访问。

### 审计日志

```bash
# 查看 API Server 审计日志
kubectl logs -n kube-system kube-apiserver-<node> | grep audit
```

## 🛠️ 故障排查

### 常见问题

#### Pod 无法启动

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n voiceassistant-prod

# 查看日志
kubectl logs <pod-name> -n voiceassistant-prod

# 查看 Istio Sidecar 日志
kubectl logs <pod-name> -c istio-proxy -n voiceassistant-prod
```

#### 服务间通信失败

```bash
# 检查 Istio 配置
istioctl analyze -n voiceassistant-prod

# 查看服务路由
kubectl exec <pod-name> -n voiceassistant-prod -c istio-proxy -- \
  pilot-agent request GET config_dump

# 测试连通性
kubectl exec -it <pod-name> -n voiceassistant-prod -- \
  curl http://target-service:8080/health
```

#### 性能问题

```bash
# 查看资源使用
kubectl top pods -n voiceassistant-prod
kubectl top nodes

# 查看 Istio 指标
kubectl port-forward -n istio-system svc/prometheus 9090:9090
# 访问 http://localhost:9090
```

详细故障排查请参考：[Runbook](../../docs/runbook/index.md)

## 💾 备份与恢复

```bash
# 使用备份脚本
./scripts/backup-restore.sh backup-all

# 备份特定服务
./scripts/backup-restore.sh backup-postgres
./scripts/backup-restore.sh backup-redis

# 恢复
./scripts/backup-restore.sh restore-postgres backups/postgres_*.sql.gz

# 清理旧备份（保留 30 天）
./scripts/backup-restore.sh cleanup 30
```

## 📈 监控和告警

### Prometheus 查询

```bash
# 服务可用性
up{job="kubernetes-pods"}

# 错误率
sum(rate(istio_requests_total{response_code=~"5.."}[5m]))
/
sum(rate(istio_requests_total[5m]))

# P95 延迟
histogram_quantile(0.95,
  rate(istio_request_duration_milliseconds_bucket[5m])
)
```

### Grafana Dashboard

预配置的 Dashboard：

- Kubernetes 集群概览
- Istio 服务网格
- 应用服务指标
- 基础设施监控

## 🧹 清理

### 删除应用服务

```bash
# 删除所有应用
kubectl delete namespace voiceassistant-prod

# 保留基础设施
kubectl delete deployment --all -n voiceassistant-prod
```

### 完全卸载

```bash
# 删除所有资源
kubectl delete namespace voiceassistant-prod
kubectl delete namespace voiceassistant-infra

# 卸载 Istio
istioctl uninstall --purge -y
kubectl delete namespace istio-system
```

## 📚 相关文档

- [架构概览](../../docs/arch/overview.md)
- [运维手册](../../docs/runbook/index.md)
- [SLO 目标](../../docs/nfr/slo.md)
- [基础设施详情](./infrastructure/README.md)
- [API 文档](../../api/openapi.yaml)

## 🆘 获取帮助

- 技术支持：support@voiceassistant.com
- 架构师：architect@voiceassistant.com
- On-Call：+86-xxx-xxxx-xxxx
- Issue：https://github.com/voiceassistant/VoiceAssistant/issues

---

**维护者**: DevOps & SRE 团队
**最后更新**: 2024-01-XX
