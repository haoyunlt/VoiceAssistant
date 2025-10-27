# PostHog Kubernetes 部署指南

本指南介绍如何在 Kubernetes 集群中部署 PostHog 并集成到 VoiceAssistant 的 Model Router 服务。

## 📋 目录

1. [部署选项](#部署选项)
2. [选项 A: 自托管 PostHog](#选项a-自托管posthog)
3. [选项 B: PostHog 云服务](#选项b-posthog云服务)
4. [部署 Model Router](#部署model-router)
5. [验证部署](#验证部署)
6. [监控和故障排查](#监控和故障排查)

## 部署选项

### 对比

| 特性     | 自托管         | 云服务             |
| -------- | -------------- | ------------------ |
| 数据控制 | ✅ 完全控制    | ⚠️ 托管在 PostHog  |
| 运维成本 | 高             | 低                 |
| 扩展性   | 需自行管理     | 自动扩展           |
| 成本     | 基础设施成本   | 按使用量付费       |
| 启动时间 | 30-60 分钟     | 5 分钟             |
| 推荐场景 | 企业、数据敏感 | 快速开始、中小规模 |

## 选项 A: 自托管 PostHog

### 前置条件

- Kubernetes 1.20+
- kubectl 已配置
- 持久化存储支持 (PVC)
- Ingress Controller (如 Nginx Ingress)
- 至少 8GB RAM 和 4 CPU cores 的节点

### 资源需求

| 组件           | CPU       | 内存       | 存储     |
| -------------- | --------- | ---------- | -------- |
| PostgreSQL     | 500m-1    | 512Mi-2Gi  | 20Gi     |
| Redis          | 250m-500m | 256Mi-1Gi  | 5Gi      |
| ClickHouse     | 1-4       | 2Gi-8Gi    | 50Gi     |
| PostHog Web    | 500m-2    | 1Gi-4Gi    | -        |
| PostHog Worker | 500m-2    | 1Gi-4Gi    | -        |
| **总计**       | **3-10**  | **5-20Gi** | **75Gi** |

### 快速部署

```bash
# 1. 创建命名空间
kubectl create namespace posthog

# 2. 应用部署
kubectl apply -f posthog-deployment.yaml

# 3. 等待Pod就绪
kubectl wait --for=condition=ready pod -l app=posthog-web -n posthog --timeout=600s

# 4. 获取Ingress地址
kubectl get ingress -n posthog
```

### 详细步骤请参考完整文档

## 选项 B: PostHog 云服务

### 步骤

1. 访问 https://app.posthog.com 注册
2. 创建项目并获取 API Key
3. 应用云配置:

```bash
kubectl apply -f posthog-cloud-config.yaml
```

## 部署 Model Router

```bash
# 1. 构建并推送镜像
cd cmd/model-router
docker build -t your-registry/model-router:latest .
docker push your-registry/model-router:latest

# 2. 更新配置
vim model-router-deployment.yaml
# 修改: 镜像地址、PostHog API Key、域名

# 3. 部署
kubectl apply -f model-router-deployment.yaml

# 4. 查看状态
kubectl get pods -n voiceassistant-prod -l app=model-router -w
```

## 验证部署

```bash
# 检查Pod状态
kubectl get pods -n posthog
kubectl get pods -n voiceassistant-prod -l app=model-router

# 测试PostHog连接
kubectl exec -it -n voiceassistant-prod \
  $(kubectl get pod -n voiceassistant-prod -l app=model-router -o jsonpath='{.items[0].metadata.name}') \
  -- curl -v $POSTHOG_HOST/_health

# 访问PostHog控制台
# https://posthog.your-domain.com
```

## 监控和故障排查

```bash
# 查看日志
kubectl logs -n posthog -l app=posthog-web -f
kubectl logs -n voiceassistant-prod -l app=model-router -f

# 查看指标
kubectl port-forward -n voiceassistant-prod svc/model-router 9090:9090
# 访问 http://localhost:9090/metrics
```

## 常见问题

### PostHog Pod 启动失败

- 检查持久化存储
- 检查数据库连接
- 增加内存限制

### Model Router 无法连接 PostHog

- 验证 PostHog 服务地址
- 检查网络策略
- 验证 API Key

### 事件未显示

- 确认 POSTHOG_ENABLED=true
- 检查 API Key
- 查看 Worker 日志

## 快速命令参考

```bash
# 查看所有PostHog资源
kubectl get all -n posthog

# 重启PostHog
kubectl rollout restart deployment/posthog-web -n posthog

# 扩容Model Router
kubectl scale deployment model-router -n voiceassistant-prod --replicas=5

# 查看HPA状态
kubectl get hpa -n voiceassistant-prod

# 备份PostgreSQL
kubectl exec -n posthog <postgres-pod> -- \
  pg_dump -U posthog posthog > backup.sql
```

## 下一步

1. 访问 PostHog 控制台
2. 创建第一个实验
3. 查看实时数据
4. 配置告警

---

**更多详细信息请参考 PostHog 官方文档: https://posthog.com/docs**

