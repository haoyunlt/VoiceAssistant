# VoiceAssistant - AI 客服与语音助手平台

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.25+-blue.svg)](https://kubernetes.io/)
[![Istio](https://img.shields.io/badge/istio-1.19+-blue.svg)](https://istio.io/)
[![Go](https://img.shields.io/badge/go-1.21+-blue.svg)](https://golang.org/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

AI 客服与语音助手平台，基于微服务架构，集成 LangChain、LangGraph、RAG、多智能体协作等先进技术。

## ✨ 核心特性

### 🎯 智能对话

- **多模态交互**: 支持文本、语音、图片多种输入方式
- **上下文理解**: 基于对话历史的智能上下文管理
- **意图识别**: 精准识别用户意图和情感
- **个性化回复**: 根据用户画像定制化回复策略

### 🤖 AI 能力

- **ReAct/Plan-Execute 智能体**: 复杂任务自动分解和执行
- **工具调用**: 支持外部 API 和工具集成
- **多智能体协作**: 协同完成复杂业务场景
- **Self-RAG**: 自我验证的检索增强生成

### 🔍 知识检索

- **混合检索**: 向量检索 + BM25 关键词检索
- **智能重排**: LLM-based 精排提升检索质量
- **语义分块**: 智能文档切分保证语义完整性
- **知识图谱**: 实体关系提取和推理

### 🎙️ 语音处理

- **实时 ASR**: 低延迟语音识别（< 300ms TTFB）
- **情感 TTS**: 支持多种情感和语气
- **VAD 检测**: 精准的语音活动检测
- **流式处理**: WebSocket 实时双向通信

### 🏗️ 架构优势

- **微服务**: 松耦合、可独立扩展
- **服务网格**: Istio 提供流量管理和安全
- **云原生**: Kubernetes 容器编排
- **可观测性**: 全链路追踪、指标、日志

## 🏛️ 系统架构

```
┌─────────────┐
│   客户端     │
│ Web/Mobile  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│      Istio Gateway (入口网关)        │
│  • 流量路由  • 安全认证  • 限流熔断  │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
    ▼                     ▼
┌─────────┐         ┌─────────┐
│ Go 服务  │         │ Python  │
│ • 认证   │         │ AI 服务 │
│ • 对话   │◄───────►│ • Agent │
│ • 知识   │         │ • RAG   │
│ • 编排   │         │ • 语音  │
└────┬────┘         └────┬────┘
     │                   │
     └────────┬──────────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
┌──────────┐      ┌──────────┐
│ 存储层    │      │ 外部服务  │
│ • PG     │      │ • LLM    │
│ • Redis  │      │ • Azure  │
│ • Milvus │      │  Speech  │
│ • ES     │      └──────────┘
└──────────┘
```

详细架构图请查看：[架构概览](docs/arch/overview.md)

## 🚀 快速开始

### 前置要求

- **Kubernetes** 1.25+
- **kubectl** 配置完成
- **Helm** 3.0+（可选）
- 集群资源：3+ 节点，每节点 8 核 CPU / 16 GB 内存

### 一键部署

```bash
# 克隆项目
git clone https://github.com/haoyunlt/VoiceAssistant.git
cd VoiceAssistant

# 执行部署脚本
chmod +x scripts/deploy-k8s.sh
./scripts/deploy-k8s.sh

# 等待所有服务就绪（约 5-10 分钟）
kubectl get pods -n voiceassistant-prod -w
```

### 验证部署

```bash
# 查看服务状态
kubectl get all -n voiceassistant-prod

# 获取访问地址
export INGRESS_HOST=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "API Gateway: http://${INGRESS_HOST}"

# 健康检查
curl http://${INGRESS_HOST}/health
```

### 访问监控

```bash
# 启动所有监控面板
./scripts/monitoring-dashboard.sh all

# 访问地址
# Grafana:    http://localhost:3000 (admin/admin)
# Kiali:      http://localhost:20001
# Jaeger:     http://localhost:16686
# Prometheus: http://localhost:9090
# Nacos:      http://localhost:8848 (nacos/nacos)
```

## 📁 项目结构

```
VoiceAssistant/
├── algo/                      # Python AI 算法服务
│   ├── agent-engine/          # 智能体引擎
│   ├── rag-engine/            # RAG 检索增强
│   ├── voice-engine/          # 语音处理
│   ├── model-adapter/         # LLM 模型适配
│   ├── retrieval-service/     # 检索服务
│   ├── indexing-service/      # 索引服务
│   ├── multimodal-engine/     # 多模态引擎
│   ├── vector-store-adapter/  # 向量存储适配
│   └── knowledge-service/     # 知识服务
│
├── cmd/                       # Go 微服务
│   ├── identity-service/      # 认证授权
│   ├── conversation-service/  # 对话管理
│   ├── knowledge-service/     # 知识管理
│   ├── ai-orchestrator/       # AI 编排
│   ├── model-router/          # 模型路由
│   ├── notification-service/  # 通知服务
│   └── analytics-service/     # 分析服务
│
├── api/                       # API 定义
│   ├── proto/                 # gRPC Protocol Buffers
│   └── openapi.yaml           # REST API 规范
│
├── deployments/               # 部署配置
│   ├── k8s/                   # Kubernetes 配置
│   │   ├── istio/             # Istio 服务网格
│   │   ├── services/          # 应用服务
│   │   └── infrastructure/    # 基础设施
│   ├── helm/                  # Helm Charts
│   └── docker/                # Docker Compose
│
├── pkg/                       # Go 共享包
│   ├── auth/                  # 认证
│   ├── cache/                 # 缓存
│   ├── database/              # 数据库
│   ├── middleware/            # 中间件
│   └── observability/         # 可观测性
│
├── scripts/                   # 运维脚本
│   ├── deploy-k8s.sh          # K8s 部署
│   ├── monitoring-dashboard.sh # 监控面板
│   └── backup-restore.sh      # 备份恢复
│
├── docs/                      # 文档
│   ├── arch/                  # 架构设计
│   ├── runbook/               # 运维手册
│   └── nfr/                   # 非功能需求
│
└── tests/                     # 测试
    ├── unit/                  # 单元测试
    ├── integration/           # 集成测试
    └── e2e/                   # 端到端测试
```

## 🔧 技术栈

### 后端框架

- **Go**: Gin (HTTP), gRPC, Wire (DI)
- **Python**: FastAPI, LangChain, LangGraph

### AI/ML

- **LLM**: OpenAI GPT-4, Claude, 通义千问, 文心一言
- **Embedding**: BGE-large-zh-v1.5, OpenAI Embeddings
- **Speech**: Azure Speech Services

### 数据存储

- **PostgreSQL**: 业务数据
- **Redis**: 缓存和会话
- **Milvus**: 向量数据库
- **Elasticsearch**: 全文搜索
- **ClickHouse**: 分析数据库
- **MinIO**: 对象存储

### 基础设施

- **Kubernetes**: 容器编排
- **Istio**: 服务网格
- **Nacos**: 配置中心
- **Kafka**: 消息队列

### 可观测性

- **Prometheus**: 指标收集
- **Grafana**: 可视化
- **Jaeger**: 分布式追踪
- **Alertmanager**: 告警管理

## 📊 性能指标

todo

## 🔐 安全特性

- **认证授权**: JWT + RBAC
- **服务间加密**: Istio mTLS
- **敏感数据**: PII 脱敏和加密
- **审计日志**: 操作审计和追踪
- **网络隔离**: Network Policy
- **密钥管理**: Kubernetes Secrets

## 📖 文档

### 核心文档

- [架构概览](docs/arch/overview.md) - 系统架构和组件说明
- [部署指南](deployments/k8s/README.md) - Kubernetes 部署手册
- [运维手册](docs/runbook/index.md) - 日常运维操作
- [SLO 目标](docs/nfr/slo.md) - 性能和可用性目标

### 服务文档

- [Agent Engine](algo/agent-engine/README.md) - 智能体引擎
- [RAG Engine](algo/rag-engine/RAG_ENHANCED_README.md) - 检索增强生成
- [Voice Engine](algo/voice-engine/README.md) - 语音处理
- [Nacos 集成](NACOS_INTEGRATION_SUMMARY.md) - 配置中心集成

### API 文档

- [gRPC API](api/proto/) - Protocol Buffers 定义
- [REST API](api/openapi.yaml) - OpenAPI 规范

## 🛠️ 开发

### 本地开发

```bash
# Go 服务
cd cmd/identity-service
go mod download
go run main.go

# Python 服务
cd algo/agent-engine
pip install -r requirements.txt
python main.py
```

### 运行测试

```bash
# Go 测试
go test ./...

# Python 测试
pytest tests/

# 集成测试
./scripts/test-services.sh
```

### 代码规范

- **Go**: golangci-lint
- **Python**: ruff, black
- **提交**: Conventional Commits

## 🔄 CI/CD

项目使用 GitHub Actions 进行持续集成和部署：

- **CI**: 代码检查、单元测试、构建镜像
- **CD**: 自动部署到开发/测试/生产环境
- **文档守卫**: 确保只有核心文档被提交

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request



## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。



## 🙏 致谢

感谢以下开源项目：

- [LangChain](https://github.com/langchain-ai/langchain)
- [Istio](https://istio.io/)
- [Kubernetes](https://kubernetes.io/)
- [Milvus](https://milvus.io/)
- 以及所有贡献者！

---

**⭐ 如果这个项目对你有帮助，请给我们一个 Star！**

**💬 有问题？欢迎在 [Issues](https://github.com/voiceassistant/VoiceAssistant/issues) 中提问！**
