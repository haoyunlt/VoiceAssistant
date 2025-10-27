# 第三方组件完整清单

> 生成日期: 2025-10-27
> 项目: VoiceAssistant - AI 客服与语音助手平台
> 版本: 2.0.0

## 📋 目录

- [基础设施组件](#基础设施组件)
- [Go 依赖](#go-依赖)
- [Python 依赖](#python-依赖)
- [前端依赖](#前端依赖)
- [监控与可观测性](#监控与可观测性)
- [云服务与外部 API](#云服务与外部-api)
- [许可证合规性](#许可证合规性)
- [版本管理策略](#版本管理策略)

---

## 🏗️ 基础设施组件

### 数据库

| 组件           | 版本        | 用途                               | 许可证             |
| -------------- | ----------- | ---------------------------------- | ------------------ |
| **PostgreSQL** | 15-alpine   | 主数据库（用户、对话、知识库）     | PostgreSQL License |
| **ClickHouse** | 23.8-alpine | 分析数据库（日志、指标、行为分析） | Apache 2.0         |
| **Milvus**     | v2.3.0      | 向量数据库（语义搜索、RAG）        | Apache 2.0         |
| **Redis**      | 7-alpine    | 缓存、会话存储                     | BSD 3-Clause       |

### 消息队列

| 组件             | 版本  | 用途             | 许可证     |
| ---------------- | ----- | ---------------- | ---------- |
| **Apache Kafka** | 3.7.0 | 事件流、异步消息 | Apache 2.0 |

### 对象存储

| 组件      | 版本   | 用途                          | 许可证   |
| --------- | ------ | ----------------------------- | -------- |
| **MinIO** | latest | S3 兼容对象存储（文件、模型） | AGPL 3.0 |

### 服务发现与配置

| 组件       | 版本     | 用途                 | 许可证     |
| ---------- | -------- | -------------------- | ---------- |
| **Nacos**  | v2.3.0   | 服务注册、配置中心   | Apache 2.0 |
| **etcd**   | v3.5.5   | Milvus 元数据存储    | Apache 2.0 |
| **Consul** | 通过 SDK | 服务发现（备选方案） | MPL 2.0    |

---

## 🔵 Go 依赖

### Web 框架 & HTTP

| 包名                  | 版本    | 用途           | Stars | 许可证       |
| --------------------- | ------- | -------------- | ----- | ------------ |
| **gin-gonic/gin**     | v1.11.0 | HTTP Web 框架  | 75k+  | MIT          |
| **go-kratos/kratos**  | v2.9.1  | 微服务框架     | 22k+  | MIT          |
| **gorilla/websocket** | v1.5.3  | WebSocket 支持 | 21k+  | BSD 2-Clause |

### 数据库 & ORM

| 包名                         | 版本    | 用途              | 许可证     |
| ---------------------------- | ------- | ----------------- | ---------- |
| **gorm.io/gorm**             | v1.31.0 | ORM 框架          | MIT        |
| **gorm.io/driver/postgres**  | v1.6.0  | PostgreSQL 驱动   | MIT        |
| **lib/pq**                   | v1.10.9 | PostgreSQL 驱动   | MIT        |
| **ClickHouse/clickhouse-go** | v2.28.3 | ClickHouse 客户端 | Apache 2.0 |

### 消息队列

| 包名                   | 版本    | 用途                   | 许可证 |
| ---------------------- | ------- | ---------------------- | ------ |
| **IBM/sarama**         | v1.46.3 | Kafka 客户端（生产者） | MIT    |
| **segmentio/kafka-go** | v0.4.47 | Kafka 客户端（消费者） | MIT    |

### 缓存 & 存储

| 包名               | 版本    | 用途                 | 许可证       |
| ------------------ | ------- | -------------------- | ------------ |
| **redis/go-redis** | v9.7.0  | Redis 客户端         | BSD 2-Clause |
| **go-redis/redis** | v8.11.5 | Redis 客户端（旧版） | BSD 2-Clause |
| **minio/minio-go** | v7.0.66 | MinIO 客户端         | Apache 2.0   |

### RPC & API

| 包名                            | 版本    | 用途             | 许可证       |
| ------------------------------- | ------- | ---------------- | ------------ |
| **google.golang.org/grpc**      | v1.75.0 | gRPC 框架        | Apache 2.0   |
| **google.golang.org/protobuf**  | v1.36.9 | Protocol Buffers | BSD 3-Clause |
| **grpc-ecosystem/grpc-gateway** | v2.27.2 | gRPC HTTP 网关   | BSD 3-Clause |

### 监控 & 可观测性

| 包名                                        | 版本    | 用途              | 许可证     |
| ------------------------------------------- | ------- | ----------------- | ---------- |
| **prometheus/client_golang**                | v1.19.1 | Prometheus 指标   | Apache 2.0 |
| **go.opentelemetry.io/otel**                | v1.38.0 | OpenTelemetry SDK | Apache 2.0 |
| **go.opentelemetry.io/otel/trace**          | v1.38.0 | 分布式追踪        | Apache 2.0 |
| **go.opentelemetry.io/otel/exporters/otlp** | v1.38.0 | OTLP 导出器       | Apache 2.0 |

### 配置管理

| 包名                         | 版本    | 用途          | 许可证     |
| ---------------------------- | ------- | ------------- | ---------- |
| **spf13/viper**              | v1.21.0 | 配置管理      | MIT        |
| **nacos-group/nacos-sdk-go** | v2.3.5  | Nacos 客户端  | Apache 2.0 |
| **hashicorp/consul/api**     | v1.29.4 | Consul 客户端 | MPL 2.0    |

### 认证 & 安全

| 包名                    | 版本    | 用途     | 许可证       |
| ----------------------- | ------- | -------- | ------------ |
| **golang-jwt/jwt**      | v5.2.2  | JWT 认证 | MIT          |
| **golang.org/x/crypto** | v0.43.0 | 加密算法 | BSD 3-Clause |

### 工具库

| 包名                  | 版本    | 用途            | 许可证       |
| --------------------- | ------- | --------------- | ------------ |
| **google/uuid**       | v1.6.0  | UUID 生成       | BSD 3-Clause |
| **google/wire**       | v0.6.0  | 依赖注入        | Apache 2.0   |
| **uber/automaxprocs** | v1.6.0  | 自动 GOMAXPROCS | MIT          |
| **uber/zap**          | v1.27.0 | 结构化日志      | MIT          |

### 分析 & A/B 测试

| 包名                   | 版本    | 用途         | 许可证 |
| ---------------------- | ------- | ------------ | ------ |
| **posthog/posthog-go** | v1.6.12 | PostHog 分析 | MIT    |

### 测试

| 包名                 | 版本    | 用途      | 许可证     |
| -------------------- | ------- | --------- | ---------- |
| **stretchr/testify** | v1.11.1 | 测试断言  | MIT        |
| **uber/mock**        | v0.5.0  | Mock 框架 | Apache 2.0 |

---

## 🐍 Python 依赖

### Web 框架

| 包名        | 版本    | 用途          | Stars | 许可证       |
| ----------- | ------- | ------------- | ----- | ------------ |
| **FastAPI** | 0.110.0 | 异步 Web 框架 | 72k+  | MIT          |
| **Uvicorn** | 0.27.0+ | ASGI 服务器   | 7.8k+ | BSD 3-Clause |

### AI & LLM

| 包名                    | 版本    | 用途                  | 许可证 |
| ----------------------- | ------- | --------------------- | ------ |
| **openai**              | 1.10.0+ | OpenAI API 客户端     | MIT    |
| **anthropic**           | 0.18.0+ | Claude API 客户端     | MIT    |
| **langchain**           | 0.1.0+  | LLM 应用框架          | MIT    |
| **langgraph**           | 0.0.20+ | Agent 工作流          | MIT    |
| **langchain-openai**    | 0.0.5+  | LangChain OpenAI 集成 | MIT    |
| **langchain-core**      | 0.1.12+ | LangChain 核心        | MIT    |
| **langchain-community** | 0.0.17+ | LangChain 社区集成    | MIT    |
| **tiktoken**            | 0.6.0   | OpenAI Token 计数     | MIT    |

### 向量数据库 & 搜索

| 包名                      | 版本   | 用途                 | 许可证     |
| ------------------------- | ------ | -------------------- | ---------- |
| **pymilvus**              | 2.3.0+ | Milvus Python 客户端 | Apache 2.0 |
| **sentence-transformers** | 2.5.1  | 句子嵌入、重排序     | Apache 2.0 |
| **rank-bm25**             | 0.2.2  | BM25 算法            | Apache 2.0 |

### 数据处理

| 包名                  | 版本   | 用途     | 许可证       |
| --------------------- | ------ | -------- | ------------ |
| **numpy**             | 1.26.3 | 数值计算 | BSD 3-Clause |
| **pydantic**          | 2.6.0+ | 数据验证 | MIT          |
| **pydantic-settings** | 2.1.0+ | 配置管理 | MIT          |

### HTTP 客户端

| 包名                 | 版本   | 用途             | 许可证       |
| -------------------- | ------ | ---------------- | ------------ |
| **httpx**            | 0.26.0 | 异步 HTTP 客户端 | BSD 3-Clause |
| **python-multipart** | 0.0.9  | 文件上传支持     | Apache 2.0   |

### 数据库客户端

| 包名                   | 版本   | 用途              | 许可证     |
| ---------------------- | ------ | ----------------- | ---------- |
| **redis**              | 5.0.0+ | Redis 客户端      | MIT        |
| **clickhouse-connect** | 0.6.0+ | ClickHouse 客户端 | Apache 2.0 |

### 流处理

| 包名        | 版本    | 用途             | 许可证     |
| ----------- | ------- | ---------------- | ---------- |
| **pyflink** | 1.18.0+ | Flink Python API | Apache 2.0 |

### 监控 & 可观测性

| 包名                                       | 版本   | 用途              | 许可证     |
| ------------------------------------------ | ------ | ----------------- | ---------- |
| **prometheus-client**                      | 0.19.0 | Prometheus 指标   | Apache 2.0 |
| **opentelemetry-api**                      | 1.21.0 | OpenTelemetry API | Apache 2.0 |
| **opentelemetry-sdk**                      | 1.21.0 | OpenTelemetry SDK | Apache 2.0 |
| **opentelemetry-instrumentation-fastapi**  | 0.42b0 | FastAPI 自动埋点  | Apache 2.0 |
| **opentelemetry-exporter-otlp-proto-grpc** | 1.21.0 | OTLP 导出器       | Apache 2.0 |

### 日志

| 包名       | 版本  | 用途         | 许可证 |
| ---------- | ----- | ------------ | ------ |
| **loguru** | 0.7.2 | 现代化日志库 | MIT    |

### 工具

| 包名                  | 版本  | 用途         | 许可证 |
| --------------------- | ----- | ------------ | ------ |
| **duckduckgo-search** | 4.1.1 | 搜索引擎工具 | MIT    |

### 开发工具

| 包名               | 版本    | 用途             | 许可证     |
| ------------------ | ------- | ---------------- | ---------- |
| **pytest**         | 7.4.0+  | 测试框架         | MIT        |
| **pytest-asyncio** | 0.21.0+ | 异步测试         | Apache 2.0 |
| **pytest-cov**     | 4.1.0+  | 代码覆盖率       | MIT        |
| **ruff**           | 0.1.0+  | 代码检查和格式化 | MIT        |
| **mypy**           | 1.7.0+  | 静态类型检查     | MIT        |
| **vulture**        | latest  | 死代码检测       | MIT        |

---

## ⚛️ 前端依赖

### 框架 & 核心

| 包名           | 版本   | 用途           | Stars | 许可证     |
| -------------- | ------ | -------------- | ----- | ---------- |
| **Next.js**    | 14.0.4 | React 框架     | 120k+ | MIT        |
| **React**      | 18.2.0 | UI 库          | 220k+ | MIT        |
| **React DOM**  | 18.2.0 | React DOM 渲染 | -     | MIT        |
| **TypeScript** | 5.3.3  | 类型系统       | 97k+  | Apache 2.0 |

### 状态管理

| 包名        | 版本  | 用途           | 许可证 |
| ----------- | ----- | -------------- | ------ |
| **Zustand** | 4.4.7 | 轻量级状态管理 | MIT    |

### UI & 样式

| 包名             | 版本    | 用途     | 许可证 |
| ---------------- | ------- | -------- | ------ |
| **Tailwind CSS** | 3.4.0   | CSS 框架 | MIT    |
| **Autoprefixer** | 10.4.16 | CSS 前缀 | MIT    |
| **PostCSS**      | 8.4.33  | CSS 处理 | MIT    |
| **lucide-react** | 0.303.0 | 图标库   | ISC    |

### Markdown & 代码高亮

| 包名                 | 版本  | 用途                     | 许可证 |
| -------------------- | ----- | ------------------------ | ------ |
| **react-markdown**   | 9.0.1 | Markdown 渲染            | MIT    |
| **remark-gfm**       | 4.0.0 | GitHub Flavored Markdown | MIT    |
| **rehype-highlight** | 7.0.0 | 代码高亮                 | MIT    |

### HTTP 客户端

| 包名      | 版本  | 用途      | 许可证 |
| --------- | ----- | --------- | ------ |
| **axios** | 1.6.5 | HTTP 请求 | MIT    |

### 可视化

| 包名            | 版本  | 用途                     | 许可证         |
| --------------- | ----- | ------------------------ | -------------- |
| **vis-network** | 9.1.9 | 网络图可视化（知识图谱） | Apache 2.0/MIT |
| **vis-data**    | 7.1.9 | 数据结构                 | Apache 2.0/MIT |

### 开发工具

| 包名                   | 版本   | 用途                | 许可证 |
| ---------------------- | ------ | ------------------- | ------ |
| **ESLint**             | 8.56.0 | 代码检查            | MIT    |
| **eslint-config-next** | 14.0.4 | Next.js ESLint 配置 | MIT    |

---

## 📊 监控与可观测性

### 监控平台

| 组件             | 版本   | 用途           | 许可证     |
| ---------------- | ------ | -------------- | ---------- |
| **Prometheus**   | latest | 指标采集与存储 | Apache 2.0 |
| **Grafana**      | latest | 可视化仪表盘   | AGPL 3.0   |
| **Jaeger**       | latest | 分布式追踪     | Apache 2.0 |
| **AlertManager** | latest | 告警管理       | Apache 2.0 |

### 服务网格（可选）

| 组件      | 版本     | 用途         | 许可证     |
| --------- | -------- | ------------ | ---------- |
| **Istio** | 通过 K8s | 服务网格     | Apache 2.0 |
| **Kiali** | latest   | Istio 可视化 | Apache 2.0 |

### 分析平台

| 组件        | 版本     | 用途               | 许可证 |
| ----------- | -------- | ------------------ | ------ |
| **PostHog** | 通过 SDK | 产品分析、A/B 测试 | MIT    |

---

## ☁️ 云服务与外部 API

### AI 服务

| 服务                      | 用途                  | 计费方式   |
| ------------------------- | --------------------- | ---------- |
| **OpenAI API**            | GPT 系列模型          | Token 计费 |
| **Anthropic Claude**      | Claude 系列模型       | Token 计费 |
| **Azure Speech Services** | 语音识别/合成（可选） | 使用量计费 |

### 云存储（可选）

| 服务           | 用途             | 计费方式  |
| -------------- | ---------------- | --------- |
| **阿里云 OSS** | 对象存储（备选） | 存储+流量 |
| **阿里云 KMS** | 密钥管理（备选） | API 调用  |

### 通知服务（可选）

| 服务           | 用途     | 计费方式 |
| -------------- | -------- | -------- |
| **阿里云短信** | SMS 发送 | 短信条数 |
| **阿里云邮件** | 邮件发送 | 邮件数量 |

---

## 📜 许可证合规性

### 许可证类型统计

| 许可证类型             | 数量 | 风险等级 | 说明                             |
| ---------------------- | ---- | -------- | -------------------------------- |
| **MIT**                | ~60  | ✅ 低    | 商业友好，无限制                 |
| **Apache 2.0**         | ~45  | ✅ 低    | 商业友好，需保留版权声明         |
| **BSD 3-Clause**       | ~15  | ✅ 低    | 商业友好，需保留版权声明         |
| **BSD 2-Clause**       | ~5   | ✅ 低    | 商业友好                         |
| **AGPL 3.0**           | 2    | ⚠️ 中    | MinIO, Grafana（网络服务需开源） |
| **MPL 2.0**            | 1    | ⚠️ 中    | Consul（修改需开源）             |
| **PostgreSQL License** | 1    | ✅ 低    | 类似 MIT                         |
| **ISC**                | 1    | ✅ 低    | 类似 MIT                         |

### 合规性建议

#### ✅ 低风险组件

- **MIT, Apache 2.0, BSD**: 可商用，需保留版权和许可证声明
- **建议**: 在应用的 LICENSES 文件中列出所有依赖

#### ⚠️ 中风险组件

**MinIO (AGPL 3.0)**

- 风险: 如果修改 MinIO 源码，需开源修改部分
- 缓解: 使用标准 MinIO Docker 镜像，不修改源码
- 备选: AWS S3, 阿里云 OSS, 腾讯云 COS

**Grafana (AGPL 3.0)**

- 风险: 如果作为 SaaS 提供需开源
- 缓解: 仅内部使用，或使用 Grafana Cloud
- 备选: Kibana, Metabase

**Consul (MPL 2.0)**

- 风险: 修改 Consul 源码需开源
- 缓解: 使用标准客户端 SDK，不修改源码
- 备选: Nacos, etcd

---

## 🔄 版本管理策略

### 固定版本策略

**生产环境** (当前采用):

- Go: 固定主版本号 (`v1.24.0`)
- Python: 固定小版本号 (`==0.110.0`)
- 前端: 使用插入符号 (`^14.0.4`)

### 升级策略

#### 定期审查

- **每季度**: 审查安全更新
- **每月**: 审查依赖更新
- **每周**: 审查 CVE 漏洞

#### 升级优先级

**P0 - 立即升级** (1-2 天)

- 严重安全漏洞 (CVSS >= 9.0)
- 影响核心功能的 Bug 修复

**P1 - 短期升级** (1-2 周)

- 中等安全漏洞 (CVSS 7.0-8.9)
- 性能改进
- 重要功能更新

**P2 - 长期升级** (季度评估)

- 小的功能增强
- 代码改进
- 非关键更新

### 依赖审计工具

| 工具            | 用途            | 频率     |
| --------------- | --------------- | -------- |
| `go mod verify` | Go 依赖校验     | 每次构建 |
| `pip-audit`     | Python 安全审计 | 每周     |
| `npm audit`     | 前端安全审计    | 每周     |
| Dependabot      | 自动 PR 更新    | 持续     |
| Snyk            | 漏洞扫描        | 每日     |

---

## 📈 依赖统计

### 总览

| 类别                | 数量  | 说明                         |
| ------------------- | ----- | ---------------------------- |
| **基础设施**        | 9     | 数据库、缓存、消息队列       |
| **Go 直接依赖**     | 37    | go.mod require               |
| **Go 间接依赖**     | 141   | go.mod require (indirect)    |
| **Python 核心依赖** | 14    | pyproject.toml               |
| **Python 开发依赖** | 5     | pyproject.toml dev           |
| **Python 服务依赖** | ~50   | requirements.txt (去重后)    |
| **前端依赖**        | 12    | package.json dependencies    |
| **前端开发依赖**    | 8     | package.json devDependencies |
| **云服务**          | 5     | 外部 API                     |
| **总计**            | ~280+ | 所有第三方组件               |

### 按语言分类

```
Go:        178 (63%)
Python:     69 (25%)
前端:       20 (7%)
基础设施:   14 (5%)
```

### 按类型分类

```
框架/库:     180 (64%)
基础设施:     14 (5%)
工具:         40 (14%)
监控:         15 (5%)
开发工具:     20 (7%)
云服务:        5 (2%)
其他:         10 (3%)
```

---

## 🔒 安全建议

### 1. 定期安全扫描

```bash
# Go 依赖安全扫描
go list -json -m all | nancy sleuth

# Python 依赖安全扫描
pip-audit

# 前端依赖安全扫描
npm audit

# 容器镜像扫描
trivy image voiceassistant:latest
```

### 2. 依赖最小化

- ✅ 已实施: 使用 Alpine 基础镜像
- ✅ 已实施: 多阶段构建
- 🔄 进行中: 移除未使用的依赖
- 📋 计划: 定期审查间接依赖

### 3. 供应链安全

- ✅ 使用 go.sum 和 package-lock.json
- ✅ 使用官方镜像源
- 📋 计划: 内部镜像仓库
- 📋 计划: SBOM 生成

---

## 📝 维护清单

### 每月

- [ ] 更新安全补丁
- [ ] 审查 Dependabot PR
- [ ] 运行完整的依赖审计
- [ ] 更新本文档

### 每季度

- [ ] 评估主要版本升级
- [ ] 审查许可证合规性
- [ ] 优化依赖树
- [ ] 评估新技术替代方案

### 每年

- [ ] 全面的依赖审查
- [ ] 技术栈评估
- [ ] 性能基准测试
- [ ] 成本优化分析

---

## 🔗 相关资源

### 内部文档

- [架构概览](docs/arch/overview.md)
- [部署指南](deployments/k8s/README.md)
- [代码审查报告](CODE_REVIEW_UNUSED_FUNCTIONS.md)

### 外部链接

- [Go 依赖文档](https://pkg.go.dev/)
- [PyPI 包索引](https://pypi.org/)
- [npm 注册表](https://www.npmjs.com/)

### 安全资源

- [CVE 数据库](https://cve.mitre.org/)
- [Snyk 漏洞数据库](https://snyk.io/vuln/)
- [GitHub Security Advisories](https://github.com/advisories)

---

**文档版本**: 1.0.0
**最后更新**: 2025-10-27
**维护者**: VoiceAssistant 技术团队
**审核周期**: 每月更新
