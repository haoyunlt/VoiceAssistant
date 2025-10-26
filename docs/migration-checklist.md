# VoiceHelper 微服务架构迁移清单

> **版本**: v1.0  
> **创建日期**: 2025-10-26  
> **迁移周期**: 12周（3个月）  
> **风险等级**: 中-高  
> **回滚策略**: 分阶段迁移，保持原架构并行运行

---

## 目录

1. [迁移总览](#1-迁移总览)
2. [阶段一：基础设施准备](#2-阶段一基础设施准备-week-1-2)
3. [阶段二：服务拆分重构](#3-阶段二服务拆分重构-week-3-6)
4. [阶段三：服务网格集成](#4-阶段三服务网格集成-week-7-8)
5. [阶段四：数据迁移](#5-阶段四数据迁移-week-9-10)
6. [阶段五：灰度发布与验证](#6-阶段五灰度发布与验证-week-11-12)
7. [风险评估与回滚计划](#7-风险评估与回滚计划)

---

## 1. 迁移总览

### 1.1 迁移范围

| 类别 | 原架构 | 目标架构 | 变更类型 |
|-----|--------|---------|---------|
| **服务数量** | 9个服务 | 12个服务 | 新增3个 |
| **通信协议** | HTTP REST | gRPC + Kafka | 协议升级 |
| **服务网格** | ❌ 无 | ✅ Istio | 新增 |
| **BFF层** | ❌ 无 | ✅ 3个BFF | 新增 |
| **事件总线** | ❌ 无 | ✅ Kafka | 新增 |
| **日志系统** | ELK Stack | Loki | 替换 |
| **数据库** | 共享PostgreSQL | 独立Schema | 重构 |
| **密钥管理** | 环境变量 | Vault | 升级 |

### 1.2 迁移原则

1. **渐进式迁移**: 一次迁移一个服务，避免大爆炸式变更
2. **保持兼容**: 新旧系统并行运行，逐步切换流量
3. **先易后难**: 从无状态服务开始，最后迁移有状态服务
4. **充分测试**: 每个阶段都有完整的测试和验证
5. **快速回滚**: 出现问题立即回滚到原架构

### 1.3 成功标准

- [ ] 所有服务迁移到新架构并稳定运行
- [ ] 系统可用性 ≥ 99.9%
- [ ] P95延迟 ≤ 原架构 + 10%
- [ ] 无数据丢失
- [ ] 无业务中断（0 downtime）
- [ ] 监控和告警正常工作

---

## 2. 阶段一：基础设施准备 (Week 1-2)

### 2.1 Kubernetes集群搭建

#### 任务清单

- [ ] **2.1.1 创建Kubernetes集群** (2天)
  - [ ] 选择Kubernetes版本（推荐v1.28+）
  - [ ] 配置控制平面（3个master节点）
  - [ ] 配置工作节点（至少6个worker节点）
  - [ ] 配置存储类（StorageClass for PostgreSQL/Redis PV）
  - [ ] 配置网络插件（Calico/Cilium）
  
- [ ] **2.1.2 安装Helm** (0.5天)
  - [ ] 安装Helm CLI（v3.x）
  - [ ] 配置Helm仓库（bitnami, stable, 自建）
  
- [ ] **2.1.3 配置Ingress Controller** (1天)
  - [ ] 安装Nginx Ingress Controller
  - [ ] 配置SSL证书（Let's Encrypt）
  - [ ] 配置域名解析

**验收标准**:
```bash
# 检查集群状态
kubectl get nodes
# 预期：所有节点Ready

# 检查Helm
helm version
# 预期：v3.x

# 检查Ingress
kubectl get svc -n ingress-nginx
# 预期：LoadBalancer外部IP
```

### 2.2 Istio服务网格部署

#### 任务清单

- [ ] **2.2.1 安装Istio** (1天)
  - [ ] 下载Istio CLI（istioctl）
  - [ ] 选择配置profile（推荐default或production）
  - [ ] 安装Istio控制平面到istio-system namespace
  - [ ] 验证Istio安装
  
```bash
# 安装Istio
istioctl install --set profile=default

# 验证
kubectl get pods -n istio-system
# 预期：istiod、istio-ingressgateway运行中
```

- [ ] **2.2.2 配置Sidecar自动注入** (0.5天)
  - [ ] 为voicehelper-prod命名空间打标签
  
```bash
kubectl label namespace voicehelper-prod istio-injection=enabled
```

- [ ] **2.2.3 部署Istio Addon** (1天)
  - [ ] 部署Kiali（服务拓扑可视化）
  - [ ] 部署Prometheus（集成监控）
  - [ ] 部署Jaeger（链路追踪）
  - [ ] 部署Grafana（可视化面板）

**验收标准**:
```bash
# 检查Istio状态
istioctl verify-install

# 访问Kiali Dashboard
istioctl dashboard kiali
```

### 2.3 Kafka事件总线部署

#### 任务清单

- [ ] **2.3.1 部署Kafka集群** (2天)
  - [ ] 使用Helm安装Kafka（bitnami/kafka）
  - [ ] 配置3个Kafka broker节点
  - [ ] 配置Zookeeper集群（3节点）
  - [ ] 配置持久化存储（PVC 100GB/broker）
  
```bash
helm install kafka bitnami/kafka \
  --set replicaCount=3 \
  --set zookeeper.replicaCount=3 \
  --set persistence.size=100Gi
```

- [ ] **2.3.2 创建Topic** (0.5天)
  - [ ] conversation.events（6分区，3副本）
  - [ ] document.events（3分区，3副本）
  - [ ] ai.tasks（12分区，3副本）
  - [ ] ai.results（6分区，3副本）
  - [ ] notification.requests（3分区，3副本）

```bash
# 创建Topic示例
kafka-topics.sh --create \
  --topic conversation.events \
  --bootstrap-server kafka:9092 \
  --partitions 6 \
  --replication-factor 3
```

- [ ] **2.3.3 部署Kafka UI** (0.5天)
  - [ ] 部署Kafka UI（provectuslabs/kafka-ui）
  - [ ] 配置访问权限

**验收标准**:
```bash
# 检查Kafka
kubectl get pods -l app=kafka
# 预期：3个broker运行中

# 测试生产消费
kafka-console-producer.sh --topic test --bootstrap-server kafka:9092
kafka-console-consumer.sh --topic test --bootstrap-server kafka:9092 --from-beginning
```

### 2.4 Vault密钥管理部署

#### 任务清单

- [ ] **2.4.1 部署Vault集群** (1天)
  - [ ] 使用Helm安装Vault（hashicorp/vault）
  - [ ] 配置高可用模式（3节点）
  - [ ] 初始化Vault并unseal
  - [ ] 配置Kubernetes认证
  
```bash
helm install vault hashicorp/vault \
  --set server.ha.enabled=true \
  --set server.ha.replicas=3
```

- [ ] **2.4.2 配置密钥存储** (1天)
  - [ ] 创建KV v2 secret engine
  - [ ] 迁移现有密钥（数据库密码、API Key等）
  - [ ] 配置密钥访问策略
  
```bash
# 启用KV v2
vault secrets enable -path=secret kv-v2

# 存储密钥
vault kv put secret/voicehelper/postgres \
  password="secure_password" \
  username="voicehelper"
```

- [ ] **2.4.3 集成服务** (1天)
  - [ ] 为每个服务创建Vault角色
  - [ ] 配置Kubernetes Service Account绑定
  - [ ] 测试服务从Vault读取密钥

**验收标准**:
```bash
# 检查Vault状态
kubectl exec -it vault-0 -- vault status
# 预期：Sealed=false

# 测试读取密钥
kubectl exec -it vault-0 -- vault kv get secret/voicehelper/postgres
```

### 2.5 可观测性平台部署

#### 任务清单

- [ ] **2.5.1 部署Prometheus Stack** (1天)
  - [ ] 使用kube-prometheus-stack Helm Chart
  - [ ] 配置ServiceMonitor自动发现
  - [ ] 配置持久化存储（PVC 500GB）
  - [ ] 配置数据保留策略（30天）

```bash
helm install prometheus prometheus-community/kube-prometheus-stack \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=500Gi
```

- [ ] **2.5.2 部署Loki** (1天)
  - [ ] 安装Loki（grafana/loki-stack）
  - [ ] 部署Promtail（日志采集）
  - [ ] 配置日志存储（S3/MinIO）
  - [ ] 配置日志保留策略（14天）

```bash
helm install loki grafana/loki-stack \
  --set loki.persistence.enabled=true \
  --set loki.persistence.size=200Gi \
  --set promtail.enabled=true
```

- [ ] **2.5.3 配置Grafana Dashboard** (1天)
  - [ ] 导入Istio Dashboard
  - [ ] 导入Kubernetes Dashboard
  - [ ] 创建业务指标Dashboard
  - [ ] 配置告警规则

**验收标准**:
- Prometheus可访问并抓取指标
- Loki可查询日志
- Grafana Dashboard正常显示

---

## 3. 阶段二：服务拆分重构 (Week 3-6)

### 3.1 Identity Service重构 (Week 3)

#### 任务清单

- [ ] **3.1.1 创建服务骨架** (1天)
  - [ ] 创建项目目录结构（DDD分层）
  - [ ] 配置go.mod依赖
  - [ ] 实现基础HTTP/gRPC服务器
  - [ ] 集成Consul服务注册
  
- [ ] **3.1.2 领域模型设计** (1天)
  - [ ] 定义User、Tenant、Role、Permission领域模型
  - [ ] 设计Repository接口
  - [ ] 设计Application Service接口
  
- [ ] **3.1.3 迁移Auth Service代码** (2天)
  - [ ] 迁移JWT认证逻辑
  - [ ] 迁移OAuth2逻辑
  - [ ] 迁移SAML逻辑
  - [ ] 迁移RBAC逻辑
  - [ ] 重构为DDD架构
  
- [ ] **3.1.4 新增租户管理** (1天)
  - [ ] 实现租户CRUD
  - [ ] 实现配额管理
  - [ ] 实现多租户数据隔离
  
- [ ] **3.1.5 编写单元测试** (1天)
  - [ ] Domain层单元测试
  - [ ] Application层单元测试
  - [ ] Repository层集成测试
  - [ ] 测试覆盖率 ≥ 80%

**API定义**:

```protobuf
// api/proto/identity/v1/identity.proto
syntax = "proto3";
package identity.v1;

service IdentityService {
  // 认证
  rpc Login(LoginRequest) returns (LoginResponse);
  rpc Logout(LogoutRequest) returns (Empty);
  rpc RefreshToken(RefreshTokenRequest) returns (TokenResponse);
  rpc VerifyToken(VerifyTokenRequest) returns (TokenClaims);
  
  // 用户管理
  rpc GetUser(GetUserRequest) returns (User);
  rpc UpdateUser(UpdateUserRequest) returns (User);
  rpc DeleteUser(DeleteUserRequest) returns (Empty);
  
  // 租户管理
  rpc CreateTenant(CreateTenantRequest) returns (Tenant);
  rpc GetTenant(GetTenantRequest) returns (Tenant);
  rpc UpdateTenantQuota(UpdateQuotaRequest) returns (Tenant);
  
  // 权限管理
  rpc CheckPermission(CheckPermissionRequest) returns (PermissionResult);
  rpc AssignRole(AssignRoleRequest) returns (Empty);
}
```

**验收标准**:
- [ ] 所有API通过单元测试
- [ ] gRPC接口可正常调用
- [ ] Prometheus指标正常暴露
- [ ] Jaeger追踪正常工作

### 3.2 Conversation Service重构 (Week 3)

#### 任务清单

- [ ] **3.2.1 创建服务骨架** (1天)
- [ ] **3.2.2 领域模型设计** (1天)
  - [ ] Conversation、Message、Context、Participant模型
- [ ] **3.2.3 迁移Session Service代码** (2天)
  - [ ] 迁移会话管理逻辑
  - [ ] 迁移消息存储逻辑
  - [ ] 迁移上下文缓存逻辑
- [ ] **3.2.4 新增流式响应** (1天)
  - [ ] 实现SSE流式接口
  - [ ] 实现WebSocket接口
  - [ ] 实现gRPC Server Stream
- [ ] **3.2.5 集成Kafka事件发布** (1天)
  - [ ] 发布conversation.created事件
  - [ ] 发布message.sent事件
  - [ ] 发布conversation.closed事件
- [ ] **3.2.6 编写测试** (1天)

**事件定义**:

```go
// internal/domain/events.go
type ConversationCreatedEvent struct {
    EventID        string    `json:"event_id"`
    EventType      string    `json:"event_type"` // "conversation.created"
    ConversationID string    `json:"conversation_id"`
    UserID         string    `json:"user_id"`
    TenantID       string    `json:"tenant_id"`
    Mode           string    `json:"mode"` // "chat", "agent", "workflow"
    Title          string    `json:"title"`
    Timestamp      time.Time `json:"timestamp"`
}
```

**验收标准**:
- [ ] gRPC接口正常工作
- [ ] 流式响应正常
- [ ] Kafka事件正常发布
- [ ] Redis缓存正常工作

### 3.3 Knowledge Service + Indexing Service + Retrieval Service (Week 4)

#### 任务清单

**Knowledge Service (Go)**:

- [ ] **3.3.1 创建Knowledge Service** (1天)
  - [ ] 迁移Document Service代码
  - [ ] 实现文档CRUD
  - [ ] 实现版本管理
  - [ ] 集成MinIO
  - [ ] 发布document.uploaded事件到Kafka

**Indexing Service (Python)**:

- [ ] **3.3.2 创建Indexing Service** (2天)
  - [ ] 订阅document.uploaded事件
  - [ ] 实现文档解析（PDF/Word/Markdown）
  - [ ] 实现语义分块
  - [ ] 实现向量化（BGE-M3）
  - [ ] 实现图谱构建（Neo4j）
  - [ ] 发布document.indexed事件

**Retrieval Service (Python)**:

- [ ] **3.3.3 创建Retrieval Service** (2天)
  - [ ] 实现向量检索（FAISS）
  - [ ] 实现BM25检索（PostgreSQL）
  - [ ] 实现图检索（Neo4j）
  - [ ] 实现混合检索（RRF融合）
  - [ ] 实现重排序（BGE Reranker）
  - [ ] 实现语义缓存（Redis）

**验收标准**:
- [ ] 文档上传→索引→检索全流程通
- [ ] 事件驱动架构正常工作
- [ ] 检索性能满足要求（P95 < 200ms）

### 3.4 AI Orchestrator + Engines (Week 5)

#### 任务清单

**AI Orchestrator (Go)**:

- [ ] **3.4.1 创建AI Orchestrator** (2天)
  - [ ] 实现任务路由逻辑
  - [ ] 实现流程编排（串行/并行）
  - [ ] 实现结果聚合
  - [ ] 集成gRPC客户端（Agent/RAG/Voice/Multimodal）
  - [ ] 实现超时控制与重试

**重构Engines**:

- [ ] **3.4.2 重构Agent Engine** (2天)
  - [ ] 拆分原Agent Service代码
  - [ ] 实现gRPC接口
  - [ ] 移除直接调用LLM Router的逻辑（改为通过Orchestrator）
  
- [ ] **3.4.3 重构RAG Engine** (2天)
  - [ ] 拆分原GraphRAG Service代码
  - [ ] 调用Retrieval Service获取上下文
  - [ ] 实现gRPC接口

**验收标准**:
- [ ] Orchestrator可正确路由到各Engine
- [ ] 流程编排正常工作
- [ ] 超时和重试逻辑正常

### 3.5 Model Router + Adapter (Week 6)

#### 任务清单

**Model Router (Go)**:

- [ ] **3.5.1 重构Model Router** (2天)
  - [ ] 迁移原LLM Router代码
  - [ ] 实现gRPC接口
  - [ ] 实现路由决策逻辑
  - [ ] 实现降级策略
  - [ ] 集成语义缓存
  
**Model Adapter (Python)**:

- [ ] **3.5.2 创建Model Adapter** (2天)
  - [ ] 实现OpenAI适配器
  - [ ] 实现Claude适配器
  - [ ] 实现通义千问适配器
  - [ ] 实现文心一言适配器
  - [ ] 实现GLM-4适配器
  - [ ] 实现gRPC接口

**职责分离**:
- Router: 路由决策（Go高性能）
- Adapter: API适配（Python灵活）

**验收标准**:
- [ ] Router→Adapter调用正常
- [ ] 所有LLM提供商可正常访问
- [ ] 降级策略正常工作

### 3.6 Notification Service重构 (Week 6)

#### 任务清单

- [ ] **3.6.1 重构Notification Service** (2天)
  - [ ] 订阅Kafka事件
  - [ ] 实现订阅规则匹配
  - [ ] 实现模板渲染
  - [ ] 保持原有Channel实现（Email/SMS/Push/Webhook）

- [ ] **3.6.2 实现WebSocket推送** (1天)
  - [ ] 实现WebSocket Hub
  - [ ] 实现连接池管理
  - [ ] 实现消息广播

**验收标准**:
- [ ] 事件驱动通知正常工作
- [ ] 各通道发送正常

### 3.7 BFF层开发 (Week 6)

#### 任务清单

- [ ] **3.7.1 创建Web BFF** (1天)
  - [ ] 实现聊天页面数据聚合
  - [ ] 实现文档页面数据聚合
  - [ ] 实现用户中心数据聚合
  
- [ ] **3.7.2 创建Mobile BFF** (1天)
  - [ ] 精简字段适配移动端
  - [ ] 实现数据压缩
  
- [ ] **3.7.3 创建Admin BFF** (1天)
  - [ ] 实现管理后台数据聚合
  - [ ] 实现统计数据预计算

**验收标准**:
- [ ] BFF可正常聚合后端服务
- [ ] 并发调用正常工作
- [ ] 响应时间满足要求

---

## 4. 阶段三：服务网格集成 (Week 7-8)

### 4.1 gRPC通信切换 (Week 7)

#### 任务清单

- [ ] **4.1.1 生成Protobuf代码** (1天)
  - [ ] 为所有服务生成Go代码
  - [ ] 为所有Python服务生成代码
  - [ ] 更新import路径
  
- [ ] **4.1.2 实现gRPC客户端** (2天)
  - [ ] Gateway → BFF (保持HTTP)
  - [ ] BFF → Domain Services (切换gRPC)
  - [ ] Domain Services ↔ Domain Services (切换gRPC)
  - [ ] 配置连接池
  - [ ] 配置超时和重试
  
- [ ] **4.1.3 集成Istio流量管理** (2天)
  - [ ] 配置VirtualService
  - [ ] 配置DestinationRule
  - [ ] 配置负载均衡策略
  - [ ] 配置熔断策略

**VirtualService示例**:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: conversation-service
spec:
  hosts:
  - conversation-service
  http:
  - timeout: 30s
    retries:
      attempts: 3
      perTryTimeout: 10s
      retryOn: 5xx,reset,connect-failure,refused-stream
    route:
    - destination:
        host: conversation-service
        port:
          number: 9090
```

**验收标准**:
- [ ] 所有服务间调用切换到gRPC
- [ ] Istio流量管理正常工作
- [ ] 熔断和重试正常工作

### 4.2 mTLS加密启用 (Week 7)

#### 任务清单

- [ ] **4.2.1 启用PeerAuthentication** (0.5天)

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: voicehelper-prod
spec:
  mtls:
    mode: STRICT  # 强制mTLS
```

- [ ] **4.2.2 配置AuthorizationPolicy** (1天)
  - [ ] 为每个服务配置访问策略
  - [ ] 限制服务间调用权限
  
```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: conversation-authz
spec:
  selector:
    matchLabels:
      app: conversation-service
  action: ALLOW
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/voicehelper-prod/sa/bff-service"]
    to:
    - operation:
        methods: ["POST"]
        paths: ["/conversation.v1.ConversationService/*"]
```

- [ ] **4.2.3 测试mTLS连接** (0.5天)

**验收标准**:
- [ ] 所有服务间通信加密
- [ ] 未授权调用被拒绝
- [ ] 证书自动轮换正常

### 4.3 Kafka事件总线集成 (Week 8)

#### 任务清单

- [ ] **4.3.1 实现事件发布者** (1天)
  - [ ] Conversation Service发布事件
  - [ ] Knowledge Service发布事件
  - [ ] AI Orchestrator发布事件
  
- [ ] **4.3.2 实现事件消费者** (2天)
  - [ ] Indexing Service订阅document.uploaded
  - [ ] Notification Service订阅所有业务事件
  - [ ] Analytics Service订阅所有事件（新增）
  
- [ ] **4.3.3 测试事件流** (1天)
  - [ ] 测试端到端事件流
  - [ ] 测试消费者组负载均衡
  - [ ] 测试消息顺序性
  - [ ] 测试At-Least-Once语义

**验收标准**:
- [ ] 事件正常发布和消费
- [ ] 消息无丢失
- [ ] 消费者组正常工作

---

## 5. 阶段四：数据迁移 (Week 9-10)

### 5.1 数据库Schema迁移 (Week 9)

#### 任务清单

- [ ] **5.1.1 创建新Schema** (1天)

```sql
-- 创建各服务独立Schema
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS conversation;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS notification;
```

- [ ] **5.1.2 迁移表结构** (2天)
  - [ ] 迁移users表到identity schema
  - [ ] 迁移sessions/messages表到conversation schema
  - [ ] 迁移documents表到knowledge schema
  - [ ] 迁移notifications表到notification schema
  
```sql
-- 示例：迁移users表
CREATE TABLE identity.users AS SELECT * FROM public.users;
CREATE INDEX idx_identity_users_email ON identity.users(email);
```

- [ ] **5.1.3 数据同步验证** (1天)
  - [ ] 对比原表和新表数据
  - [ ] 验证外键关系
  - [ ] 验证索引

**验收标准**:
- [ ] 数据完整性100%
- [ ] 无数据丢失
- [ ] 索引正常工作

### 5.2 缓存迁移 (Week 9)

#### 任务清单

- [ ] **5.2.1 Redis Key重命名** (1天)

```bash
# 旧Key格式
session:{id}
user:{id}

# 新Key格式（加服务前缀）
conversation:cache:session:{id}
identity:cache:user:{id}
```

- [ ] **5.2.2 编写迁移脚本** (1天)

```python
# migrate_redis_keys.py
import redis

r = redis.Redis()

# 迁移session key
for key in r.scan_iter("session:*"):
    new_key = key.replace(b"session:", b"conversation:cache:session:")
    r.rename(key, new_key)
```

- [ ] **5.2.3 执行迁移** (0.5天)
  - [ ] 在低峰期执行
  - [ ] 监控Redis性能

**验收标准**:
- [ ] 所有Key已重命名
- [ ] 缓存命中率正常
- [ ] 无业务影响

### 5.3 MinIO数据迁移 (Week 10)

#### 任务清单

- [ ] **5.3.1 创建新Bucket** (0.5天)

```bash
# 旧Bucket
voicehelper

# 新Bucket（按服务划分）
voicehelper-documents
voicehelper-avatars
voicehelper-attachments
```

- [ ] **5.3.2 数据迁移** (1天)

```bash
# 使用mc (MinIO Client)迁移
mc cp --recursive s3/voicehelper/documents/ s3/voicehelper-documents/
mc cp --recursive s3/voicehelper/avatars/ s3/voicehelper-avatars/
```

- [ ] **5.3.3 更新服务配置** (0.5天)
  - [ ] 更新Knowledge Service配置
  - [ ] 更新Identity Service配置

**验收标准**:
- [ ] 文件完整性100%
- [ ] 下载链接正常工作

---

## 6. 阶段五：灰度发布与验证 (Week 11-12)

### 6.1 金丝雀发布 (Week 11)

#### 任务清单

- [ ] **6.1.1 部署v2版本** (1天)
  - [ ] 所有新服务部署到生产环境
  - [ ] 标记version=v2 label
  - [ ] 配置环境变量和密钥

- [ ] **6.1.2 配置流量分配** (1天)

**Stage 1: 5%流量**

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bff-service
spec:
  hosts:
  - bff-service
  http:
  - route:
    - destination:
        host: bff-service
        subset: v1
      weight: 95
    - destination:
        host: bff-service
        subset: v2
      weight: 5
```

- [ ] **6.1.3 观察与验证** (2天)
  - [ ] 监控错误率（< 0.1%）
  - [ ] 监控P95延迟（< 500ms）
  - [ ] 监控业务指标（会话创建成功率 > 99%）
  - [ ] 查看Jaeger追踪
  - [ ] 查看Grafana Dashboard

**Stage 2-5: 逐步增加流量**

| Stage | v2流量 | 观察时长 | 回滚条件 |
|-------|-------|---------|---------|
| Stage 1 | 5% | 4小时 | 错误率 > 0.5% |
| Stage 2 | 20% | 8小时 | 错误率 > 0.3% |
| Stage 3 | 50% | 12小时 | P95延迟 > 800ms |
| Stage 4 | 80% | 24小时 | 用户投诉 > 3 |
| Stage 5 | 100% | - | - |

- [ ] **6.1.4 Full Rollout** (1天)
  - [ ] 100%流量切换到v2
  - [ ] 下线v1服务
  - [ ] 清理旧代码和配置

**验收标准**:
- [ ] v2服务稳定运行
- [ ] 所有业务指标正常
- [ ] 无用户投诉

### 6.2 回归测试 (Week 12)

#### 任务清单

- [ ] **6.2.1 功能测试** (2天)
  - [ ] 用户注册/登录
  - [ ] 创建会话
  - [ ] 发送消息（chat/agent/workflow）
  - [ ] 上传文档
  - [ ] 知识检索
  - [ ] 语音对话
  - [ ] 接收通知

- [ ] **6.2.2 性能测试** (2天)
  - [ ] 并发用户测试（1000并发）
  - [ ] 压力测试（10000 QPS）
  - [ ] 长时间稳定性测试（24小时）

- [ ] **6.2.3 安全测试** (1天)
  - [ ] 渗透测试
  - [ ] SQL注入测试
  - [ ] XSS测试
  - [ ] CSRF测试
  - [ ] 认证绕过测试

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 性能满足要求
- [ ] 无安全漏洞

### 6.3 文档更新 (Week 12)

#### 任务清单

- [ ] **6.3.1 更新架构文档** (1天)
  - [ ] 更新架构图
  - [ ] 更新服务列表
  - [ ] 更新API文档

- [ ] **6.3.2 编写运维手册** (1天)
  - [ ] Kubernetes部署指南
  - [ ] Istio配置指南
  - [ ] 故障排查手册
  - [ ] 回滚操作手册

- [ ] **6.3.3 培训团队** (1天)
  - [ ] 新架构培训
  - [ ] Istio使用培训
  - [ ] Kafka使用培训
  - [ ] 监控和告警培训

**验收标准**:
- [ ] 文档完整准确
- [ ] 团队成员熟悉新架构

---

## 7. 风险评估与回滚计划

### 7.1 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|------|---------|
| **服务间通信失败** | 中 | 高 | 保留HTTP备用接口、配置重试 |
| **数据迁移丢失** | 低 | 高 | 全量备份、分步迁移、双写验证 |
| **性能下降** | 中 | 中 | 压力测试、逐步放量、性能优化 |
| **Istio故障** | 低 | 高 | 保留Consul备用、快速回滚 |
| **Kafka消息堆积** | 中 | 中 | 监控消费lag、扩容消费者 |
| **证书过期** | 低 | 中 | 自动轮换、告警提醒 |
| **新服务Bug** | 高 | 中 | 充分测试、金丝雀发布、快速回滚 |
| **学习曲线** | 高 | 低 | 提前培训、文档完善 |

### 7.2 回滚计划

#### 7.2.1 快速回滚步骤

**Step 1: 流量切回v1**

```bash
# 将流量100%切回v1版本
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bff-service
spec:
  hosts:
  - bff-service
  http:
  - route:
    - destination:
        host: bff-service
        subset: v1
      weight: 100
EOF
```

**Step 2: 验证v1服务正常**

```bash
# 检查v1服务健康
kubectl get pods -l version=v1
# 验证API可访问
curl http://bff-service/health
```

**Step 3: 数据回滚（如果有数据迁移）**

```sql
-- 回滚到旧Schema
SET search_path TO public;
```

**Step 4: 通知团队**

- 发送告警通知
- 记录回滚原因
- 安排复盘会议

#### 7.2.2 回滚决策矩阵

| 指标 | 阈值 | 决策 |
|-----|------|------|
| 错误率 | > 1% | 立即回滚 |
| P95延迟 | > 2x baseline | 立即回滚 |
| P99延迟 | > 3x baseline | 考虑回滚 |
| 数据丢失 | 任何数量 | 立即回滚 |
| 服务宕机 | > 30s | 立即回滚 |
| 用户投诉 | > 5个/小时 | 考虑回滚 |

### 7.3 应急预案

#### 7.3.1 Istio故障

```bash
# 禁用Istio Sidecar自动注入
kubectl label namespace voicehelper-prod istio-injection=disabled

# 重启Pods（移除Sidecar）
kubectl rollout restart deployment -n voicehelper-prod

# 服务发现退回到Consul
export USE_CONSUL=true
```

#### 7.3.2 Kafka故障

```bash
# 切换到同步调用
export USE_KAFKA=false

# 直接调用Notification Service
curl -X POST http://notification-service/send
```

#### 7.3.3 数据库故障

```bash
# 切换到从库
export DB_HOST=postgres-replica

# 启用只读模式
export DB_READ_ONLY=true
```

---

## 8. 迁移后验证清单

### 8.1 功能验证

- [ ] 用户注册和登录正常
- [ ] 会话创建和消息发送正常
- [ ] 文档上传和检索正常
- [ ] Agent任务执行正常
- [ ] 语音对话正常
- [ ] 通知推送正常
- [ ] WebSocket连接正常
- [ ] 流式响应正常

### 8.2 性能验证

- [ ] API P95延迟 < 300ms
- [ ] API P99延迟 < 1s
- [ ] 并发1000用户无问题
- [ ] QPS 5000+稳定
- [ ] 语音端到端延迟 < 3s
- [ ] 文档上传处理时间 < 10s

### 8.3 可观测性验证

- [ ] Prometheus指标正常采集
- [ ] Grafana Dashboard正常显示
- [ ] Loki日志正常查询
- [ ] Jaeger追踪完整链路
- [ ] 告警规则正常触发

### 8.4 安全验证

- [ ] mTLS加密正常工作
- [ ] 未授权访问被拦截
- [ ] API Key验证正常
- [ ] JWT Token验证正常
- [ ] 敏感数据加密存储
- [ ] 审计日志完整记录

### 8.5 高可用验证

- [ ] 服务实例故障自动恢复
- [ ] 数据库主从切换正常
- [ ] Redis Sentinel切换正常
- [ ] 负载均衡正常工作
- [ ] 熔断器正常工作
- [ ] 限流器正常工作

---

## 9. 迁移成本估算

### 9.1 人力成本

| 角色 | 人数 | 周数 | 人周 |
|-----|------|------|------|
| **架构师** | 1 | 12 | 12 |
| **后端工程师（Go）** | 2 | 12 | 24 |
| **后端工程师（Python）** | 2 | 8 | 16 |
| **SRE工程师** | 1 | 12 | 12 |
| **测试工程师** | 1 | 6 | 6 |
| **总计** | 7 | - | **70人周** |

### 9.2 基础设施成本（年化）

| 资源 | 规格 | 数量 | 月费用 | 年费用 |
|-----|------|------|-------|-------|
| **Kubernetes节点** | 8核16GB | 10 | $2000 | $24000 |
| **PostgreSQL** | RDS 4核16GB | 2 | $600 | $7200 |
| **Redis Sentinel** | 3节点 | 1 | $300 | $3600 |
| **Kafka集群** | 3 broker | 1 | $500 | $6000 |
| **MinIO存储** | 10TB | 1 | $200 | $2400 |
| **Vault集群** | 3节点 | 1 | $300 | $3600 |
| **监控存储** | 2TB | 1 | $100 | $1200 |
| **总计** | - | - | $4000 | **$48000** |

### 9.3 总成本

- 人力成本：70人周 × $2000/人周 = **$140,000**
- 基础设施成本（首年）：**$48,000**
- **总计：$188,000**

---

## 10. 迁移后收益

### 10.1 技术收益

| 指标 | 迁移前 | 迁移后 | 提升 |
|-----|-------|--------|------|
| **服务间通信性能** | HTTP REST | gRPC | 5-10x |
| **故障恢复时间** | 5-10分钟 | < 1分钟 | 90% |
| **部署时间** | 30分钟 | 5分钟 | 83% |
| **监控覆盖率** | 60% | 95% | 35pp |
| **安全性** | JWT + HTTPS | mTLS + Vault | - |
| **开发效率** | - | BFF减少前端请求 | 30% |

### 10.2 业务收益

- ✅ 支持更大规模用户（10x扩展能力）
- ✅ 更快响应速度（P95延迟降低30%）
- ✅ 更高可用性（99.9% → 99.95%）
- ✅ 更低运维成本（自动化运维）
- ✅ 更快迭代速度（独立服务部署）

---

## 11. 总结

本迁移计划包含：

- ✅ **12周**完整迁移周期
- ✅ **70人周**人力投入
- ✅ **5个阶段**渐进式迁移
- ✅ **12个服务**重构或新建
- ✅ **完整回滚计划**保障安全
- ✅ **详细验收标准**确保质量

**关键成功因素**:
1. 充分的测试和验证
2. 分阶段渐进式迁移
3. 保持原架构并行运行
4. 快速回滚能力
5. 团队培训和文档完善

**下一步行动**:
1. 评审本迁移计划
2. 搭建开发环境
3. 启动阶段一基础设施准备

