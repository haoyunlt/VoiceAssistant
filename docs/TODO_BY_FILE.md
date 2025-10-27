# TODO 按文件索引

> 方便开发者快速定位待完成功能
> 生成时间: 2025-10-27

---

## 📁 目录

- [Go 服务](#go服务)
- [Python 服务](#python服务)
- [共享模块](#共享模块)
- [Flink 作业](#flink作业)

---

## Go 服务

### cmd/identity-service/

#### internal/biz/auth_usecase.go:201

```go
// TODO: 实现 Token 黑名单机制（使用 Redis）
```

- **优先级**: P0
- **工作量**: 1 天
- **依赖**: Redis 配置
- **说明**: 用户登出后 Token 仍有效，存在安全风险

#### internal/biz/tenant_usecase.go:173

```go
// TODO: 检查租户下是否还有用户，如果有则不允许删除
```

- **优先级**: P0
- **工作量**: 0.5 天
- **依赖**: 无
- **说明**: 防止误删有数据的租户

#### internal/service/identity.go:22

```go
// TODO: Implement gRPC methods based on proto definition
```

- **优先级**: P1
- **工作量**: 1 天
- **依赖**: proto 定义
- **说明**: gRPC 接口实现

---

### cmd/knowledge-service/

#### internal/biz/document_usecase.go

```go
// Line 147: TODO: 实现事件补偿机制
// Line 209: TODO: 实现清理任务
// Line 229: TODO: 实现事件补偿机制
```

- **优先级**: P1
- **工作量**: 2 天
- **依赖**: 补偿框架选型
- **说明**: 确保事件最终一致性

---

### cmd/model-router/

#### main.go

```go
// Line 116: TODO: 实现路由逻辑
// Line 158: TODO: 从实际存储获取模型信息
// Line 172: TODO: 实际健康检查
```

- **优先级**: P0
- **工作量**: 2 天
- **依赖**: 路由策略设计
- **说明**: 智能路由和成本优化

#### internal/application/cost_optimizer.go:96

```go
// TODO: 发送告警
```

- **优先级**: P0
- **工作量**: 0.5 天
- **依赖**: 通知服务
- **说明**: 成本超标告警

---

### cmd/ai-orchestrator/

#### main.go:172

```go
// TODO: 实现流式响应
```

- **优先级**: P0
- **工作量**: 1-2 天
- **依赖**: SSE/WebSocket 实现
- **说明**: 提升用户体验，减少等待时间

---

### cmd/analytics-service/

#### internal/biz/report_usecase.go

```go
// Line 105: TODO: 实现使用报表生成逻辑
// Line 119: TODO: 实现成本报表生成逻辑
// Line 131: TODO: 实现模型报表生成逻辑
// Line 143: TODO: 实现用户报表生成逻辑
```

- **优先级**: P2
- **工作量**: 2-3 天
- **依赖**: ClickHouse 查询优化
- **说明**: 数据洞察和运营支撑

---

### pkg/middleware/

#### auth.go:30

```go
// TODO: Implement JWT validation
```

- **优先级**: P0
- **工作量**: 1 天
- **依赖**: 无
- **说明**: 网关统一鉴权

---

### pkg/events/

#### consumer.go:301

```go
// TODO: 添加延迟
```

- **优先级**: P1
- **工作量**: 0.5 天
- **依赖**: 无
- **说明**: 控制消费速率，保护下游

---

## Python 服务

### algo/voice-engine/

#### app/core/full_duplex_engine.py:205

```python
# TODO: 实际实现中需要停止音频播放
```

- **优先级**: P0
- **工作量**: 1 天
- **依赖**: 无
- **说明**: 全双工对话打断机制

#### app/core/tts_engine.py:347

```python
# TODO: 实现语音克隆（使用 YourTTS, Coqui TTS 等）
```

- **优先级**: P0
- **工作量**: 2-3 天
- **依赖**: TTS 模型选型
- **说明**: 个性化语音服务

#### app/core/asr_engine.py

(未找到具体 TODO，但需要完善流式识别)

#### main.py

```python
# Line 261: TODO: 实现降噪
# Line 264: TODO: 实现音频增强
```

- **优先级**: P0
- **工作量**: 2 天
- **依赖**: 音频处理库选型
- **说明**: 提升嘈杂环境识别率

#### app/services/tts_service.py

```python
# Line 69:  duration_ms=0,  # TODO: 计算实际音频时长
# Line 132: TODO: 实现 Azure Speech SDK 集成
# Line 194: TODO: 使用 Redis 缓存
# Line 199: TODO: 使用 Redis 缓存
```

- **优先级**: P0
- **工作量**: 2 天
- **依赖**: Azure 账号、Redis
- **说明**: 多厂商备份、成本优化

#### app/services/asr_service.py:190

```python
# TODO: 实现 Azure Speech SDK 集成
```

- **优先级**: P0
- **工作量**: 1 天
- **依赖**: Azure 账号
- **说明**: 多厂商备份

#### app/routers/asr.py:91

```python
# TODO: 实现流式识别
```

- **优先级**: P0
- **工作量**: 2 天
- **依赖**: 无
- **说明**: 实时对话核心功能

#### app/routers/health.py:25

```python
# TODO: 检查 ASR/TTS 模型加载状态
```

- **优先级**: P0
- **工作量**: 0.5 天
- **依赖**: 无
- **说明**: K8s 健康探测

---

### algo/agent-engine/

#### app/memory/memory_manager.py

```python
# Line 209: TODO: 实现基于向量相似度的检索
# Line 282: TODO: 实现向量存储
# Line 306: TODO: 实现向量检索
```

- **优先级**: P1
- **工作量**: 2-3 天
- **依赖**: 向量数据库
- **说明**: Agent 长期记忆能力

#### app/tools/tool_registry.py

```python
# Line 246: TODO: 实现真实的搜索功能
# Line 261: TODO: 实现真实的知识库搜索
# Line 267: TODO: 实现真实的天气API调用
```

- **优先级**: P1
- **工作量**: 3-4 天
- **依赖**: 各 API 接入
- **说明**: Agent 实际能力

#### app/workflows/react_agent.py:385

```python
# TODO: 实现流式输出
```

- **优先级**: P1
- **工作量**: 1 天
- **依赖**: 无
- **说明**: 实时显示推理过程

#### app/core/executor/plan_execute_executor.py:97

```python
# TODO: 实际应该解析步骤，调用工具
```

- **优先级**: P1
- **工作量**: 2-3 天
- **依赖**: 工具系统完善
- **说明**: 复杂任务规划

#### app/core/tools/builtin_tools.py

```python
# Line 34: TODO: 实际实现搜索功能（调用搜索引擎API）
# Line 65: TODO: 实际实现网页抓取
# Line 79: TODO: 实际实现文件读取（需要安全检查）
```

- **优先级**: P1
- **工作量**: 2 天
- **依赖**: API 接入
- **说明**: 内置工具实现

#### main.py:225

```python
# TODO: 实现动态工具注册
```

- **优先级**: P1
- **工作量**: 1-2 天
- **依赖**: 无
- **说明**: 工具扩展能力

#### routers/agent.py

```python
# Line 34: TODO: Implement agent execution logic using LangGraph
# Line 53: TODO: Implement status retrieval
```

- **优先级**: P1
- **工作量**: 1-2 天
- **依赖**: LangGraph 集成
- **说明**: Agent 路由入口

---

### algo/indexing-service/

#### app/core/entity_extractor.py:233

```python
# TODO: 实现 LLM 关系抽取
```

- **优先级**: P1
- **工作量**: 2-3 天
- **依赖**: LLM 服务
- **说明**: 知识图谱构建

#### app/kafka_consumer.py:281

```python
# 7. 发布索引完成事件（TODO: 需要 Kafka Producer）
```

- **优先级**: P1
- **工作量**: 1 天
- **依赖**: Kafka Producer 配置
- **说明**: 事件驱动通知

---

### algo/model-adapter/

#### (参考 README.md)

```markdown
| 智谱 AI (GLM) | 🔄 | 待实现 |
| 通义千问 (Qwen) | 🔄 | 待实现 |
| 百度文心 | 🔄 | 待实现 |
```

- **优先级**: P1
- **工作量**: 2-3 天
- **依赖**: API Key 申请
- **说明**: 国产模型支持

---

### algo/retrieval-service/

#### app/services/retrieval_service.py

```python
# Line 44:  TODO: 调用 embedding 服务获取向量
# Line 88:  TODO: 调用 embedding 服务获取向量
```

- **优先级**: P0
- **工作量**: 1 天
- **依赖**: Embedding 服务地址
- **说明**: 向量检索核心

#### app/core/bm25_retriever.py:37

```python
# TODO: 实际实现应该从 Milvus 或独立索引加载
```

- **优先级**: P0
- **工作量**: 1-2 天
- **依赖**: 存储方案选型
- **说明**: BM25 索引持久化

#### app/core/graph_retriever.py

```python
# Line 67: TODO: 实现 NER
# Line 82: TODO: 实现图谱查询
```

- **优先级**: P0
- **工作量**: 2-3 天
- **依赖**: Neo4j 集成
- **说明**: 知识图谱检索

#### app/core/reranker.py

```python
# Line 85: TODO: 初始化 LLM 客户端
# Line 96: TODO: 实现 LLM 重排序
```

- **优先级**: P0
- **工作量**: 1-2 天
- **依赖**: LLM 服务
- **说明**: 检索精度提升

#### app/routers/health.py:25

```python
# TODO: 检查 Milvus、Elasticsearch 连接
```

- **优先级**: P0
- **工作量**: 0.5 天
- **依赖**: 无
- **说明**: 健康探测

---

### algo/rag-engine/

#### app/core/rag_engine.py:246

```python
# TODO: 从 Conversation Service 获取历史
```

- **优先级**: P1
- **工作量**: 1 天
- **依赖**: Conversation Service API
- **说明**: 多轮对话上下文

---

### algo/multimodal-engine/

#### app/services/ocr_service.py:181

```python
# TODO: 实现 EasyOCR 集成
```

- **优先级**: P2
- **工作量**: 1 天
- **依赖**: EasyOCR 模型
- **说明**: OCR 备用方案

#### app/routers/health.py:25

```python
# TODO: 检查 OCR 模型加载状态
```

- **优先级**: P0
- **工作量**: 0.5 天
- **依赖**: 无
- **说明**: 健康探测

---

## Flink 作业

### flink-jobs/document-analysis/main.py:17

```python
# TODO: Implement document analysis
```

- **优先级**: P2
- **工作量**: 2 天
- **依赖**: Flink 环境
- **说明**: 文档质量分析

### flink-jobs/user-behavior/main.py:17

```python
# TODO: Implement user behavior analysis
```

- **优先级**: P2
- **工作量**: 2 天
- **依赖**: Flink 环境
- **说明**: 用户画像

### flink-jobs/message-stats/main.py

```python
# Line 65: TODO: Implement windowing and aggregation
# Line 72: TODO: Sink to ClickHouse
```

- **优先级**: P2
- **工作量**: 1-2 天
- **依赖**: ClickHouse 集成
- **说明**: 实时统计

---

## 📊 按目录统计

| 目录                    | TODO 数 | P0  | P1  | P2  |
| ----------------------- | ------- | --- | --- | --- |
| algo/voice-engine/      | 10      | 10  | 0   | 0   |
| algo/agent-engine/      | 12      | 0   | 12  | 0   |
| algo/retrieval-service/ | 7       | 7   | 0   | 0   |
| algo/indexing-service/  | 3       | 0   | 3   | 0   |
| algo/model-adapter/     | 4       | 0   | 4   | 0   |
| algo/rag-engine/        | 1       | 0   | 1   | 0   |
| algo/multimodal-engine/ | 3       | 1   | 0   | 2   |
| cmd/identity-service/   | 3       | 3   | 0   | 0   |
| cmd/knowledge-service/  | 5       | 0   | 5   | 0   |
| cmd/model-router/       | 4       | 4   | 0   | 0   |
| cmd/ai-orchestrator/    | 2       | 2   | 0   | 0   |
| cmd/analytics-service/  | 4       | 0   | 0   | 4   |
| pkg/                    | 2       | 1   | 1   | 0   |
| flink-jobs/             | 3       | 0   | 0   | 3   |

---

## 🔍 快速查找

### 按优先级查找

**P0 (31 项)**

```bash
# 语音相关
algo/voice-engine/app/core/full_duplex_engine.py:205
algo/voice-engine/app/core/tts_engine.py:347
algo/voice-engine/main.py:261,264
algo/voice-engine/app/services/tts_service.py:69,132,194,199
algo/voice-engine/app/services/asr_service.py:190
algo/voice-engine/app/routers/asr.py:91
algo/voice-engine/app/routers/health.py:25

# 检索相关
algo/retrieval-service/app/services/retrieval_service.py:44,88
algo/retrieval-service/app/core/bm25_retriever.py:37
algo/retrieval-service/app/core/graph_retriever.py:67,82
algo/retrieval-service/app/core/reranker.py:85,96
algo/retrieval-service/app/routers/health.py:25

# 身份与安全
cmd/identity-service/internal/biz/auth_usecase.go:201
cmd/identity-service/internal/biz/tenant_usecase.go:173
pkg/middleware/auth.go:30

# 模型路由
cmd/model-router/main.go:116,158,172
cmd/model-router/internal/application/cost_optimizer.go:96

# AI编排
cmd/ai-orchestrator/main.go:172

# 多模态
algo/multimodal-engine/app/routers/health.py:25
```

**P1 (34 项)**

```bash
# Agent相关
algo/agent-engine/app/memory/memory_manager.py:209,282,306
algo/agent-engine/app/tools/tool_registry.py:246,261,267
algo/agent-engine/app/workflows/react_agent.py:385
algo/agent-engine/app/core/executor/plan_execute_executor.py:97
algo/agent-engine/app/core/tools/builtin_tools.py:34,65,79
algo/agent-engine/main.py:225
algo/agent-engine/routers/agent.py:34,53

# 索引与知识
algo/indexing-service/app/core/entity_extractor.py:233
algo/indexing-service/app/kafka_consumer.py:281
cmd/knowledge-service/internal/biz/document_usecase.go:147,209,229

# 模型适配
algo/model-adapter/ (多厂商适配)

# RAG
algo/rag-engine/app/core/rag_engine.py:246

# 基础设施
pkg/events/consumer.go:301
cmd/identity-service/internal/service/identity.go:22
```

**P2 (10 项)**

```bash
# 多模态
algo/multimodal-engine/app/services/ocr_service.py:181

# 分析
cmd/analytics-service/internal/biz/report_usecase.go:105,119,131,143

# Flink
flink-jobs/document-analysis/main.py:17
flink-jobs/user-behavior/main.py:17
flink-jobs/message-stats/main.py:65,72
```

### 按关键词查找

**安全相关**

```bash
cmd/identity-service/internal/biz/auth_usecase.go:201       # Token黑名单
cmd/identity-service/internal/biz/tenant_usecase.go:173    # 租户保护
pkg/middleware/auth.go:30                                   # JWT验证
```

**流式/实时相关**

```bash
cmd/ai-orchestrator/main.go:172                            # 流式响应
algo/voice-engine/app/routers/asr.py:91                   # 流式ASR
algo/agent-engine/app/workflows/react_agent.py:385        # 流式输出
```

**缓存/性能相关**

```bash
algo/voice-engine/app/services/tts_service.py:194,199     # TTS缓存
algo/retrieval-service/app/core/bm25_retriever.py:37      # BM25持久化
```

**成本相关**

```bash
cmd/model-router/main.go:116                               # 路由逻辑
cmd/model-router/internal/application/cost_optimizer.go:96 # 成本告警
```

---

## 🛠️ 开发者快速上手

### 1. 选择一个 TODO 开始

```bash
# 查看某个文件的TODO
grep -n "TODO" algo/voice-engine/app/services/tts_service.py

# 或使用ripgrep（更快）
rg "TODO" algo/voice-engine/
```

### 2. 创建分支

```bash
git checkout -b feature/tts-redis-cache
```

### 3. 实现功能

参考详细清单中的:

- 工作量估算
- 依赖项
- 影响分析

### 4. 测试

```bash
# 单元测试
pytest tests/unit/test_tts_service.py

# 集成测试
pytest tests/integration/test_tts_cache.py
```

### 5. 提交 PR

```bash
git add .
git commit -m "feat(voice): implement TTS Redis cache

- Add Redis cache for TTS results
- Cache key: tts:{text_hash}:{voice_id}
- TTL: 24h
- Cache hit rate metric added

Closes #123"
```

---

## 📝 更新此文档

当完成一个 TODO 时，请:

1. 在此文档中标记为 ~~已完成~~
2. 更新 [TODO_TRACKER.md](TODO_TRACKER.md) 状态
3. 更新完成率统计

```bash
# 重新扫描TODO
grep -rn "TODO\|FIXME\|XXX" --include="*.py" --include="*.go" . > todo_scan.txt
```

---

_保持更新 | 方便开发 | 提升效率_
