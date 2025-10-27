# 基础设施服务 Kubernetes 配置

本目录包含 VoiceAssistant 项目所需的所有基础设施服务的 Kubernetes 部署配置。

## 📋 服务清单

### 核心存储服务

| 服务              | 文件                    | 用途       | 端口       | 存储需求 |
| ----------------- | ----------------------- | ---------- | ---------- | -------- |
| **PostgreSQL**    | `postgres.yaml`         | 关系数据库 | 5432       | 50Gi     |
| **Redis**         | `redis.yaml`            | 缓存和会话 | 6379       | 10Gi     |
| **Milvus**        | `milvus.yaml`           | 向量数据库 | 19530      | 100Gi    |
| **Elasticsearch** | `elasticsearch.yaml`    | 全文搜索   | 9200       | 100Gi    |
| **ClickHouse**    | `clickhouse.yaml`       | 分析数据库 | 9000, 8123 | 100Gi    |
| **MinIO**         | `minio-standalone.yaml` | 对象存储   | 9000, 9001 | 200Gi    |

### 配置与协调服务

| 服务      | 文件          | 用途              | 端口 | 副本数 |
| --------- | ------------- | ----------------- | ---- | ------ |
| **Nacos** | `nacos.yaml`  | 配置中心/服务发现 | 8848 | 3      |
| **Etcd**  | `milvus.yaml` | Milvus 元数据存储 | 2379 | 1      |

### 消息队列

| 服务      | 文件         | 用途     | 端口 | 副本数 |
| --------- | ------------ | -------- | ---- | ------ |
| **Kafka** | `kafka.yaml` | 消息队列 | 9092 | 3      |

### 可观测性

| 服务             | 文件                      | 用途       | 端口  | 存储需求 |
| ---------------- | ------------------------- | ---------- | ----- | -------- |
| **Prometheus**   | `prometheus-grafana.yaml` | 指标收集   | 9090  | 100Gi    |
| **Grafana**      | `prometheus-grafana.yaml` | 可视化     | 3000  | 10Gi     |
| **Jaeger**       | `jaeger.yaml`             | 分布式追踪 | 16686 | -        |
| **Alertmanager** | `alertmanager.yaml`       | 告警管理   | 9093  | -        |

## 🚀 快速部署

### 方式一：一键部署所有基础设施

```bash
# 创建命名空间
kubectl create namespace voiceassistant-infra

# 部署所有基础设施服务
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml
kubectl apply -f nacos.yaml
kubectl apply -f milvus.yaml
kubectl apply -f elasticsearch.yaml
kubectl apply -f clickhouse.yaml
kubectl apply -f kafka.yaml
kubectl apply -f minio-standalone.yaml
kubectl apply -f prometheus-grafana.yaml
kubectl apply -f jaeger.yaml
kubectl apply -f alertmanager.yaml
```

### 方式二：按需部署

```bash
# 最小化部署（核心服务）
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml
kubectl apply -f nacos.yaml
kubectl apply -f milvus.yaml

# 可选：分析服务
kubectl apply -f elasticsearch.yaml
kubectl apply -f clickhouse.yaml

# 可选：消息队列
kubectl apply -f kafka.yaml

# 可选：监控
kubectl apply -f prometheus-grafana.yaml
kubectl apply -f jaeger.yaml
kubectl apply -f alertmanager.yaml
```

### 方式三：使用脚本部署

```bash
# 使用项目提供的部署脚本
cd ../../scripts
./deploy-k8s.sh --skip-istio
```

## 📊 资源需求

### 最小配置

| 资源类型 | 需求   |
| -------- | ------ |
| CPU      | 16 核  |
| 内存     | 32 GB  |
| 存储     | 500 GB |
| 节点数   | 3      |

### 生产环境推荐

| 资源类型 | 需求  |
| -------- | ----- |
| CPU      | 32 核 |
| 内存     | 64 GB |
| 存储     | 1 TB  |
| 节点数   | 5+    |

## 🔧 配置说明

### PostgreSQL

- **用途**: 存储用户、对话、知识库等业务数据
- **配置**:
  - 主从复制：支持（通过 StatefulSet）
  - 连接池：200
  - 持久化：启用
- **访问**: `postgres.voiceassistant-infra.svc.cluster.local:5432`
- **初始化**: 自动创建 `identity`、`conversation`、`knowledge` 数据库

### Redis

- **用途**: 缓存、会话、限流
- **配置**:
  - 持久化：AOF + RDB
  - 最大内存：2GB
  - 淘汰策略：allkeys-lru
- **访问**: `redis.voiceassistant-infra.svc.cluster.local:6379`

### Nacos

