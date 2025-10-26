# VoiceHelper 微服务架构 - 快速开始指南

> **版本**: v2.0.0  
> **最后更新**: 2025-10-26  
> **状态**: ✅ 开发中

---

## 📋 项目概述

VoiceHelper 是一个基于 DDD（领域驱动设计）和云原生最佳实践的 GraphRAG + Multi-Agent 语音助手平台。

### 核心特性
- ✅ 微服务架构 (Kratos + FastAPI)
- ✅ 事件驱动 (Kafka)
- ✅ gRPC 高性能通信
- ✅ GraphRAG 知识检索
- ✅ Multi-Agent 任务编排
- ✅ 实时语音对话
- ✅ 多模态理解
- ✅ 全链路可观测性 (OpenTelemetry)

---

## 🏗️ 架构概览

### 服务列表 (12个服务)

#### Go 微服务 (Kratos v2)
1. **Identity Service** - 用户认证、租户管理、权限控制
2. **Conversation Service** - 会话管理、消息路由、上下文维护
3. **Knowledge Service** - 文档管理、集合管理、版本控制
4. **AI Orchestrator** - AI 任务编排、流程控制、结果聚合
5. **Model Router** - 模型路由、成本优化、降级策略
6. **Notification Service** - 消息推送、邮件、Webhook
7. **Analytics Service** - 实时统计、报表生成、成本分析

#### Python 微服务 (FastAPI)
1. **Indexing Service** - 文档解析、向量化、图谱构建
2. **Retrieval Service** - 混合检索、重排序、语义缓存
3. **Agent Engine** - Agent 执行、工具调用、反思机制
4. **RAG Engine** - 检索增强生成、上下文生成
5. **Voice Engine** - ASR/TTS/VAD
6. **Multimodal Engine** - OCR/视觉理解
7. **Model Adapter** - API 适配、协议转换

---

## 🚀 快速启动

### 前置要求

- **Go**: v1.21+
- **Python**: v3.11+
- **Docker**: v24+
- **Docker Compose**: v2.20+
- **Node.js**: v18+ (前端)

### 本地开发环境

#### 1. 克隆项目
```bash
git clone https://github.com/yourusername/VoiceAssistant.git
cd VoiceAssistant
```

#### 2. 启动基础设施
```bash
# 启动 PostgreSQL, Redis, Kafka, MinIO, Neo4j, Milvus
docker-compose up -d

# 等待服务就绪
docker-compose ps
```

#### 3. 数据库初始化
```bash
# 创建 Schema 和表
psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/001_init_schema.sql
psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/002_identity_schema.sql
psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/003_conversation_schema.sql
psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/004_knowledge_schema.sql
```

#### 4. 启动 Go 服务

**Identity Service**:
```bash
cd cmd/identity-service
go run main.go wire.go

# 健康检查
curl http://localhost:8000/health
```

**Conversation Service**:
```bash
cd cmd/conversation-service
go run main.go

# 健康检查
curl http://localhost:8001/health
```

**Knowledge Service**:
```bash
cd cmd/knowledge-service
go run main.go

# 健康检查
curl http://localhost:8002/health
```

#### 5. 启动 Python 服务

**Indexing Service**:
```bash
cd algo/indexing-service
pip install -r requirements.txt
python main.py

# 健康检查
curl http://localhost:8010/health
```

**Retrieval Service**:
```bash
cd algo/retrieval-service
pip install -r requirements.txt
python main.py

# 健康检查
curl http://localhost:8011/health
```

#### 6. 启动前端
```bash
cd platforms/web
npm install
npm run dev

# 访问 http://localhost:3000
```

---

## 📚 目录结构

