# Kubernetes 部署配置

本目录包含VoiceAssistant项目的Kubernetes部署配置，包括PostHog A/B测试平台的集成。

## 📂 文件列表

| 文件 | 说明 |
|------|------|
| `namespace.yaml` | 命名空间定义 |
| `posthog-deployment.yaml` | PostHog自托管完整部署 |
| `posthog-cloud-config.yaml` | PostHog云服务配置 |
| `model-router-deployment.yaml` | Model Router服务部署 |
| `deploy-posthog.sh` | 快速部署脚本 |
| `POSTHOG_K8S_DEPLOYMENT_GUIDE.md` | 详细部署指南 |

## 🚀 快速开始

### 选项1: 使用PostHog云服务（推荐）

```bash
# 1. 注册PostHog云服务
# 访问 https://app.posthog.com 获取API Key

# 2. 配置
./deploy-posthog.sh cloud

# 3. 部署Model Router
./deploy-posthog.sh model-router

# 4. 验证
./deploy-posthog.sh verify
```

### 选项2: 自托管PostHog

```bash
# 1. 编辑配置
vim posthog-deployment.yaml
# 更新: Secret密码、域名

# 2. 部署PostHog
./deploy-posthog.sh self-hosted

# 3. 部署Model Router
./deploy-posthog.sh model-router

# 4. 验证
./deploy-posthog.sh verify
```

## 📦 部署架构

```
┌─────────────────────────────────────────────┐
│         Kubernetes Cluster                  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  Namespace: voicehelper-prod         │  │
│  │  ┌──────────────────────────────┐    │  │
│  │  │  Model Router (3+ replicas)  │────┼──┼─> PostHog
│  │  │  - PostHog SDK 集成          │    │  │
│  │  │  - A/B Testing               │    │  │
│  │  │  - Feature Flags             │    │  │
│  │  └──────────────────────────────┘    │  │
│  │  - ConfigMap                         │  │
│  │  - Secret                            │  │
│  │  - HPA                               │  │
│  │  - Service                           │  │
│  │  - Ingress                           │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  Namespace: posthog (自托管)         │  │
│  │  ┌──────────────────────────────┐    │  │
│  │  │  PostHog Web (2 replicas)    │    │  │
│  │  │  PostHog Worker (2 replicas) │    │  │
│  │  │  PostgreSQL                  │    │  │
│  │  │  Redis                       │    │  │
│  │  │  ClickHouse                  │    │  │
│  │  └──────────────────────────────┘    │  │
│  └──────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

## 🔧 配置说明

### PostHog自托管

需要配置的密钥（`posthog-deployment.yaml`）:

```yaml
stringData:
  POSTHOG_DB_PASSWORD: "your-strong-password"      # PostgreSQL密码
  CLICKHOUSE_PASSWORD: "your-clickhouse-password"  # ClickHouse密码
  SECRET_KEY: "your-secret-key-min-32-chars"      # Django Secret Key (至少32字符)
```

生成强密码:

```bash
# PostgreSQL密码
openssl rand -base64 32

# ClickHouse密码
openssl rand -base64 32

# Secret Key
openssl rand -base64 48
```

需要配置的域名:

```yaml
# ConfigMap
SITE_URL: "https://posthog.your-domain.com"

# Ingress
spec:
  rules:
  - host: posthog.your-domain.com
```

### PostHog云服务

只需配置API Key:

```yaml
stringData:
  POSTHOG_API_KEY: "phc_YOUR_API_KEY"  # 从PostHog控制台获取
```

### Model Router

需要配置的内容（`model-router-deployment.yaml`）:

1. **镜像地址**:
```yaml
image: your-registry/model-router:latest
```

2. **PostHog配置**:
```yaml
# ConfigMap
POSTHOG_ENABLED: "true"
POSTHOG_HOST: "http://posthog-web.posthog.svc.cluster.local:8000"  # 自托管
# 或: https://app.posthog.com  # 云服务

# Secret
POSTHOG_API_KEY: "phc_YOUR_API_KEY"
```

3. **数据库配置**:
```yaml
DB_HOST: "postgres-service.voicehelper-prod.svc.cluster.local"
DB_PORT: "5432"
DB_NAME: "model_router"
DB_USER: "model_router"
DB_PASSWORD: "your-db-password"
```

4. **LLM API Keys**:
```yaml
OPENAI_API_KEY: "sk-..."
ANTHROPIC_API_KEY: "sk-ant-..."
```

## 📊 资源需求

### PostHog自托管

| 组件 | 副本数 | CPU | 内存 | 存储 |
|------|--------|-----|------|------|
| PostgreSQL | 1 | 500m-1 | 512Mi-2Gi | 20Gi |
| Redis | 1 | 250m-500m | 256Mi-1Gi | 5Gi |
| ClickHouse | 1 | 1-4 | 2Gi-8Gi | 50Gi |
| PostHog Web | 2 | 500m-2 | 1Gi-4Gi | - |
| PostHog Worker | 2 | 500m-2 | 1Gi-4Gi | - |
| **总计** | **7** | **3-10** | **5-20Gi** | **75Gi** |

### Model Router

| 组件 | 副本数 | CPU | 内存 |
|------|--------|-----|------|
| Model Router | 3-10 (HPA) | 500m-2 | 512Mi-2Gi |

## 🔍 验证部署

```bash
# 检查所有资源
kubectl get all -n posthog
kubectl get all -n voicehelper-prod