- **用途**: 配置中心、服务发现
- **配置**:
  - 集群模式：3 节点
  - 存储：MySQL
- **访问**: `nacos.voiceassistant-infra.svc.cluster.local:8848`
- **控制台**:
  ```bash
  kubectl port-forward -n voiceassistant-infra svc/nacos 8848:8848
  # 访问 http://localhost:8848/nacos (nacos/nacos)
  ```

### Milvus

- **用途**: 向量相似度搜索
- **配置**:
  - 模式：Standalone
  - 依赖：Etcd + MinIO
- **访问**: `milvus.voiceassistant-infra.svc.cluster.local:19530`

### Elasticsearch

- **用途**: 全文检索、日志分析
- **配置**:
  - 节点数：1
  - 堆内存：2GB
  - 索引生命周期：30 天
- **访问**: `elasticsearch.voiceassistant-infra.svc.cluster.local:9200`

### ClickHouse

- **用途**: OLAP 分析、用户行为分析
- **配置**:
  - 节点数：1
  - 压缩：启用
  - 数据保留：90 天
- **访问**: `clickhouse.voiceassistant-infra.svc.cluster.local:8123` (HTTP)

### Kafka

- **用途**: 事件流、异步处理
- **配置**:
  - 模式：KRaft（无需 ZooKeeper）
  - 副本数：3
  - 数据保留：7 天
- **访问**: `kafka.voiceassistant-infra.svc.cluster.local:9092`
- **UI**:
  ```bash
  kubectl port-forward -n voiceassistant-infra svc/kafka-ui 8080:8080
  # 访问 http://localhost:8080
  ```

### MinIO

- **用途**: 对象存储（文档、图片、模型）
- **配置**:
  - Buckets: documents, multimodal, milvus-bucket, backups
  - 版本控制：可选
- **访问**:
  - API: `minio.voiceassistant-infra.svc.cluster.local:9000`
  - Console:
    ```bash
    kubectl port-forward -n voiceassistant-infra svc/minio 9001:9001
    # 访问 http://localhost:9001 (minioadmin/minioadmin123)
    ```

### Prometheus

- **用途**: 指标收集和存储
- **配置**:
  - 采集间隔：15s
  - 数据保留：15 天
  - 存储：100Gi
- **访问**:
  ```bash
  kubectl port-forward -n voiceassistant-infra svc/prometheus 9090:9090
  # 访问 http://localhost:9090
  ```

### Grafana

- **用途**: 指标可视化
- **配置**:
  - 数据源：Prometheus
  - 默认密码：admin/admin
- **访问**:
  ```bash
  kubectl port-forward -n voiceassistant-infra svc/grafana 3000:3000
  # 访问 http://localhost:3000
  ```

### Jaeger

- **用途**: 分布式追踪
- **配置**:
  - 存储：Elasticsearch
  - 采样率：10%（AI 服务 50%）
- **访问**:
  ```bash
  kubectl port-forward -n voiceassistant-infra svc/jaeger-query 16686:16686
  # 访问 http://localhost:16686
  ```

### Alertmanager

- **用途**: 告警路由和通知
- **配置**:
  - 分组：按 alertname、cluster、service
  - 接收器：Email、Webhook
- **访问**:
  ```bash
  kubectl port-forward -n voiceassistant-infra svc/alertmanager 9093:9093
  # 访问 http://localhost:9093
  ```

## 🔍 健康检查

### 检查所有服务状态

```bash
# 查看所有 Pod
kubectl get pods -n voiceassistant-infra

# 查看服务
kubectl get svc -n voiceassistant-infra

# 查看持久化存储
kubectl get pvc -n voiceassistant-infra
```

### 检查特定服务

```bash
# PostgreSQL
kubectl exec -it postgres-0 -n voiceassistant-infra -- psql -U postgres -c "SELECT version();"

# Redis
kubectl exec -it redis-0 -n voiceassistant-infra -- redis-cli ping

# Nacos
curl http://localhost:8848/nacos/actuator/health

# Milvus
kubectl exec -it milvus-0 -n voiceassistant-infra -- curl localhost:9091/healthz

# Elasticsearch
kubectl exec -it elasticsearch-0 -n voiceassistant-infra -- curl localhost:9200/_cluster/health

# ClickHouse
kubectl exec -it clickhouse-0 -n voiceassistant-infra -- clickhouse-client --query "SELECT 1"

# Kafka
kubectl exec -it kafka-0 -n voiceassistant-infra -- kafka-topics --bootstrap-server localhost:9092 --list
```

## 🔐 安全配置

### 默认密码（生产环境必须修改）