```
voicehelper/
├── cmd/                           # Go 微服务
│   ├── identity-service/          # 用户域
│   ├── conversation-service/      # 对话域
│   ├── knowledge-service/         # 知识域
│   ├── ai-orchestrator/           # AI 编排
│   ├── model-router/              # 模型路由
│   ├── notification-service/      # 通知域
│   └── analytics-service/         # 分析域
├── algo/                          # Python 算法服务
│   ├── indexing-service/          # 索引服务
│   ├── retrieval-service/         # 检索服务
│   ├── agent-engine/              # Agent 引擎
│   ├── rag-engine/                # RAG 引擎
│   ├── voice-engine/              # 语音引擎
│   ├── multimodal-engine/         # 多模态引擎
│   └── model-adapter/             # 模型适配器
├── api/                           # API 定义
│   ├── proto/                     # Protobuf 定义
│   └── openapi.yaml               # OpenAPI 规范
├── configs/                       # 配置文件
├── deployments/                   # 部署配置
│   ├── docker/                    # Dockerfile
│   ├── k8s/                       # Kubernetes YAML
│   └── helm/                      # Helm Charts
├── migrations/                    # 数据库迁移
├── platforms/                     # 前端平台
│   └── web/                       # Next.js Web 应用
├── docs/                          # 文档
└── docker-compose.yml             # 本地开发环境
```

---

## 🔧 开发指南

### Go 服务开发

#### 1. 创建新服务
```bash
# 使用 Kratos 脚手架
kratos new my-service

# 或手动创建目录结构
mkdir -p cmd/my-service/internal/{domain,biz,data,service,server,conf}
```

#### 2. 定义 Protobuf API
```protobuf
// api/proto/myservice/v1/myservice.proto
syntax = "proto3";
package myservice.v1;

service MyService {
  rpc GetUser(GetUserRequest) returns (User);
}
```

#### 3. 生成代码
```bash
make proto
```

#### 4. 实现业务逻辑
```go
// cmd/my-service/internal/biz/user.go
type UserUsecase struct {
    repo UserRepository
}

func (uc *UserUsecase) GetUser(ctx context.Context, id string) (*User, error) {
    return uc.repo.GetByID(ctx, id)
}
```

### Python 服务开发

#### 1. 创建 FastAPI 应用
```python
# algo/my-service/main.py
from fastapi import FastAPI

app = FastAPI(title="My Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

#### 2. 添加依赖
```bash
pip install fastapi uvicorn
pip freeze > requirements.txt
```

---

## 🧪 测试

### 单元测试
```bash
# Go 服务
cd cmd/identity-service
go test ./... -v -cover

# Python 服务
cd algo/indexing-service
pytest
```

### 集成测试
```bash
make integration-test
```

### 压力测试 (k6)
```bash
k6 run tests/load/k6/conversation.js
```

---

## 📦 部署

### Docker 构建
```bash
# 构建 Go 服务镜像
docker build -t voicehelper/identity-service:v2.0.0 \
  -f deployments/docker/Dockerfile.go-service \
  --build-arg SERVICE_NAME=identity-service .

# 构建 Python 服务镜像
docker build -t voicehelper/indexing-service:v2.0.0 \
  -f deployments/docker/Dockerfile.python-service \
  --build-arg SERVICE_NAME=indexing-service .
```

### Kubernetes 部署
```bash
# 使用 Helm
helm install identity-service deployments/helm/identity-service \
  --set image.tag=v2.0.0 \
  --namespace voicehelper-prod

# 检查状态
kubectl get pods -n voicehelper-prod
```

---

## 📊 可观测性

### Prometheus 指标
```bash
# 访问 Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# 查看指标
http://localhost:9090
```

### Jaeger 链路追踪
```bash
# 访问 Jaeger UI
kubectl port-forward -n observability svc/jaeger 16686:16686

# 查看追踪
http://localhost:16686
```

### Grafana Dashboard
```bash
# 访问 Grafana
kubectl port-forward -n monitoring svc/grafana 3000:80

# 默认账号: admin / admin
http://localhost:3000
```

---

## 📖 文档

- [架构设计 v2.0](docs/microservice-architecture-v2.md)
- [迁移清单](docs/migration-checklist.md)
- [迁移进度](docs/migration-progress.md)
- [API 总览](docs/api/API_OVERVIEW.md)
- [运维手册](docs/runbook/)

---

## 🤝 贡献指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 许可证

MIT License

---

## 联系方式

- **项目地址**: https://github.com/yourusername/VoiceAssistant
- **文档站点**: https://docs.voicehelper.ai
- **问题反馈**: https://github.com/yourusername/VoiceAssistant/issues

---

**最后更新**: 2025-10-26  
**版本**: v2.0.0  
**状态**: 🚧 开发中
