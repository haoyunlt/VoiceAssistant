# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-26

### Added
- 🚀 完整的微服务架构（7 个 Go 服务 + 7 个 Python 服务）
- 🤖 GraphRAG + Multi-Agent 语音助手功能
- 📊 实时数据流处理（Debezium CDC + Flink）
- 🔍 向量检索（Milvus）+ 知识图谱（Neo4j）
- 🌐 Apache APISIX API 网关
- 📈 完整的可观测性（OpenTelemetry + Prometheus + Jaeger + Grafana）
- ☁️ Kubernetes + Helm + Argo CD GitOps 部署
- 🎨 Next.js 14 Web 前端
- 📚 完整的 API 文档（Proto + OpenAPI）
- 🧪 测试框架（单元测试 + 集成测试 + E2E 测试）
- 📦 Docker Compose 本地开发环境

### Architecture
- 基于 DDD 的领域驱动设计
- Kratos (Go) + FastAPI (Python) 双栈实现
- 事件驱动架构（Kafka）
- CQRS + Event Sourcing
- 多级缓存策略

### Technical Stack
- **框架**: Kratos v2.7+, FastAPI v0.110+, Next.js v14+
- **数据库**: PostgreSQL 15+, Milvus 2.3+, ClickHouse 23+, Neo4j 5+, Redis 7+
- **消息**: Kafka 3.6+, Debezium 2.5+
- **流计算**: Apache Flink 1.18+
- **网关**: Apache APISIX 3.7+
- **监控**: OpenTelemetry, Prometheus, Grafana, Jaeger
- **部署**: Kubernetes 1.28+, Helm 3.13+, Argo CD 2.9+

### Performance
- API Gateway P95 < 100ms
- gRPC P95 < 50ms
- 向量检索 P95 < 10ms
- 支持 1k+ RPS

### Security
- JWT + OAuth 2.0 认证
- RBAC 权限控制
- TLS 1.3 加密
- PII 数据脱敏
- 审计日志

## [1.0.0] - 2024-xx-xx

### Added
- 初始版本

[2.0.0]: https://github.com/voicehelper/voiceassistant/releases/tag/v2.0.0
[1.0.0]: https://github.com/voicehelper/voiceassistant/releases/tag/v1.0.0

