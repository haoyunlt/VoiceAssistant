# VoiceHelper 服务 TODO 跟踪器

> **最后更新**: 2025-10-26
> **总进度**: 25% 完成
> **预计剩余工时**: 170 天 (4 人团队: 8 周)

---

## 🎯 快速导航

| 服务                                             | 状态 | 完成度 | P0 任务 | P1 任务 | P2 任务 | 预计工时 |
| ------------------------------------------------ | ---- | ------ | ------- | ------- | ------- | -------- |
| [Gateway (APISIX)](#1-gateway-apisix)            | 🚧   | 40%    | 4       | 4       | 2       | 13 天    |
| [Identity Service](#2-identity-service)          | ✅   | 80%    | 3       | 3       | 2       | 17.5 天  |
| [Conversation Service](#3-conversation-service)  | ✅   | 75%    | 2       | 4       | 2       | 15 天    |
| [Knowledge Service](#4-knowledge-service)        | 🚧   | 30%    | 4       | 3       | 2       | 19 天    |
| [Indexing Service](#5-indexing-service)          | ❌   | 5%     | 6       | 0       | 0       | 10 天    |
| [Retrieval Service](#6-retrieval-service)        | ❌   | 5%     | 6       | 0       | 0       | 8 天     |
| [RAG Engine](#7-rag-engine)                      | ❌   | 5%     | 4       | 0       | 0       | 5 天     |
| [Agent Engine](#8-agent-engine)                  | ❌   | 15%    | 4       | 3       | 2       | 16 天    |
| [Voice Engine](#9-voice-engine)                  | ❌   | 10%    | 4       | 3       | 0       | 10 天    |
| [Model Router](#10-model-router)                 | ❌   | 10%    | 4       | 0       | 0       | 5 天     |
| [Model Adapter](#11-model-adapter)               | ❌   | 10%    | 6       | 0       | 0       | 6 天     |
| [Multimodal Engine](#12-multimodal-engine)       | ❌   | 10%    | 0       | 3       | 0       | 6 天     |
| [Notification Service](#13-notification-service) | ❌   | 10%    | 0       | 6       | 0       | 7 天     |
| [AI Orchestrator](#14-ai-orchestrator)           | ❌   | 5%     | 4       | 0       | 0       | 6 天     |
| [Analytics Service](#15-analytics-service)       | ❌   | 5%     | 0       | 4       | 0       | 5 天     |

**图例**:

- ✅ 基本完成 (>70%)
- 🚧 进行中 (30-70%)
- ❌ 未开始 (<30%)
- 🔥 P0 = 阻塞开发，立即完成
- ⭐ P1 = 重要功能，短期完成
- 💡 P2 = 优化增强，中期完成

---

## 1. Gateway (APISIX)

**状态**: 🚧 进行中
**完成度**: 40%
**负责人**: TBD
**预计工时**: 13 天

### 🔥 P0 任务 (4 天)

- [ ] **T1.1 完整路由配置** `[2天]` `#网关` `#路由`

  - **文件**: `configs/gateway/apisix-routes.yaml`
  - **内容**:
    - 配置 14 个服务的路由
    - 路径前缀规则: `/api/v1/{service}/*`
    - 上游配置: `{service}.voicehelper.svc.cluster.local:9000`
  - **验收标准**:
    - 所有服务路由正常
    - 路由规则测试通过
    - 文档更新完整

- [ ] **T1.2 JWT 认证插件** `[1天]` `#安全` `#认证`

  - **文件**: `configs/gateway/plugins/jwt-auth.yaml`
  - **依赖**: Vault 密钥配置
  - **内容**:
    - JWT secret 从 Vault 读取
    - 验证 user_id 和 tenant_id claims
    - 白名单路径配置 (登录、健康检查等)
  - **验收标准**:
    - JWT 验证正常
    - 未授权请求返回 401
    - 白名单路径可访问

- [ ] **T1.3 限流插件配置** `[1天]` `#限流` `#性能`
  - **文件**: `configs/gateway/plugins/rate-limit.yaml`
  - **内容**:
    - 用户级限流: 100 req/min
    - IP 级限流: 1000 req/min
    - 租户级限流: 10000 req/min
  - **验收标准**:
    - 限流正常工作
    - 超限返回 429
    - Redis 计数器正确

### ⭐ P1 任务 (6 天)

- [ ] **T1.4 Consul 服务发现** `[2天]` `#服务发现`

  - **依赖**: 所有服务注册到 Consul
  - **内容**:
    - 集成 APISIX Discovery 插件
    - 动态上游节点发现
    - 健康检查配置

- [ ] **T1.5 WebSocket 代理** `[1天]` `#实时通信`

  - **路由**: `/ws/*`
  - **上游**: conversation-service:8080
  - **配置**: websocket 插件

- [ ] **T1.6 gRPC 转码** `[2天]` `#协议转换`

  - **插件**: grpc-transcode
  - **Proto**: 所有服务的 proto 文件
  - **支持**: HTTP → gRPC 双向转换

- [ ] **T1.7 监控配置** `[1天]` `#监控`
  - **插件**: prometheus + opentelemetry
  - **指标**: QPS、延迟、错误率
  - **Dashboard**: Grafana 配置

### 💡 P2 任务 (3 天)

- [ ] **T1.8 灰度发布** `[2天]` `#部署`

  - **插件**: traffic-split
  - **策略**: 金丝雀发布 (5% → 20% → 50% → 100%)

- [ ] **T1.9 熔断器** `[1天]` `#容错`
  - **插件**: api-breaker
  - **配置**: 错误率 > 50% 触发熔断

---

## 2. Identity Service

**状态**: ✅ 基本完成
**完成度**: 80%
**负责人**: TBD
**预计工时**: 17.5 天

### 🔥 P0 任务 (2.5 天)

- [ ] **T2.1 生成 Wire 代码** `[0.5天]` `#依赖注入`

  - **命令**: `cd cmd/identity-service && wire gen`
  - **输出**: `wire_gen.go`
  - **验收**: 编译通过，依赖注入正常

- [ ] **T2.2 完善 Redis 缓存** `[1天]` `#缓存`

  - **文件**: `internal/data/cache.go`
  - **功能**:
    - 用户缓存 (TTL: 1h)
    - Token 缓存 (TTL: 24h)
    - 权限缓存 (TTL: 10min)
  - **验收**: 缓存命中率 > 80%

- [ ] **T2.3 Consul 服务注册** `[1天]` `#服务发现`
  - **文件**: `internal/server/registry.go`
  - **功能**: 自动注册、健康检查、优雅退出
  - **验收**: Consul UI 显示正常

### ⭐ P1 任务 (7 天)

- [ ] **T2.4 OAuth 2.0 集成** `[3天]` `#认证` `#OAuth`

  - **支持**: Google、GitHub、Microsoft
  - **流程**: Authorization Code Flow
  - **存储**: OAuth Token 关联

- [ ] **T2.5 审计日志增强** `[1天]` `#安全` `#审计`

  - **记录**: 所有操作 (登录、创建用户、修改权限)
  - **字段**: IP、User-Agent、操作时间、结果
  - **存储**: PostgreSQL + ClickHouse (长期)

- [ ] **T2.6 单元测试** `[3天]` `#测试`
  - **覆盖率**: 70%+
  - **文件**: `internal/biz/*_test.go`
  - **工具**: testify, gomock

### 💡 P2 任务 (8 天)

- [ ] **T2.7 MFA 多因素认证** `[3天]` `#安全` `#MFA`

  - **支持**: TOTP、SMS、邮箱
  - **库**: pquerna/otp

- [ ] **T2.8 SSO 单点登录** `[5天]` `#SSO`
  - **协议**: SAML 2.0、CAS
  - **集成**: LDAP

---

## 3. Conversation Service

**状态**: ✅ 基本完成
**完成度**: 75%
**负责人**: TBD
**预计工时**: 15 天

### 🔥 P0 任务 (3 天)

- [ ] **T3.1 Redis 上下文缓存** `[1天]` `#缓存`

  - **文件**: `internal/data/context_cache.go`
  - **功能**:
    - GetContext、SetContext、AppendMessage
    - 自动截断 (max_tokens: 4000)
  - **验收**: 上下文管理正常

- [ ] **T3.2 调用 AI Orchestrator** `[2天]` `#集成`
  - **文件**: `internal/infra/ai_client.go`
  - **功能**: ProcessMessage、StreamResponse
  - **协议**: gRPC
  - **验收**: 消息流程正常

### ⭐ P1 任务 (8 天)

- [ ] **T3.3 流式响应 (SSE)** `[2天]` `#流式` `#SSE`

  - **文件**: `internal/interface/http/stream_handler.go`
  - **路由**: `/api/v1/conversation/{id}/stream`
  - **格式**: `data: {JSON}\n\n`

- [ ] **T3.4 WebSocket 支持** `[2天]` `#实时通信`

  - **文件**: `internal/interface/websocket/handler.go`
  - **功能**: 双向通信、连接池管理
  - **协议**: WebSocket + JSON

- [ ] **T3.5 会话分享** `[1天]` `#功能`

  - **文件**: `internal/biz/share_usecase.go`
  - **功能**: 创建分享链接、访问控制
  - **过期**: 可配置 (7 天、30 天、永久)

- [ ] **T3.6 单元测试** `[3天]` `#测试`
  - **覆盖率**: 70%+
  - **Mock**: Kafka、Redis、gRPC client

### 💡 P2 任务 (4 天)

- [ ] **T3.7 会话导出** `[2天]` `#功能`

  - **格式**: PDF、Markdown、JSON
  - **库**: wkhtmltopdf, gofpdf

- [ ] **T3.8 会话模板** `[2天]` `#功能`
  - **管理**: 创建、编辑、删除模板
  - **使用**: 从模板创建会话

---

## 4. Knowledge Service

**状态**: 🚧 进行中
**完成度**: 30%
**负责人**: TBD
**预计工时**: 19 天

### 🔥 P0 任务 (7 天)

- [ ] **T4.1 MinIO 集成** `[2天]` `#存储`

  - **文件**: `internal/infrastructure/storage/minio_client.go`
  - **功能**: Upload、Download、Delete、PresignedURL
  - **桶**: `voicehelper-documents`
  - **验收**: 文件操作正常

- [ ] **T4.2 文档上传流程** `[3天]` `#核心功能`

  - **文件**: `internal/application/document_service.go`
  - **流程**:
    1. 验证文件类型和大小
    2. 生成唯一文件名 (UUID)
    3. 病毒扫描
    4. 上传到 MinIO
    5. 保存元数据到 PostgreSQL
    6. 发布 Kafka 事件
  - **验收**: 完整流程测试通过

- [ ] **T4.3 ClamAV 病毒扫描** `[1天]` `#安全`

  - **文件**: `internal/infrastructure/security/virus_scanner.go`
  - **集成**: ClamAV TCP socket
  - **配置**: docker-compose.yml 中启动 ClamAV
  - **验收**: 能检测到测试病毒文件

- [ ] **T4.4 Kafka 事件发布** `[1天]` `#事件驱动`
  - **文件**: `internal/infrastructure/event/publisher.go`
  - **事件**:
    - document.uploaded
    - document.deleted
    - document.updated
  - **验收**: 事件正常发布到 Kafka

### ⭐ P1 任务 (7 天)

- [ ] **T4.5 版本管理** `[3天]` `#功能`

  - **表**: `knowledge.document_versions`
  - **功能**: 创建版本、获取版本、列出版本、对比版本
  - **存储**: 每个版本独立存储在 MinIO

- [ ] **T4.6 权限管理** `[2天]` `#权限`

  - **角色**: owner、editor、viewer
  - **功能**: 授权、撤销、检查权限
  - **集成**: Identity Service RBAC

- [ ] **T4.7 文档分享** `[2天]` `#功能`
  - **类型**: 公开链接、私有链接
  - **过期**: 可配置
  - **权限**: 只读、可下载

### 💡 P2 任务 (5 天)

- [ ] **T4.8 格式转换** `[3天]` `#格式转换`

  - **工具**: Pandoc
  - **支持**: PDF → Markdown, Word → Markdown, HTML → Markdown

- [ ] **T4.9 文档预览** `[2天]` `#预览`
  - **PDF**: pdf.js
  - **图片**: 直接显示
  - **Office**: LibreOffice 转 PDF

---

## 5. Indexing Service

**状态**: ❌ 未开始
**完成度**: 5%
**负责人**: TBD
**预计工时**: 10 天
**依赖**: Knowledge Service (T4.4)

### 🔥 P0 任务 (10 天)

- [ ] **T5.1 Kafka Consumer** `[1天]` `#事件驱动`

  - **文件**: `app/infrastructure/kafka_consumer.py`
  - **订阅**: document.events
  - **Group ID**: indexing-service
  - **验收**: 能接收到文档事件

- [ ] **T5.2 文档解析器** `[3天]` `#解析`

  - **文件**: `app/core/parsers/`
  - **支持**: PDF、Word、Markdown、Excel、PPT、HTML
  - **库**:
    - PDF: PyPDF2, pdfplumber
    - Word: python-docx
    - Excel: openpyxl
    - PPT: python-pptx
  - **验收**: 所有格式解析正常

- [ ] **T5.3 文档分块** `[1天]` `#分块`

  - **文件**: `app/core/chunker.py`
  - **库**: LangChain RecursiveCharacterTextSplitter
  - **参数**: chunk_size=500, chunk_overlap=50
  - **验收**: 分块结果合理

- [ ] **T5.4 向量化** `[2天]` `#向量化`

  - **文件**: `app/core/embedder.py`
  - **模型**: BGE-M3 (BAAI/bge-m3)
  - **库**: sentence-transformers
  - **批处理**: batch_size=32
  - **验收**: 向量质量高

- [ ] **T5.5 Milvus 集成** `[2天]` `#向量数据库`

  - **文件**: `app/infrastructure/milvus_client.py`
  - **Collection**: document_chunks
  - **Schema**: id, chunk_id, doc_id, content, embedding (1024 维), tenant_id, created_at
  - **索引**: HNSW (M=16, efConstruction=256)
  - **验收**: 向量插入和搜索正常

- [ ] **T5.6 Neo4j 图谱构建** `[2天]` `#知识图谱`
  - **文件**: `app/core/graph_builder.py`
  - **功能**:
    - 实体识别 (NER)
    - 关系抽取
    - 社区检测
  - **库**: spacy, networkx
  - **验收**: 图谱构建正常

---

## 6. Retrieval Service

**状态**: ❌ 未开始
**完成度**: 5%
**负责人**: TBD
**预计工时**: 8 天
**依赖**: Indexing Service (T5.5)

### 🔥 P0 任务 (8 天)

- [ ] **T6.1 Milvus 向量检索** `[1天]` `#检索`

  - **文件**: `app/core/vector_retriever.py`
  - **参数**: top_k=10, metric_type='IP'
  - **过滤**: tenant_id 标量过滤
  - **验收**: 检索准确率 > 80%

- [ ] **T6.2 BM25 检索** `[2天]` `#BM25`

  - **文件**: `app/core/bm25_retriever.py`
  - **库**: rank_bm25
  - **语料库**: 从 Milvus 加载所有文档
  - **验收**: BM25 分数合理

- [ ] **T6.3 图谱检索** `[2天]` `#图谱`

  - **文件**: `app/core/graph_retriever.py`
  - **功能**:
    - 按实体检索
    - 按关系检索
    - 社区检索
  - **深度**: 可配置 (1-3 层)
  - **验收**: 图谱查询正常

- [ ] **T6.4 混合检索 (RRF)** `[1天]` `#混合检索`

  - **文件**: `app/core/hybrid_retriever.py`
  - **融合**: RRF (Reciprocal Rank Fusion)
  - **权重**: 向量(0.5) + BM25(0.3) + 图谱(0.2)
  - **验收**: 混合检索效果优于单一方法

- [ ] **T6.5 重排序** `[1天]` `#重排`

  - **文件**: `app/core/reranker.py`
  - **模型**: Cross-Encoder (ms-marco-MiniLM-L-12-v2)
  - **输入**: Top 50 → 输出: Top 10
  - **验收**: 重排后相关性提升

- [ ] **T6.6 Redis 语义缓存** `[1天]` `#缓存`
  - **文件**: `app/infrastructure/semantic_cache.py`
  - **策略**: 查询向量相似度 > 0.95 命中缓存
  - **TTL**: 24h
  - **验收**: 缓存命中率 > 30%

---

## 7. RAG Engine

**状态**: ❌ 未开始
**完成度**: 5%
**负责人**: TBD
**预计工时**: 5 天
**依赖**: Retrieval Service (T6.4)

### 🔥 P0 任务 (5 天)

- [ ] **T7.1 查询改写** `[1天]` `#查询优化`

  - **文件**: `app/core/query_rewriter.py`
  - **方法**:
    - HyDE (Hypothetical Document Embeddings)
    - Multi-Query (生成多个相关查询)
    - Step-back Prompting
  - **验收**: 查询改写效果明显

- [ ] **T7.2 上下文构建** `[1天]` `#上下文`

  - **文件**: `app/core/context_builder.py`
  - **功能**:
    - 组装检索结果
    - 截断到 max_tokens (默认 4000)
    - 添加来源标记
  - **验收**: 上下文格式正确

- [ ] **T7.3 答案生成** `[2天]` `#生成`

  - **文件**: `app/core/answer_generator.py`
  - **模式**: 非流式 + 流式
  - **调用**: Model Router gRPC
  - **验收**: 答案质量高

- [ ] **T7.4 引用来源** `[1天]` `#引用`
  - **文件**: `app/core/citation_generator.py`
  - **格式**: [1] 文档名 (页码/位置)
  - **功能**: 自动匹配答案与来源
  - **验收**: 引用准确

---

## 8. Agent Engine

**状态**: ❌ 未开始
**完成度**: 15%
**负责人**: TBD
**预计工时**: 16 天

### 🔥 P0 任务 (8 天)

- [ ] **T8.1 LangGraph 工作流** `[3天]` `#核心`

  - **文件**: `app/core/agent/workflow.py`
  - **节点**: Planner → Executor → Reflector
  - **状态**: AgentState (任务、历史、工具调用)
  - **验收**: ReAct 模式正常工作

- [ ] **T8.2 工具注册表** `[2天]` `#工具`

  - **文件**: `app/core/tools/registry.py`
  - **内置工具** (50+):
    - Search (Google, Bing)
    - Calculator
    - CodeInterpreter
    - WebScraper
    - FileReader
    - DatabaseQuery
  - **验收**: 所有工具可调用

- [ ] **T8.3 工具调用系统** `[2天]` `#执行`

  - **文件**: `app/core/tools/executor.py`
  - **安全**:
    - 白名单检查
    - 参数验证
    - 超时控制 (30s)
  - **成本追踪**: 每次调用记录成本
  - **验收**: 工具调用安全可靠

- [ ] **T8.4 长期记忆** `[1天]` `#记忆`
  - **文件**: `app/core/memory/vector_memory.py`
  - **存储**: FAISS Index
  - **操作**: Add、Search、Decay
  - **验收**: 记忆检索正常

### ⭐ P1 任务 (5 天)

- [ ] **T8.5 MCP 集成** `[2天]` `#MCP`

  - **文件**: `app/core/tools/mcp_integration.py`
  - **协议**: Model Context Protocol
  - **功能**: 发现工具、调用工具

- [ ] **T8.6 记忆衰减** `[1天]` `#记忆`

  - **文件**: `app/core/memory/decay_manager.py`
  - **策略**: 时间衰减 (factor=0.9)
  - **清理**: 定期删除低分记忆

- [ ] **T8.7 对话历史** `[1天]` `#历史`

  - **文件**: `app/core/memory/conversation_history.py`
  - **功能**: Add、Get、Summarize
  - **压缩**: 自动总结长对话

- [ ] **T8.8 单元测试** `[1天]` `#测试`
  - **覆盖率**: 70%+
  - **Mock**: LLM、工具

### 💡 P2 任务 (3 天)

- [ ] **T8.9 多 Agent 协作** `[2天]` `#协作`

  - **模式**: Manager-Worker
  - **通信**: 消息传递

- [ ] **T8.10 Agent 可视化** `[1天]` `#可视化`
  - **工具**: LangGraph Studio
  - **功能**: 流程图、状态追踪

---

## 9. Voice Engine

**状态**: ❌ 未开始
**完成度**: 10%
**负责人**: TBD
**预计工时**: 10 天

### 🔥 P0 任务 (6 天)

- [ ] **T9.1 Whisper ASR** `[2天]` `#ASR`

  - **文件**: `app/core/asr/whisper_asr.py`
  - **模型**: Whisper Base/Medium
  - **模式**: 文件转写 + 流式转写
  - **语言**: 自动检测
  - **验收**: 转写准确率 > 95%

- [ ] **T9.2 Silero VAD** `[1天]` `#VAD`

  - **文件**: `app/core/vad/silero_vad.py`
  - **功能**: 检测语音活动片段
  - **阈值**: 可配置 (默认 0.5)
  - **验收**: VAD 准确率 > 90%

- [ ] **T9.3 Edge TTS** `[2天]` `#TTS`

  - **文件**: `app/core/tts/edge_tts.py`
  - **语音**: zh-CN-XiaoxiaoNeural (中文女声)
  - **模式**: 文件合成 + 流式合成
  - **验收**: 语音自然流畅

- [ ] **T9.4 WebRTC 集成** `[1天]` `#实时通信`
  - **文件**: `app/api/webrtc_handler.py`
  - **库**: aiortc
  - **功能**: Offer/Answer、音频轨道处理
  - **验收**: 实时通话正常

### ⭐ P1 任务 (4 天)

- [ ] **T9.5 说话人分离** `[2天]` `#分离`

  - **库**: pyannote.audio
  - **功能**: 识别不同说话人
  - **输出**: 每句话标记说话人 ID

- [ ] **T9.6 情感识别** `[1天]` `#情感`

  - **模型**: 中文情感分析模型
  - **输出**: 正面、负面、中性

- [ ] **T9.7 语音降噪** `[1天]` `#降噪`
  - **库**: noisereduce
  - **功能**: 去除背景噪音

---

## 10. Model Router

**状态**: ❌ 未开始
**完成度**: 10%
**负责人**: TBD
**预计工时**: 5 天

### 🔥 P0 任务 (5 天)

- [ ] **T10.1 路由决策引擎** `[2天]` `#路由`

  - **文件**: `internal/application/routing_service.go`
  - **策略**:
    - 成本优先 (最便宜模型)
    - 延迟优先 (最快模型)
    - 可用性优先 (健康模型)
  - **配置**: models.yaml
  - **验收**: 路由决策合理

- [ ] **T10.2 成本优化器** `[1天]` `#成本`

  - **文件**: `internal/application/cost_optimizer.go`
  - **功能**:
    - 计算每次调用成本
    - 选择最便宜模型
    - 成本预警
  - **验收**: 成本计算准确

- [ ] **T10.3 降级管理器** `[1天]` `#降级`

  - **文件**: `internal/application/fallback_manager.go`
  - **降级链**: GPT-4 → GPT-3.5 → Qianwen → 本地模型
  - **触发**: 错误、超时、限流
  - **验收**: 降级正常工作

- [ ] **T10.4 gRPC 服务实现** `[1天]` `#服务`
  - **API**: RouteModel、GetModelStatus
  - **集成**: Model Adapter gRPC client
  - **验收**: 服务正常运行

---

## 11. Model Adapter

**状态**: ❌ 未开始
**完成度**: 10%
**负责人**: TBD
**预计工时**: 6 天
**依赖**: Model Router

### 🔥 P0 任务 (6 天)

- [ ] **T11.1 OpenAI 适配器** `[1天]` `#适配器`

  - **文件**: `app/adapters/openai_adapter.py`
  - **模型**: GPT-4, GPT-3.5
  - **功能**: Chat、Stream、TokenCount
  - **验收**: OpenAI API 正常

- [ ] **T11.2 Claude 适配器** `[1天]` `#适配器`

  - **文件**: `app/adapters/claude_adapter.py`
  - **模型**: Claude 3 Opus/Sonnet
  - **库**: anthropic
  - **验收**: Claude API 正常

- [ ] **T11.3 Zhipu 适配器** `[1天]` `#适配器`

  - **文件**: `app/adapters/zhipu_adapter.py`
  - **模型**: GLM-4
  - **验收**: Zhipu API 正常

- [ ] **T11.4 协议转换器** `[1天]` `#转换`

  - **文件**: `app/core/protocol_converter.py`
  - **功能**: 统一消息格式 ↔ 各厂商格式
  - **验收**: 格式转换无损

- [ ] **T11.5 错误处理器** `[1天]` `#容错`

  - **文件**: `app/core/error_handler.py`
  - **功能**:
    - 统一错误码
    - 重试策略 (指数退避)
    - 超时控制
  - **验收**: 错误处理完善

- [ ] **T11.6 gRPC 服务** `[1天]` `#服务`
  - **API**: CallModel、StreamModel
  - **验收**: 服务正常运行

---

## 12. Multimodal Engine

**状态**: ❌ 未开始
**完成度**: 10%
**负责人**: TBD
**预计工时**: 6 天

### ⭐ P1 任务 (6 天)

- [ ] **T12.1 Paddle OCR** `[2天]` `#OCR`

  - **文件**: `app/core/ocr/paddle_ocr.py`
  - **功能**: 文本识别、表格识别
  - **语言**: 中英文
  - **验收**: OCR 准确率 > 95%

- [ ] **T12.2 GPT-4V 集成** `[2天]` `#视觉理解`

  - **文件**: `app/core/vision/gpt4v.py`
  - **功能**: 图像分析、实体提取
  - **验收**: 图像理解准确

- [ ] **T12.3 视频处理** `[2天]` `#视频`
  - **文件**: `app/core/video/analyzer.py`
  - **功能**: 帧提取、视频分析
  - **库**: opencv-python
  - **验收**: 视频处理正常

---

## 13. Notification Service

**状态**: ❌ 未开始
**完成度**: 10%
**负责人**: TBD
**预计工时**: 7 天

### ⭐ P1 任务 (7 天)

- [ ] **T13.1 邮件发送** `[1天]` `#邮件`

  - **文件**: `internal/infrastructure/channels/email.go`
  - **协议**: SMTP
  - **模板**: HTML + 纯文本

- [ ] **T13.2 短信发送** `[1天]` `#短信`

  - **文件**: `internal/infrastructure/channels/sms.go`
  - **提供商**: 阿里云、腾讯云

- [ ] **T13.3 Push 通知** `[2天]` `#推送`

  - **文件**: `internal/infrastructure/channels/push.go`
  - **支持**: FCM (Android), APNs (iOS)

- [ ] **T13.4 模板引擎** `[1天]` `#模板`

  - **文件**: `internal/application/template_service.go`
  - **语法**: Go template

- [ ] **T13.5 Kafka 消费者** `[1天]` `#事件驱动`

  - **订阅**: conversation.events, document.events

- [ ] **T13.6 RabbitMQ 任务队列** `[1天]` `#队列`
  - **用途**: 异步发送、重试机制

---

## 14. AI Orchestrator

**状态**: ❌ 未开始
**完成度**: 5%
**负责人**: TBD
**预计工时**: 6 天
**依赖**: Agent Engine, RAG Engine, Voice Engine

### 🔥 P0 任务 (6 天)

- [ ] **T14.1 任务路由器** `[2天]` `#路由`

  - **文件**: `internal/application/task_router.go`
  - **策略**: 根据任务类型路由到对应引擎
  - **类型**: agent, rag, voice, multimodal

- [ ] **T14.2 流程编排器** `[2天]` `#编排`

  - **文件**: `internal/application/orchestration_service.go`
  - **模式**: 串行、并行、条件分支
  - **DAG**: 支持复杂工作流

- [ ] **T14.3 结果聚合器** `[1天]` `#聚合`

  - **文件**: `internal/application/result_aggregator.go`
  - **功能**: 合并多引擎结果

- [ ] **T14.4 gRPC 服务** `[1天]` `#服务`
  - **API**: ExecuteTask, ExecuteWorkflow

---

## 15. Analytics Service

**状态**: ❌ 未开始
**完成度**: 5%
**负责人**: TBD
**预计工时**: 5 天
**依赖**: ClickHouse 数据流

### ⭐ P1 任务 (5 天)

- [ ] **T15.1 ClickHouse 客户端** `[1天]` `#数据库`

  - **文件**: `internal/infrastructure/clickhouse_client.go`
  - **库**: clickhouse-go

- [ ] **T15.2 实时指标查询** `[2天]` `#查询`

  - **文件**: `internal/application/metrics_service.go`
  - **指标**: 今日用量、7 天趋势、Top 10 租户

- [ ] **T15.3 报表生成** `[1天]` `#报表`

  - **文件**: `internal/application/report_service.go`
  - **类型**: 日报、月报

- [ ] **T15.4 gRPC 服务** `[1天]` `#服务`
  - **API**: GetUsage, GetTrend, GenerateReport

---

## 🎯 执行建议

### Week 1-2: P0 阻塞项 (关键路径)

**Go Team**:

- T1.1, T1.2, T1.3 (Gateway)
- T2.1, T2.2, T2.3 (Identity)
- T3.1, T3.2 (Conversation)

**Python Team**:

- T5.1-T5.6 (Indexing Service 完整)
- T6.1, T6.2 (Retrieval Service 部分)

### Week 3-4: P0 核心功能

**Go Team**:

- T4.1-T4.4 (Knowledge Service)
- T14.1-T14.4 (AI Orchestrator)

**Python Team**:

- T6.3-T6.6 (Retrieval Service 完成)
- T7.1-T7.4 (RAG Engine 完整)

### Week 5-6: P0 + P1 重要功能

**Go Team**:

- T10.1-T10.4 (Model Router)
- T13.1-T13.6 (Notification)

**Python Team**:

- T11.1-T11.6 (Model Adapter)
- T8.1-T8.4 (Agent Engine 核心)

### Week 7-8: P1 完善 + P2 优化

**Go Team**:

- T15.1-T15.4 (Analytics)
- T1.4-T1.7 (Gateway P1)
- T2.4-T2.6 (Identity P1)

**Python Team**:

- T9.1-T9.4 (Voice Engine 核心)
- T8.5-T8.8 (Agent Engine P1)
- T12.1-T12.3 (Multimodal)

---

## 📊 进度追踪

### 本周任务 (Week 1)

**优先级**: 🔥 P0

- [ ] T1.1 完整路由配置
- [ ] T1.2 JWT 认证插件
- [ ] T1.3 限流插件配置
- [ ] T4.1 MinIO 集成
- [ ] T4.2 文档上传流程
- [ ] T5.1 Kafka Consumer
- [ ] T5.2 文档解析器

**目标**: 打通文档上传 → 索引 → 检索完整链路

---

**最后更新**: 2025-10-26
**维护者**: VoiceHelper Team
**工具**: Jira, GitHub Projects, Notion
