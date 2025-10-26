# VoiceHelper AI - 客服语音助手平台

<div align="center">

[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat&logo=go)](https://go.dev/)
[![Python Version](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**GraphRAG + Multi-Agent 驱动的云原生语音客服平台**

[English](README_EN.md) | [架构文档](docs/arch/microservice-architecture-v2.md) | [快速开始](#快速开始) | [API 文档](docs/api/API_OVERVIEW.md)

</div>

---

## 🎯 项目概述

VoiceHelper AI 是基于 **领域驱动设计（DDD）** 和 **云原生架构** 的企业级语音客服平台，采用：

- 🚀 **微服务架构**: Kratos (Go) + FastAPI (Python) 双栈实现
- 🤖 **AI 增强**: GraphRAG 知识检索 + LangGraph Multi-Agent 编排
- 📊 **实时数据**: Debezium CDC + Flink 流计算 + ClickHouse 分析
- 🔍 **向量检索**: Milvus 向量数据库 + 混合检索策略
- 🌐 **API 网关**: Apache APISIX 动态路由 + 灰度发布
- 📈 **可观测性**: OpenTelemetry + Prometheus + Jaeger + Grafana

---

## ✨ 核心特性

### 业务能力
- ✅ **多模态对话**: 语音 + 文本 + 图像理解
- ✅ **知识增强**: GraphRAG + 知识图谱 + 语义缓存
- ✅ **智能路由**: 多模型成本优化 + 自动降级
- ✅ **实时分析**: 对话质量 + 用户行为 + 成本监控

### 技术能力
- ✅ **高可用**: 99.95% SLA + 多副本 + 自动回滚
- ✅ **高性能**: P95 < 100ms + 1k+ RPS
- ✅ **弹性伸缩**: HPA + 金丝雀发布
- ✅ **安全合规**: JWT + RBAC + PII 脱敏 + 审计日志

---

## 📐 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      Apache APISIX Gateway                   │
│           (路由、限流、熔断、认证、追踪、监控)                 │
└────────────┬───────────────────────────┬────────────────────┘
             │                           │
    ┌────────▼──────────┐       ┌───────▼─────────┐
    │   Go 微服务层     │       │ Python AI 引擎   │
    │   (Kratos gRPC)   │       │  (FastAPI)       │
    ├───────────────────┤       ├──────────────────┤
    │ Identity Service  │       │ Agent Engine     │
    │ Conversation Svc  │       │ RAG Engine       │
    │ Knowledge Service │       │ Voice Engine     │
    │ AI Orchestrator   │       │ Retrieval Svc    │
    │ Model Router      │       │ Indexing Svc     │
    │ Notification Svc  │       │ Multimodal Eng   │
    │ Analytics Service │       │ Model Adapter    │
    └────────┬──────────┘       └───────┬──────────┘
             │                           │
             └────────────┬──────────────┘
                          │
         ┌────────────────▼───────────────────┐
         │       事件总线 (Kafka)             │
         │    + CDC (Debezium)                │
         │    + 流计算 (Flink)                │
         └────────────────┬───────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
┌───▼────┐  ┌──────▼──────┐  ┌────▼─────┐  ┌──▼───┐
│PostgreSQL│ │   Milvus    │  │ClickHouse│  │Neo4j│
│  (OLTP)  │ │  (向量检索)  │  │  (OLAP)  │  │(图谱)│
└──────────┘ └─────────────┘  └──────────┘  └─────┘
```

完整架构详见: [docs/arch/microservice-architecture-v2.md](docs/arch/microservice-architecture-v2.md)

---

## 🛠️ 技术栈

### 核心框架
| 组件 | 版本 | 语言 | 用途 |
|-----|------|------|------|
| [Kratos](https://go-kratos.dev/) | v2.7+ | Go | 微服务框架 |
| [FastAPI](https://fastapi.tiangolo.com/) | v0.110+ | Python | AI 服务框架 |
| [Next.js](https://nextjs.org/) | v14+ | TypeScript | Web 前端 |

### 基础设施
| 组件 | 版本 | 用途 |
|-----|------|------|
| [Apache APISIX](https://apisix.apache.org/) | v3.7+ | API 网关 |
| [Kubernetes](https://kubernetes.io/) | v1.28+ | 容器编排 |
| [Argo CD](https://argoproj.github.io/cd/) | v2.9+ | GitOps 部署 |
| [Kafka](https://kafka.apache.org/) | v3.6+ | 消息队列 |
| [Flink](https://flink.apache.org/) | v1.18+ | 流计算 |

### 数据存储
| 组件 | 版本 | 用途 |
|-----|------|------|
| PostgreSQL | v15+ | 关系型数据库 |
| [Milvus](https://milvus.io/) | v2.3+ | 向量数据库 |
| [ClickHouse](https://clickhouse.com/) | v23+ | 分析数据库 |
| [Neo4j](https://neo4j.com/) | v5+ | 知识图谱 |
| Redis | v7+ | 缓存 |
| MinIO | Latest | 对象存储 |

### 可观测性
| 组件 | 版本 | 用途 |
|-----|------|------|
| [OpenTelemetry](https://opentelemetry.io/) | v1.21+ | 遥测数据采集 |
| Prometheus | v2.48+ | 指标监控 |
| Jaeger | v1.52+ | 分布式追踪 |
| Grafana | v10+ | 可视化 |

---

## 🚀 快速开始

### 前置要求

- **开发工具**: Go 1.21+, Python 3.11+, Node.js 20+, Docker, Kubernetes
- **数据库**: PostgreSQL 15+, Redis 7+
- **基础设施**: Kafka, Milvus, ClickHouse（本地使用 docker-compose）

### 本地开发环境

#### 1. 克隆仓库
```bash
git clone https://github.com/voicehelper/voiceassistant.git
cd voiceassistant
```

#### 2. 启动基础设施
```bash
# 启动所有依赖服务（PostgreSQL, Redis, Kafka, Milvus, etc.）
make dev-up

# 查看服务状态
docker-compose ps

# 查看日志
make dev-logs
```

#### 3. 初始化数据库
```bash
# 运行数据库迁移
make migrate-up
```

#### 4. 生成 Protobuf 代码
```bash
make proto-gen
```

#### 5. 启动微服务（开发模式）

**启动 Go 服务:**
```bash
# 以 identity-service 为例
cd cmd/identity-service
go run .
```

**启动 Python 服务:**
```bash
# 以 agent-engine 为例
cd algo/agent-engine
pip install -e .
uvicorn main:app --reload --port 8001
```

**启动前端:**
```bash
cd platforms/web
npm install
npm run dev
```

#### 6. 访问服务

- **API Gateway**: http://localhost:9080
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger UI**: http://localhost:16686
- **Prometheus**: http://localhost:9090
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

---

## 📚 目录结构

```
voiceassistant/
├── cmd/                    # Go 微服务入口
│   ├── identity-service/
│   ├── conversation-service/
│   ├── knowledge-service/
│   ├── ai-orchestrator/
│   ├── model-router/
│   ├── notification-service/
│   └── analytics-service/
├── algo/                   # Python AI 服务
│   ├── agent-engine/
│   ├── rag-engine/
│   ├── voice-engine/
│   ├── retrieval-service/
│   ├── indexing-service/
│   ├── multimodal-engine/
│   └── model-adapter/
├── internal/               # Go 内部包
├── pkg/                    # Go 公共库
├── api/                    # API 定义（Proto + OpenAPI）
├── platforms/              # 前端平台
│   ├── web/               # Next.js Web
│   └── admin/             # 管理后台
├── deployments/            # 部署配置
│   ├── docker/
│   ├── k8s/
│   ├── helm/
│   └── argocd/
├── configs/                # 配置文件
├── migrations/             # 数据库迁移
├── scripts/                # 脚本
├── tests/                  # 测试
├── docs/                   # 文档
├── flink-jobs/             # Flink 任务
├── go.mod
├── pyproject.toml
├── Makefile
└── docker-compose.yml
```

---

## 🧪 测试

### 单元测试
```bash
make test
```

### 集成测试
```bash
cd tests/integration
go test -v ./...
```

### E2E 测试
```bash
make e2e
```

### 压力测试
```bash
make load
```

---

## 📦 部署

### Kubernetes 部署

#### 1. 配置 kubectl
```bash
kubectl config use-context <your-cluster>
```

#### 2. 使用 Helm 部署
```bash
# 安装 identity-service
helm install identity-service \
  ./deployments/helm/identity-service \
  -n voicehelper-prod
```

#### 3. 使用 Argo CD（推荐）
```bash
# 应用所有 Argo CD 应用定义
kubectl apply -f deployments/argocd/
```

### GitOps 工作流

1. 提交代码到 `main` 分支
2. CI 构建 Docker 镜像并推送到仓库
3. 更新 Helm Chart 版本
4. Argo CD 自动同步到 Kubernetes

详见: [docs/deployment/gitops.md](docs/deployment/gitops.md)

---

## 📊 监控与告警

### 核心指标

- **可用性**: 99.95% SLA
- **性能**: API Gateway P95 < 100ms
- **QPS**: 支持 1k+ RPS
- **错误率**: < 0.1%

### 监控面板

访问 Grafana (http://localhost:3000) 查看预置的监控面板：

- **服务概览**: 各服务 QPS、延迟、错误率
- **AI 性能**: LLM 调用、向量检索、Agent 执行
- **成本分析**: Token 消耗、模型成本
- **基础设施**: CPU、内存、网络

### 告警规则

告警配置详见: [configs/monitoring/prometheus/rules/](configs/monitoring/prometheus/rules/)

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交变更 (`git commit -m 'feat(scope): add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### Commit 规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type**: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

### PR 检查清单

- [ ] 代码已通过 lint
- [ ] 单元测试已通过（覆盖率 ≥ 70%）
- [ ] API 文档已更新
- [ ] 监控指标已添加
- [ ] Runbook 已更新

详见: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📖 文档

完整文档位于 [docs/](docs/) 目录:

### 架构设计
- [微服务架构 v2.0](docs/arch/microservice-architecture-v2.md)
- [领域驱动设计](docs/arch/ddd.md)
- [RAG 架构](docs/arch/rag.md)
- [Agent 架构](docs/arch/agent.md)

### API 文档
- [API 总览](docs/api/API_OVERVIEW.md)
- [gRPC Proto](docs/api/grpc/)
- [OpenAPI 规范](docs/api/openapi/)

### 运维手册
- [服务 Runbook](docs/runbook/)
- [故障排查](docs/troubleshooting/)
- [性能优化](docs/nfr/performance-optimization.md)

### 开发指南
- [本地开发环境](docs/development/local-setup.md)
- [代码规范](docs/development/coding-standards.md)
- [测试策略](docs/development/testing.md)

---

## 📄 License

本项目采用 [Apache License 2.0](LICENSE) 许可证。

---

## 🙏 致谢

感谢以下开源项目:

- [Kratos](https://github.com/go-kratos/kratos) - Go 微服务框架
- [FastAPI](https://github.com/tiangolo/fastapi) - Python Web 框架
- [Apache APISIX](https://github.com/apache/apisix) - API 网关
- [Milvus](https://github.com/milvus-io/milvus) - 向量数据库
- [LangChain](https://github.com/langchain-ai/langchain) - AI 编排框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent 框架

---

## 📞 联系我们

- **问题反馈**: [GitHub Issues](https://github.com/voicehelper/voiceassistant/issues)
- **功能请求**: [GitHub Discussions](https://github.com/voicehelper/voiceassistant/discussions)
- **邮件**: dev@voicehelper.ai

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！**

Made with ❤️ by VoiceHelper Team

</div>