# 检查Pod状态
kubectl get pods -n posthog
kubectl get pods -n voicehelper-prod -l app=model-router

# 查看日志
kubectl logs -n posthog -l app=posthog-web -f
kubectl logs -n voicehelper-prod -l app=model-router -f

# 测试健康检查
kubectl exec -it -n voicehelper-prod \
  $(kubectl get pod -n voicehelper-prod -l app=model-router -o jsonpath='{.items[0].metadata.name}') \
  -- curl http://localhost:8080/health

# 查看HPA状态
kubectl get hpa -n voicehelper-prod

# 查看Ingress
kubectl get ingress -n posthog
kubectl get ingress -n voicehelper-prod
```

## 🔄 常用操作

### 扩容/缩容

```bash
# Model Router手动扩容
kubectl scale deployment model-router -n voicehelper-prod --replicas=5

# PostHog扩容
kubectl scale deployment posthog-web -n posthog --replicas=4
kubectl scale deployment posthog-worker -n posthog --replicas=4
```

### 更新配置

```bash
# 更新ConfigMap后重启
kubectl rollout restart deployment/model-router -n voicehelper-prod

# 更新Secret后重启
kubectl rollout restart deployment/model-router -n voicehelper-prod
```

### 查看指标

```bash
# 端口转发到Prometheus指标端点
kubectl port-forward -n voicehelper-prod svc/model-router 9090:9090

# 访问 http://localhost:9090/metrics
```

### 故障排查

```bash
# 查看Pod详情
kubectl describe pod -n voicehelper-prod <pod-name>

# 进入容器
kubectl exec -it -n voicehelper-prod <pod-name> -- /bin/sh

# 查看事件
kubectl get events -n voicehelper-prod --sort-by='.lastTimestamp'

# 查看日志（最近100行）
kubectl logs -n voicehelper-prod <pod-name> --tail=100
```

## 📈 监控

PostHog提供了内置的监控面板:

1. 访问PostHog控制台
2. 进入 **Settings** → **System Status**
3. 查看:
   - 事件摄入率
   - 查询性能
   - 存储使用情况
   - Worker状态

Model Router指标（Prometheus格式）:

- `model_router_requests_total` - 总请求数
- `model_router_request_duration_seconds` - 请求延迟
- `model_router_ab_test_exposures_total` - 实验曝光数
- `posthog_events_sent_total` - 发送到PostHog的事件数

## 🔐 安全

### Secret管理

建议使用外部Secret管理工具:

- **Sealed Secrets**: 加密Secret存储在Git
- **External Secrets Operator**: 从外部系统同步
- **Vault**: HashiCorp Vault集成

### 网络策略

限制Pod间通信:

```bash
kubectl apply -f - <<YAML
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: model-router-netpol
  namespace: voicehelper-prod
spec:
  podSelector:
    matchLabels:
      app: model-router
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: posthog
YAML
```

## 📚 相关文档

- [详细部署指南](./POSTHOG_K8S_DEPLOYMENT_GUIDE.md)
- [PostHog官方文档](https://posthog.com/docs)
- [PostHog Kubernetes部署](https://posthog.com/docs/self-host/deploy/kubernetes)
- [Model Router集成说明](../../cmd/model-router/POSTHOG_INTEGRATION.md)

## ❓ 常见问题

### Q: 自托管还是云服务？

**云服务**适合:
- 快速开始（5分钟）
- 中小规模（< 100万事件/月）
- 不想管理基础设施

**自托管**适合:
- 数据隐私要求高
- 大规模部署（> 100万事件/月）
- 需要完全控制

### Q: 部署失败怎么办？

```bash
# 1. 查看Pod状态
kubectl get pods -n posthog
kubectl get pods -n voicehelper-prod

# 2. 查看详细信息
kubectl describe pod -n posthog <pod-name>

# 3. 查看日志
kubectl logs -n posthog <pod-name>

# 4. 常见问题:
# - 持久化存储未就绪
# - 内存不足
# - 镜像拉取失败
```

### Q: 如何升级？

```bash
# 升级PostHog
kubectl set image deployment/posthog-web -n posthog \
  posthog=posthog/posthog:1.45.0

# 升级Model Router
kubectl set image deployment/model-router -n voicehelper-prod \
  model-router=your-registry/model-router:v2.0.0

# 回滚
kubectl rollout undo deployment/model-router -n voicehelper-prod
```

## 🆘 获取帮助

- GitHub Issues: https://github.com/your-org/voice-assistant/issues
- PostHog社区: https://posthog.com/community
- PostHog Slack: https://posthog.com/slack

---

**开始部署企业级A/B测试平台！🚀**
