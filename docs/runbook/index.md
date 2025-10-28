# VoiceHelper 运维手册 (Runbook)

## 目录

- [1. 启动与停止](#1-启动与停止)
- [2. 健康检查](#2-健康检查)
- [3. 依赖服务](#3-依赖服务)
- [4. 常见故障排查](#4-常见故障排查)
- [5. 扩容与缩容](#5-扩容与缩容)
- [6. 配置更新](#6-配置更新)

---

## 1. 启动与停止

### 1.1 完整部署

```bash
# 一键部署所有服务
cd scripts
./deploy-k8s.sh

# 跳过Istio安装（如果已安装）
./deploy-k8s.sh --skip-istio

# 只部署应用服务（跳过基础设施）
./deploy-k8s.sh --skip-infra
```

### 1.2 单独部署服务

```bash
# 部署单个Go服务
kubectl apply -f deployments/k8s/services/go/identity-service.yaml

# 部署单个Python服务
kubectl apply -f deployments/k8s/services/python/agent-engine.yaml
```

### 1.3 使用 Helm 部署

```bash
# 添加依赖仓库
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# 部署
helm install voiceassistant ./deployments/helm/voiceassistant \
  --namespace voiceassistant-prod \
  --create-namespace \
  --values ./deployments/helm/voiceassistant/values.yaml

# 升级
helm upgrade voiceassistant ./deployments/helm/voiceassistant \
  --namespace voiceassistant-prod

# 卸载
helm uninstall voiceassistant --namespace voiceassistant-prod
```

### 1.4 停止服务

```bash
# 删除所有应用服务（保留基础设施）
kubectl delete deployment --all -n voiceassistant-prod

# 完全卸载
kubectl delete namespace voiceassistant-prod
kubectl delete namespace voiceassistant-infra
```

---

## 2. 健康检查

### 2.1 集群整体健康

```bash
# 检查所有Pod状态
kubectl get pods -n voiceassistant-prod
kubectl get pods -n voiceassistant-infra

# 检查服务端点
kubectl get endpoints -n voiceassistant-prod

# 检查资源使用
kubectl top nodes
kubectl top pods -n voiceassistant-prod
```

### 2.2 Istio 健康检查

```bash
# 检查Istio组件
kubectl get pods -n istio-system

# 检查Istio配置
istioctl analyze -n voiceassistant-prod

# 检查代理状态
istioctl proxy-status

# 查看Envoy配置
kubectl exec -it <pod-name> -n voiceassistant-prod -c istio-proxy -- curl localhost:15000/config_dump
```

### 2.3 单个服务健康检查

```bash
# HTTP健康检查
kubectl exec -it <pod-name> -n voiceassistant-prod -- curl localhost:8080/health

# 查看日志
kubectl logs -f <pod-name> -n voiceassistant-prod
kubectl logs -f <pod-name> -n voiceassistant-prod -c istio-proxy

# 进入容器
kubectl exec -it <pod-name> -n voiceassistant-prod -- /bin/sh
```

---

## 3. 依赖服务

### 3.1 PostgreSQL

```bash
# 检查状态
kubectl get pods -l app=postgres -n voiceassistant-infra

# 连接数据库
kubectl exec -it postgres-0 -n voiceassistant-infra -- psql -U postgres

# 备份
kubectl exec -it postgres-0 -n voiceassistant-infra -- pg_dump -U postgres voiceassistant > backup.sql

# 恢复
kubectl exec -i postgres-0 -n voiceassistant-infra -- psql -U postgres voiceassistant < backup.sql
```

### 3.2 Redis

```bash
# 检查状态
kubectl get pods -l app=redis -n voiceassistant-infra

# 连接Redis
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli

# 查看内存使用
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli INFO memory

# 清空缓存
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli FLUSHDB
```

### 3.3 Nacos

```bash
# 检查状态
kubectl get pods -l app=nacos -n voiceassistant-infra

# 端口转发访问控制台
kubectl port-forward -n voiceassistant-infra svc/nacos 8848:8848

# 访问: http://localhost:8848/nacos
# 用户名/密码: nacos/nacos
```

### 3.4 Milvus

```bash
# 检查状态
kubectl get pods -l app=milvus -n voiceassistant-infra

# 检查集合
kubectl exec -it milvus-0 -n voiceassistant-infra -- milvus-cli

# 查看统计信息
kubectl exec -it milvus-0 -n voiceassistant-infra -- curl localhost:9091/metrics
```

### 3.5 Elasticsearch

```bash
# 检查状态
kubectl get pods -l app=elasticsearch -n voiceassistant-infra

# 检查集群健康
kubectl exec -it elasticsearch-0 -n voiceassistant-infra -- curl localhost:9200/_cluster/health?pretty

# 查看索引
kubectl exec -it elasticsearch-0 -n voiceassistant-infra -- curl localhost:9200/_cat/indices?v
```

---

## 4. 常见故障排查

### 4.1 Pod 启动失败

**症状**: Pod 处于`CrashLoopBackOff`或`Error`状态

**排查步骤**:

```bash
# 1. 查看Pod详情
kubectl describe pod <pod-name> -n voiceassistant-prod

# 2. 查看日志
kubectl logs <pod-name> -n voiceassistant-prod --previous

# 3. 检查资源限制
kubectl get pod <pod-name> -n voiceassistant-prod -o yaml | grep -A 10 resources

# 4. 检查存储卷
kubectl get pvc -n voiceassistant-prod
```

**常见原因**:

- 镜像拉取失败: 检查镜像仓库权限
- 资源不足: 调整 resource requests/limits
- 配置错误: 检查 ConfigMap 和 Secret
- 依赖服务未就绪: 检查 initContainers

### 4.2 服务间通信失败

**症状**: 服务 A 无法访问服务 B

**排查步骤**:

```bash
# 1. 检查Service和Endpoints
kubectl get svc -n voiceassistant-prod
kubectl get endpoints <service-name> -n voiceassistant-prod

# 2. 测试网络连通性
kubectl exec -it <pod-name> -n voiceassistant-prod -- curl <service-name>:8080/health

# 3. 检查Istio配置
istioctl analyze -n voiceassistant-prod

# 4. 检查Network Policy
kubectl get networkpolicy -n voiceassistant-prod
kubectl describe networkpolicy <policy-name> -n voiceassistant-prod

# 5. 查看Envoy路由
kubectl exec <pod-name> -n voiceassistant-prod -c istio-proxy -- pilot-agent request GET config_dump
```

### 4.3 数据库连接超时

**症状**: 服务日志显示数据库连接超时

**排查步骤**:

```bash
# 1. 检查PostgreSQL状态
kubectl get pods -l app=postgres -n voiceassistant-infra
kubectl logs postgres-0 -n voiceassistant-infra

# 2. 检查连接数
kubectl exec -it postgres-0 -n voiceassistant-infra -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# 3. 检查慢查询
kubectl exec -it postgres-0 -n voiceassistant-infra -- psql -U postgres -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# 4. 调整连接池
# 修改ConfigMap中的max_connections参数
kubectl edit configmap postgres-tuning-config -n voiceassistant-infra
```

### 4.4 向量检索失败

**症状**: RAG 相关服务无法检索向量

**排查步骤**:

```bash
# 1. 检查Milvus状态
kubectl get pods -l app=milvus -n voiceassistant-infra

# 2. 检查集合是否存在
kubectl exec -it milvus-0 -n voiceassistant-infra -- curl "localhost:9091/api/v1/collections"

# 3. 重建索引
# 通过indexing-service API重建

# 4. 检查Milvus日志
kubectl logs milvus-0 -n voiceassistant-infra
```

### 4.5 缓存穿透

**症状**: Redis 命中率低，后端压力大

**排查步骤**:

```bash
# 1. 查看Redis统计
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli INFO stats

# 2. 监控实时命令
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli MONITOR

# 3. 查看慢日志
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli SLOWLOG GET 10

# 4. 增加缓存预热
# 通过应用层预热热点数据
```

### 4.6 限流触发

**症状**: 部分请求返回 429 Too Many Requests

**排查步骤**:

```bash
# 1. 查看Istio限流配置
kubectl get envoyfilter -n voiceassistant-prod

# 2. 查看Prometheus指标
kubectl port-forward -n istio-system svc/prometheus 9090:9090
# 访问: http://localhost:9090
# 查询: rate(istio_requests_total{response_code="429"}[5m])

# 3. 调整限流配置
kubectl edit envoyfilter rate-limit-filter -n voiceassistant-prod

# 4. 临时禁用限流（紧急情况）
kubectl delete envoyfilter rate-limit-filter -n voiceassistant-prod
```

---

## 5. 扩容与缩容

### 5.1 手动扩容

```bash
# 扩容Deployment
kubectl scale deployment agent-engine --replicas=5 -n voiceassistant-prod

# 扩容StatefulSet
kubectl scale statefulset nacos --replicas=5 -n voiceassistant-infra

# 批量扩容
kubectl scale deployment --all --replicas=3 -n voiceassistant-prod
```

### 5.2 HPA 自动扩容

```bash
# 查看HPA状态
kubectl get hpa -n voiceassistant-prod

# 查看HPA详情
kubectl describe hpa agent-engine-hpa -n voiceassistant-prod

# 修改HPA配置
kubectl edit hpa agent-engine-hpa -n voiceassistant-prod

# 临时禁用HPA
kubectl delete hpa agent-engine-hpa -n voiceassistant-prod
```

### 5.3 节点扩容

```bash
# AWS EKS
eksctl scale nodegroup --cluster=voiceassistant --name=ng-1 --nodes=10

# GKE
gcloud container clusters resize voiceassistant --num-nodes=10 --zone=us-central1-a

# 手动扩容（自建集群）
# 添加新节点后：
kubectl get nodes
```

---

## 6. 配置更新

### 6.1 更新 ConfigMap

```bash
# 编辑ConfigMap
kubectl edit configmap agent-engine-config -n voiceassistant-prod

# 重启Pod以应用新配置
kubectl rollout restart deployment agent-engine -n voiceassistant-prod

# 验证配置
kubectl exec -it <pod-name> -n voiceassistant-prod -- env | grep <CONFIG_KEY>
```

### 6.2 更新 Secret

```bash
# 创建新Secret
kubectl create secret generic new-secret --from-literal=key=value -n voiceassistant-prod

# 更新Secret
kubectl edit secret agent-engine-secret -n voiceassistant-prod

# 重启Pod
kubectl rollout restart deployment agent-engine -n voiceassistant-prod
```

### 6.3 滚动更新

```bash
# 更新镜像
kubectl set image deployment/agent-engine agent-engine=ghcr.io/voiceassistant/agent-engine:1.1.0 -n voiceassistant-prod

# 查看更新状态
kubectl rollout status deployment/agent-engine -n voiceassistant-prod

# 回滚
kubectl rollout undo deployment/agent-engine -n voiceassistant-prod

# 回滚到指定版本
kubectl rollout history deployment/agent-engine -n voiceassistant-prod
kubectl rollout undo deployment/agent-engine --to-revision=2 -n voiceassistant-prod
```

### 6.4 蓝绿发布

```bash
# 1. 部署新版本（green）
kubectl apply -f deployments/k8s/services/python/agent-engine-v2.yaml

# 2. 修改VirtualService切流量到green
kubectl edit virtualservice agent-engine-internal -n voiceassistant-prod
# weight: blue=50, green=50

# 3. 观察指标，逐步切换
# weight: blue=20, green=80

# 4. 完全切换后删除旧版本
kubectl delete deployment agent-engine-v1 -n voiceassistant-prod
```

---

## 附录：监控面板访问

```bash
# Grafana
kubectl port-forward -n istio-system svc/grafana 3000:3000
# 访问: http://localhost:3000

# Kiali (服务网格可视化)
kubectl port-forward -n istio-system svc/kiali 20001:20001
# 访问: http://localhost:20001

# Jaeger (分布式追踪)
kubectl port-forward -n istio-system svc/tracing 16686:16686
# 访问: http://localhost:16686

# Prometheus
kubectl port-forward -n istio-system svc/prometheus 9090:9090
# 访问: http://localhost:9090
```

---

## 紧急联系人

- **运维负责人**: ops@voiceassistant.com
- **架构师**: architect@voiceassistant.com
- **On-Call**: +86-xxx-xxxx-xxxx
