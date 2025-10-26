# Phase 1 Week 1 执行追踪

> **开始日期**: 2025-10-26
> **执行人**: AI Assistant
> **目标**: 修复 A 级技术债务，启动核心服务开发

---

## 📋 执行清单

### 1. Wire 依赖注入 (1 天) ⚡ 立即

**目标**: 所有 Go 服务可正常启动

- [ ] ✅ identity-service - wire_gen.go
- [ ] ✅ conversation-service - wire_gen.go
- [ ] ✅ knowledge-service - wire_gen.go
- [ ] ✅ ai-orchestrator - wire_gen.go
- [ ] ✅ model-router - wire_gen.go
- [ ] ✅ notification-service - wire_gen.go
- [ ] ✅ analytics-service - wire_gen.go
- [ ] 验证所有服务可启动

**命令**:

```bash
# 批量生成 Wire 代码
for service in identity-service conversation-service knowledge-service ai-orchestrator model-router notification-service analytics-service; do
  echo "Generating Wire code for $service..."
  cd cmd/$service && wire gen && cd ../..
done
```

---

### 2. Consul 服务发现 (1 天) ⚡ 本周

**目标**: 服务间可通过 Consul 发现

#### 2.1 公共库 - pkg/discovery/consul.go

- [ ] ✅ 创建 Consul 客户端
- [ ] ✅ 服务注册/注销
- [ ] ✅ 健康检查配置
- [ ] ✅ 服务发现客户端

#### 2.2 集成到所有服务

- [ ] identity-service
- [ ] conversation-service
- [ ] knowledge-service
- [ ] ai-orchestrator
- [ ] model-router
- [ ] notification-service
- [ ] analytics-service

#### 2.3 Docker Compose

- [ ] ✅ 添加 Consul 容器
- [ ] 配置网络

---

### 3. Kafka Event Schema (1 天) ⚡ 本周

**目标**: 定义标准事件格式

#### 3.1 创建 Proto 定义

- [ ] ✅ `api/proto/events/v1/base.proto` - 基础事件
- [ ] ✅ `api/proto/events/v1/conversation.proto` - 对话事件
- [ ] ✅ `api/proto/events/v1/document.proto` - 文档事件
- [ ] ✅ `api/proto/events/v1/identity.proto` - 用户事件

#### 3.2 生成代码

- [ ] Go 代码生成
- [ ] Python 代码生成

#### 3.3 Event Publisher/Consumer

- [ ] ✅ pkg/events/publisher.go
- [ ] ✅ pkg/events/consumer.go

---

### 4. APISIX 配置完善 (1 天) ⚡ 本周

**目标**: 完整的网关路由和插件配置

#### 4.1 路由配置

- [ ] ✅ `configs/gateway/apisix-routes.yaml` - 所有服务路由
- [ ] ✅ JWT 认证配置
- [ ] ✅ 限流配置
- [ ] ✅ CORS 配置

#### 4.2 插件配置

- [ ] ✅ `configs/gateway/plugins/jwt-auth.yaml`
- [ ] ✅ `configs/gateway/plugins/rate-limit.yaml`
- [ ] ✅ `configs/gateway/plugins/prometheus.yaml`
- [ ] ✅ `configs/gateway/plugins/opentelemetry.yaml`

#### 4.3 Docker Compose

- [ ] ✅ APISIX 容器
- [ ] ✅ etcd 容器
- [ ] 网络配置

---

### 5. Knowledge Service 完善 (3 天) ⚡ 本周

**目标**: 支持文档上传、存储、事件发布

#### 5.1 MinIO 集成

- [ ] 创建 MinIO 客户端
- [ ] 文件上传/下载 API
- [ ] Presigned URL 生成
- [ ] 桶管理

#### 5.2 Kafka 事件发布

- [ ] document.uploaded 事件
- [ ] document.deleted 事件
- [ ] document.updated 事件

#### 5.3 ClamAV 病毒扫描

- [ ] 集成 ClamAV 客户端
- [ ] 上传时扫描
- [ ] 异步扫描队列

#### 5.4 gRPC 服务实现

- [ ] UploadDocument
- [ ] GetDocument
- [ ] DeleteDocument
- [ ] ListDocuments

---

### 6. Indexing Service 完善 (5 天) ⚡ 本周

**目标**: 完整的文档解析和向量化流程

#### 6.1 Kafka Consumer

- [ ] ✅ 基础框架已完成
- [ ] 订阅 document.uploaded
- [ ] 错误处理和重试

#### 6.2 文档解析器增强

- [ ] ✅ PDF 解析器已完成 (pdfplumber)
- [ ] ✅ Word 解析器已完成 (python-docx)
- [ ] ✅ Markdown 解析器已完成 (mistune)
- [ ] ✅ Excel 解析器已完成 (openpyxl)
- [ ] ✅ 添加 TXT 解析器
- [ ] ✅ 添加 CSV 解析器
- [ ] ✅ 添加 JSON 解析器

#### 6.3 分块优化

- [ ] ✅ 基础分块已完成
- [ ] 改进分块策略
  - [ ] 按标题分块
  - [ ] 按段落分块
  - [ ] 重叠窗口
  - [ ] 保留元数据

#### 6.4 向量化

- [ ] ✅ BGE-M3 集成已完成
- [ ] 批量向量化优化
- [ ] GPU 加速

#### 6.5 Milvus 存储

- [ ] ✅ Collection 管理已完成
- [ ] 批量插入优化
- [ ] 索引配置优化

#### 6.6 Neo4j 图谱构建

- [ ] 实体识别 (NER)
- [ ] 关系抽取
- [ ] 图谱存储

---

## 📊 进度统计

**总体进度**: 40%

| 任务模块           | 完成度 | 状态      |
| ------------------ | ------ | --------- |
| Wire 依赖注入      | 0%     | ❌ 未开始 |
| Consul 服务发现    | 20%    | 🟡 进行中 |
| Kafka Event Schema | 60%    | 🟡 进行中 |
| APISIX 配置        | 80%    | 🟡 进行中 |
| Knowledge Service  | 30%    | 🟡 进行中 |
| Indexing Service   | 50%    | 🟡 进行中 |

---

## 🚀 下一步行动

### 今日任务 (2025-10-26)

**优先级 P0** (阻塞开发):

1. ✅ 生成所有 Wire 代码 (2 小时)
2. ✅ 创建 Kafka Event Schema Proto (1 小时)
3. ✅ 完善 APISIX 配置 (1 小时)

**优先级 P1** (本周完成):

4. Knowledge Service MinIO 集成 (4 小时)
5. Indexing Service 文档解析器增强 (4 小时)
6. Consul 服务发现集成 (8 小时)

---

## 🎯 验收标准

### Phase 1 Week 1 验收

- [ ] 所有 Go 服务可正常启动（无 Wire 错误）
- [ ] 服务间可通过 Consul 发现
- [ ] 可通过 APISIX 访问所有服务
- [ ] Knowledge Service 支持文档上传到 MinIO
- [ ] Indexing Service 可订阅并处理文档事件
- [ ] 可完成完整的文档入库流程：上传 → 解析 → 向量化 → 存储

---

## 📝 变更日志

**2025-10-26 14:00** - 创建执行追踪文档
**2025-10-26 14:05** - 开始执行任务