| 服务       | 用户名     | 密码          | Secret          |
| ---------- | ---------- | ------------- | --------------- |
| PostgreSQL | postgres   | changeme      | postgres-secret |
| Redis      | -          | (空)          | redis-secret    |
| Nacos      | nacos      | nacos         | nacos-secret    |
| Milvus     | root       | Milvus        | milvus-secret   |
| MinIO      | minioadmin | minioadmin123 | minio-secret    |
| Grafana    | admin      | admin         | -               |

### 修改密码

```bash
# PostgreSQL
kubectl edit secret postgres-secret -n voiceassistant-infra

# MinIO
kubectl edit secret minio-secret -n voiceassistant-infra

# 重启服务使密码生效
kubectl rollout restart statefulset/postgres -n voiceassistant-infra
kubectl rollout restart deployment/minio -n voiceassistant-infra
```

## 💾 备份与恢复

### PostgreSQL

```bash
# 备份
kubectl exec -n voiceassistant-infra postgres-0 -- pg_dumpall -U postgres > backup.sql

# 恢复
kubectl exec -i -n voiceassistant-infra postgres-0 -- psql -U postgres < backup.sql
```

### Redis

```bash
# 备份
kubectl exec -n voiceassistant-infra redis-0 -- redis-cli BGSAVE
kubectl cp voiceassistant-infra/redis-0:/data/dump.rdb ./redis-backup.rdb

# 恢复
kubectl cp ./redis-backup.rdb voiceassistant-infra/redis-0:/data/dump.rdb
kubectl rollout restart statefulset/redis -n voiceassistant-infra
```

### MinIO

```bash
# 使用 mc 客户端备份
kubectl exec -n voiceassistant-infra minio-0 -- mc mirror /data /backup
```

详细备份脚本请参考：`../../scripts/backup-restore.sh`

## 📈 监控指标

### 关键指标

- **PostgreSQL**: 连接数、QPS、慢查询
- **Redis**: 命中率、内存使用、QPS
- **Milvus**: 向量搜索延迟、索引数量
- **Kafka**: 消息堆积、消费延迟
- **ClickHouse**: 查询延迟、压缩率

### 查看指标

```bash
# Prometheus 指标
curl http://localhost:9090/api/v1/query?query=up

# 应用指标
kubectl port-forward -n voiceassistant-infra svc/prometheus 9090:9090
# 访问 http://localhost:9090/graph
```

## 🛠️ 故障排查

### Pod 无法启动

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n voiceassistant-infra

# 查看日志
kubectl logs <pod-name> -n voiceassistant-infra

# 查看事件
kubectl get events -n voiceassistant-infra --sort-by='.lastTimestamp'
```

### 存储问题

```bash
# 查看 PVC 状态
kubectl get pvc -n voiceassistant-infra

# 查看 PV
kubectl get pv

# 检查存储类
kubectl get storageclass
```

### 网络问题

```bash
# 测试服务连通性
kubectl run -it --rm debug --image=busybox -n voiceassistant-infra -- sh
# 在 Pod 内：
# wget -O- http://postgres:5432
# nc -zv redis 6379
```

## 📚 参考文档

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Redis 官方文档](https://redis.io/documentation)
- [Nacos 官方文档](https://nacos.io/zh-cn/docs/what-is-nacos.html)
- [Milvus 官方文档](https://milvus.io/docs)
- [Elasticsearch 官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [ClickHouse 官方文档](https://clickhouse.com/docs/)
- [Kafka 官方文档](https://kafka.apache.org/documentation/)
- [MinIO 官方文档](https://min.io/docs/)
- [Prometheus 官方文档](https://prometheus.io/docs/)
- [Jaeger 官方文档](https://www.jaegertracing.io/docs/)

## ⚠️ 注意事项

1. **存储**: 确保 Kubernetes 集群有足够的持久化存储
2. **资源**: 生产环境建议增加 CPU 和内存限制
3. **高可用**: 考虑部署多副本和跨可用区
4. **备份**: 定期备份数据库和关键数据
5. **监控**: 配置告警规则，及时发现问题
6. **安全**: 修改默认密码，启用访问控制
7. **网络**: 配置 NetworkPolicy 限制服务间访问

## 🔄 升级策略

### 滚动升级

```bash
# 升级镜像版本
kubectl set image deployment/postgres postgres=postgres:16 -n voiceassistant-infra

# 查看升级状态
kubectl rollout status deployment/postgres -n voiceassistant-infra

# 回滚
kubectl rollout undo deployment/postgres -n voiceassistant-infra
```

### 蓝绿部署

1. 部署新版本（green）
2. 切换流量
3. 验证新版本
4. 删除旧版本（blue）

---

**维护负责人**: SRE 团队
**最后更新**: 2024-01-XX
