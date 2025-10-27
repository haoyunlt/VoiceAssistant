# VoiceAssistant 服务迭代总计划

> **文档类型**: 主计划汇总
> **生成日期**: 2025-10-27
> **涵盖服务**: 15 个核心服务
> **计划周期**: 12 周 (3 个月)

---

## 📊 执行摘要

本文档汇总了 VoiceAssistant 平台所有核心服务的功能清单和迭代计划,基于:

- **代码扫描**: 228 个 TODO 标记
- **现有文档**: 15 份技术文档
- **业界对比**: LangChain, AutoGPT, voicehelper 等项目
- **最佳实践**: AI 客服、语音助手领域 2024-2025 最新技术

---

## 🎯 总体目标

| 维度       | 当前状态    | 目标状态 (12 周后) | 提升幅度   |
| ---------- | ----------- | ------------------ | ---------- |
| 功能完成度 | 45%         | 85%                | **+40%**   |
| 代码质量   | TODO:228 个 | TODO < 30 个       | **-87%**   |
| 测试覆盖率 | < 5%        | > 70%              | **+1300%** |
| 性能指标   | P95: ~2.5s  | P95 < 1.5s         | **+40%**   |
| 可用性     | N/A         | > 99.9%            | **新增**   |

---

## 📋 服务清单与优先级

### 核心 AI 服务 (P0)

| 服务名称                                | 完成度 | 未完成功能数      | 预计工作量 | 负责团队 |
| --------------------------------------- | ------ | ----------------- | ---------- | -------- |
| [Agent Engine](#agent-engine)           | 60%    | 5 个 P0 + 3 个 P1 | 12-15 天   | AI Team  |
| [Voice Engine](#voice-engine)           | 70%    | 6 个 P0 + 4 个 P1 | 10-12 天   | AI Team  |
| [RAG Engine](#rag-engine)               | 65%    | 4 个 P0 + 3 个 P1 | 8-10 天    | AI Team  |
| [Retrieval Service](#retrieval-service) | 50%    | 7 个 P0 + 2 个 P1 | 10-12 天   | AI Team  |

### 基础服务 (P0)

| 服务名称                                      | 完成度 | 未完成功能数      | 预计工作量 | 负责团队     |
| --------------------------------------------- | ------ | ----------------- | ---------- | ------------ |
| [Identity Service](#identity-service)         | 75%    | 3 个 P0           | 3-4 天     | Backend Team |
| [Knowledge Service](#knowledge-service)       | 70%    | 5 个 P0 + 2 个 P1 | 5-6 天     | Backend Team |
| [Model Router](#model-router)                 | 55%    | 4 个 P0 + 2 个 P1 | 4-5 天     | Backend Team |
| [Conversation Service](#conversation-service) | 80%    | 4 个 P1           | 4-5 天     | Backend Team |

### 支撑服务 (P1)

| 服务名称             | 完成度 | 未完成功能数 | 预计工作量 | 负责团队     |
| -------------------- | ------ | ------------ | ---------- | ------------ |
| Indexing Service     | 60%    | 3 个 P1      | 4-5 天     | AI Team      |
| Model Adapter        | 70%    | 2 个 P1      | 3-4 天     | AI Team      |
| Multimodal Engine    | 75%    | 3 个 P2      | 3-4 天     | AI Team      |
| Vector Store Adapter | 80%    | 2 个 P1      | 2-3 天     | Backend Team |
| AI Orchestrator      | 70%    | 2 个 P0      | 3-4 天     | Backend Team |

### 其他服务 (P2)

| 服务名称             | 完成度 | 未完成功能数 | 预计工作量    | 负责团队     |
| -------------------- | ------ | ------------ | ------------- | ------------ |
| Analytics Service    | 40%    | 4 个 P2      | 4-5 天        | Backend Team |
| Notification Service | 90%    | 0 个         | 1-2 天 (优化) | Backend Team |

**总计工作量**: 80-100 人天 (约 12-16 周 @ 5 人团队)

---

## 🚀 核心服务详细计划

### Agent Engine

**文档**: [SERVICE_AGENT_ENGINE_PLAN.md](SERVICE_AGENT_ENGINE_PLAN.md)

#### 未完成功能 (P0)

1. **记忆系统 - 向量检索**

   - 文件: `app/memory/memory_manager.py:209,282,306`
   - 工作量: 3-4 天
   - 技术方案: Milvus + 时间衰减 + 访问频率增强
   - 验收: 召回率 > 80%

2. **工具注册与实现**

   - 文件: `app/tools/tool_registry.py:246,261,267`
   - 工作量: 3-4 天
   - 技术方案: 动态工具注册 + 5+实际工具 (搜索/知识库/天气/计算器等)
   - 验收: 至少 5 个实际工具可用

3. **Plan-Execute 执行器**

   - 文件: `app/core/executor/plan_execute_executor.py:97`
   - 工作量: 3-4 天
   - 技术方案: LLM 规划 + 步骤执行 + 失败恢复
   - 验收: 能正确分解复杂任务

4. **流式输出**

   - 文件: `app/workflows/react_agent.py:385`
   - 工作量: 2-3 天
   - 技术方案: SSE 流式推送 + 事件类型化
   - 验收: 实时展示推理过程

5. **Agent 路由逻辑**
   - 文件: `routers/agent.py:34,53`
   - 工作量: 2-3 天
   - 技术方案: 策略模式 + Redis 任务持久化
   - 验收: 任务状态查询准确

#### 关键改进点

- 借鉴 LangChain 的工具定义标准
- 参考 AutoGPT 的 Plan-and-Execute 模式
- 实现 voicehelper 的 Redis 任务持久化

#### 迭代时间线

- **Sprint 1 (Week 1-2)**: 记忆系统 + 工具实现
- **Sprint 2 (Week 3-4)**: Plan-Execute + 流式输出
- **Sprint 3 (Week 5-6)**: LangGraph 工作流 + 多 Agent 协作

---

### Voice Engine

**文档**: [SERVICE_VOICE_ENGINE_PLAN.md](SERVICE_VOICE_ENGINE_PLAN.md)

#### 未完成功能 (P0)

1. **流式 ASR 识别**

   - 文件: `app/routers/asr.py:91`
   - 工作量: 3-4 天
   - 技术方案: WebSocket + Whisper + WebRTC VAD
   - 验收: 延迟 < 500ms

2. **TTS Redis 缓存**

   - 文件: `app/services/tts_service.py:194,199`
   - 工作量: 2 天
   - 技术方案: Redis + LRU 淘汰 + 统计
   - 验收: 命中率 > 40%

3. **VAD 升级 (Silero)**

   - 当前: 已实现但配置不精细
   - 工作量: 2 天
   - 技术方案: 参数优化 + 精确时间戳
   - 验收: 准确率 > 95%

4. **Azure Speech SDK 集成**

   - 文件: `app/services/tts_service.py:132`, `app/services/asr_service.py:190`
   - 工作量: 2-3 天
   - 技术方案: 多厂商适配器 + 自动降级
   - 验收: Azure ASR/TTS 可用

5. **音频降噪与增强**

   - 文件: `main.py:261,264`
   - 工作量: 2-3 天
   - 技术方案: noisereduce + 归一化 + EQ
   - 验收: 降噪效果改善

6. **语音克隆 (可选)**
   - 文件: `app/core/tts_engine.py:347`
   - 工作量: 3-5 天
   - 技术方案: Coqui TTS XTTS
   - 验收: 能克隆指定语音

#### 业界对比

| 功能       | voicehelper | 本项目当前 | 本项目目标    |
| ---------- | ----------- | ---------- | ------------- |
| Silero VAD | ✅          | ✅         | ✅ 优化       |
| 流式 ASR   | ✅          | ❌         | ✅ 实现       |
| TTS 缓存   | ❌          | ❌         | ✅ Redis      |
| 多厂商支持 | ⚠️          | ⚠️         | ✅ Azure      |
| 情感识别   | ✅          | ❌         | ✅ (Sprint 3) |

#### 迭代时间线

- **Sprint 1 (Week 1-2)**: 流式 ASR + TTS 缓存 + VAD 优化
- **Sprint 2 (Week 3-4)**: Azure 集成 + 音频增强
- **Sprint 3 (Week 5-6)**: 语音克隆 + 情感识别

---

### RAG Engine

#### 未完成功能 (P0)

1. **历史对话获取**

   - 文件: `app/core/rag_engine.py:246`
   - 工作量: 1 天
   - 技术方案: 调用 Conversation Service API
   - 验收: 多轮对话有效

2. **LLM 重排序**

   - 文件: 当前仅有 Cross-Encoder 框架
   - 工作量: 2-3 天
   - 技术方案: LLM Rerank + 多策略融合
   - 验收: 重排序准确率提升 15%+

3. **图谱检索集成**

   - 依赖: Indexing Service 的图谱构建
   - 工作量: 2-3 天
   - 技术方案: Neo4j Cypher 查询 + 向量混合
   - 验收: 结构化知识可用

4. **查询扩展优化**
   - 当前: 已实现但效果一般
   - 工作量: 1-2 天
   - 技术方案: 多样性采样 + 缓存
   - 验收: 召回率提升 10%+

#### 业界最佳实践

- **LangChain RAG**: 多查询扩展 + 自适应检索
- **LlamaIndex**: Graph RAG + Multi-Document Agent
- **HayStack**: Hybrid Retrieval + Answer Post-processing

#### 迭代时间线

- **Sprint 1 (Week 1-2)**: 历史对话 + LLM 重排序
- **Sprint 2 (Week 3-4)**: 图谱检索 + 查询优化
- **Sprint 3 (Week 5-6)**: Self-RAG + Adaptive RAG

---

### Retrieval Service

#### 未完成功能 (P0)

1. **Embedding 服务调用**

   - 文件: `app/services/retrieval_service.py:44,88`
   - 工作量: 1 天
   - 技术方案: 调用 Model Adapter
   - 验收: 向量检索可用

2. **BM25 索引持久化**

   - 文件: `app/core/bm25_retriever.py:37`
   - 工作量: 1-2 天
   - 技术方案: Elasticsearch 或本地持久化
   - 验收: 重启不丢失索引

3. **混合检索 (Hybrid Retrieval)**

   - 当前: 仅向量检索
   - 工作量: 3-4 天
   - 技术方案: 向量 + BM25 + RRF 融合
   - 验收: 召回率提升 20%+

4. **图谱检索**

   - 文件: `app/core/graph_retriever.py:67,82`
   - 工作量: 2-3 天
   - 技术方案: Neo4j + NER + Cypher
   - 验收: 实体关系检索正确

5. **LLM 重排序**

   - 文件: `app/core/reranker.py:85,96`
   - 工作量: 1-2 天
   - 技术方案: LLM 评分 + Cross-Encoder
   - 验收: NDCG 提升 15%+

6. **检索结果缓存**

   - 当前: 未实现
   - 工作量: 1 天
   - 技术方案: Redis 语义缓存
   - 验收: 命中率 > 30%

7. **健康检查完善**
   - 文件: `app/routers/health.py:25`
   - 工作量: 0.5 天
   - 技术方案: Milvus/ES 连接检查
   - 验收: K8s 探测准确

#### 迭代时间线

- **Sprint 1 (Week 1-2)**: Embedding 调用 + BM25 持久化 + 混合检索
- **Sprint 2 (Week 3-4)**: 图谱检索 + LLM 重排序
- **Sprint 3 (Week 5-6)**: 语义缓存 + 高级检索策略

---

### Identity Service

#### 未完成功能 (P0)

1. **Token 黑名单机制**

   - 文件: `internal/biz/auth_usecase.go:201`
   - 工作量: 1 天
   - 技术方案: Redis SET 存储 + TTL 自动过期
   - 验收: 登出后 Token 无效

2. **租户删除保护**

   - 文件: `internal/biz/tenant_usecase.go:173`
   - 工作量: 0.5 天
   - 技术方案: 检查关联用户/资源
   - 验收: 有数据的租户无法删除

3. **JWT 验证中间件**
   - 文件: `pkg/middleware/auth.go:30`
   - 工作量: 1 天
   - 技术方案: 网关统一鉴权 + 白名单
   - 验收: API 受保护

#### 安全加固 (P1)

4. **MFA 多因素认证**

   - 工作量: 2-3 天
   - 技术方案: TOTP + 备用码
   - 验收: MFA 可选启用

5. **密码策略加强**

   - 工作量: 1 天
   - 技术方案: 复杂度检查 + 历史记录
   - 验收: 符合安全标准

6. **审计日志**
   - 工作量: 1-2 天
   - 技术方案: 记录所有认证事件
   - 验收: 可追溯审计

#### 迭代时间线

- **Sprint 1 (Week 1)**: Token 黑名单 + JWT 中间件
- **Sprint 2 (Week 3)**: 租户删除保护 + MFA
- **Sprint 3 (Week 5)**: 审计日志 + 安全加固

---

### Knowledge Service

#### 未完成功能 (P0)

1. **MinIO 文件上传集成**

   - 当前: 可能使用本地文件系统
   - 工作量: 2 天
   - 技术方案: MinIO SDK + 预签名 URL
   - 验收: 文件上传/下载正常

2. **事件补偿机制**

   - 文件: `internal/biz/document_usecase.go:147,229`
   - 工作量: 1-2 天
   - 技术方案: 本地消息表 + 定时重试
   - 验收: 事件不丢失

3. **文档清理任务**

   - 文件: `internal/biz/document_usecase.go:209`
   - 工作量: 1 天
   - 技术方案: 软删除 + 定时清理 + GC
   - 验收: 存储不泄漏

4. **文档版本管理**

   - 当前: 未实现
   - 工作量: 2-3 天
   - 技术方案: 版本号 + 增量存储
   - 验收: 可回滚版本

5. **病毒扫描 (ClamAV)**
   - 参考: voicehelper 已实现
   - 工作量: 1-2 天
   - 技术方案: ClamAV 集成 + 异步扫描
   - 验收: 恶意文件被拦截

#### 迭代时间线

- **Sprint 1 (Week 1-2)**: MinIO 集成 + 事件补偿
- **Sprint 2 (Week 3-4)**: 文档清理 + 版本管理
- **Sprint 3 (Week 5-6)**: 病毒扫描 + 高级特性

---

### Model Router

#### 未完成功能 (P0)

1. **路由逻辑实现**

   - 文件: `main.go:116`
   - 工作量: 1-2 天
   - 技术方案: 负载/成本/延迟综合评分
   - 验收: 智能路由生效

2. **模型信息动态获取**

   - 文件: `main.go:158`
   - 工作量: 0.5 天
   - 技术方案: 配置中心 + 动态更新
   - 验收: 模型配置可热更新

3. **健康检查**

   - 文件: `main.go:172`
   - 工作量: 0.5 天
   - 技术方案: 定期探测后端模型服务
   - 验收: 不可用模型被摘除

4. **成本告警**
   - 文件: `internal/application/cost_optimizer.go:96`
   - 工作量: 0.5 天
   - 技术方案: 阈值检查 + Webhook 通知
   - 验收: 成本超标有告警

#### 高级功能 (P1)

5. **智谱 GLM-4 支持**

   - 参考: voicehelper 已支持
   - 工作量: 1 天
   - 技术方案: 适配器模式
   - 验收: GLM-4 可用

6. **模型降级策略**
   - 工作量: 1-2 天
   - 技术方案: GPT-4 → GPT-3.5 → 本地模型
   - 验收: 成本节约 20%+

#### 迭代时间线

- **Sprint 1 (Week 1-2)**: 路由逻辑 + 健康检查 + 成本告警
- **Sprint 2 (Week 3-4)**: GLM-4 支持 + 降级策略
- **Sprint 3 (Week 5-6)**: 性能优化 + A/B 测试

---

### Conversation Service

#### 未完成功能 (P1)

1. **Kafka 事件发布**

   - 当前: 未集成
   - 工作量: 1 天
   - 技术方案: 集成`pkg/events/publisher.go`
   - 验收: 对话事件可消费

2. **上下文压缩**

   - 当前: 可能超出上下文窗口
   - 工作量: 1-2 天
   - 技术方案: Sliding Window + 摘要压缩
   - 验收: 长对话不报错

3. **高级对话管理**

   - 当前: 简单列表管理
   - 工作量: 2-3 天
   - 技术方案: 状态机 + 对话策略
   - 验收: 复杂场景处理正确

4. **SSE 流式响应**
   - 当前: 仅批量响应
   - 工作量: 1-2 天
   - 技术方案: Server-Sent Events
   - 验收: 实时流式输出

#### 迭代时间线

- **Sprint 2 (Week 3-4)**: Kafka 事件 + SSE 流式
- **Sprint 3 (Week 5-6)**: 上下文压缩 + 对话管理

---

## 📅 12 周迭代时间线

### Phase 1: 核心打通与补全 (Week 1-4)

#### Sprint 1: P0 阻塞项解决 (Week 1)

**团队**: Backend 2 人, AI 2 人, SRE 1 人

| 任务           | 服务              | 工作量 | 负责人    | 状态 |
| -------------- | ----------------- | ------ | --------- | ---- |
| Wire 代码生成  | All Go Services   | 2 天   | Backend 1 | 📝   |
| Proto 代码生成 | All Services      | 1 天   | Backend 1 | 📝   |
| 服务启动验证   | All Services      | 1 天   | SRE       | 📝   |
| MinIO 集成     | Knowledge Service | 2 天   | Backend 2 | 📝   |

**验收**: 所有服务可启动并通过健康检查

---

#### Sprint 2: 核心功能第一阶段 (Week 2)

| 任务             | 服务                   | 工作量 | 负责人    |
| ---------------- | ---------------------- | ------ | --------- |
| Kafka 事件集成   | Knowledge/Conversation | 2 天   | Backend 2 |
| Indexing 消费者  | Indexing Service       | 3 天   | AI 1      |
| 记忆系统向量检索 | Agent Engine           | 3-4 天 | AI 1      |
| TTS Redis 缓存   | Voice Engine           | 2 天   | Backend 2 |

**验收**: 端到端索引流程可用

---

#### Sprint 3: 核心功能第二阶段 (Week 3)

| 任务           | 服务              | 工作量 | 负责人    |
| -------------- | ----------------- | ------ | --------- |
| 工具注册实现   | Agent Engine      | 3-4 天 | AI 2      |
| 流式 ASR       | Voice Engine      | 3-4 天 | AI 1      |
| Embedding 调用 | Retrieval Service | 1 天   | AI 2      |
| Token 黑名单   | Identity Service  | 1 天   | Backend 1 |

**验收**: Agent 有实际工具,ASR 流式可用

---

#### Sprint 4: 核心功能完善 (Week 4)

| 任务                | 服务              | 工作量 | 负责人    |
| ------------------- | ----------------- | ------ | --------- |
| Plan-Execute 执行器 | Agent Engine      | 3-4 天 | AI 1      |
| 混合检索            | Retrieval Service | 3-4 天 | AI 2      |
| Azure Speech 集成   | Voice Engine      | 2-3 天 | AI 1      |
| JWT 中间件          | Identity Service  | 1 天   | Backend 1 |

**验收**: MVP 端到端流程完整

---

### Phase 2: 可观测性与性能 (Week 5-8)

#### Sprint 5: 监控指标 (Week 5)

| 任务            | 范围              | 工作量 | 负责人     |
| --------------- | ----------------- | ------ | ---------- |
| Prometheus 指标 | All Services      | 2 天   | SRE + Devs |
| 业务指标定义    | All Services      | 1 天   | SRE        |
| Agent 流式输出  | Agent Engine      | 2-3 天 | AI 1       |
| 图谱检索        | Retrieval Service | 2-3 天 | AI 2       |

---

#### Sprint 6: 分布式追踪 (Week 6)

| 任务             | 范围            | 工作量 | 负责人 |
| ---------------- | --------------- | ------ | ------ |
| OTEL Go 集成     | Go Services     | 2 天   | SRE    |
| OTEL Python 集成 | Python Services | 2 天   | AI 1   |
| 跨服务追踪验证   | All Services    | 1 天   | SRE    |
| LLM 重排序       | RAG/Retrieval   | 2 天   | AI 2   |

---

#### Sprint 7: Grafana 与告警 (Week 7)

| 任务           | 范围         | 工作量 | 负责人    |
| -------------- | ------------ | ------ | --------- |
| Dashboard 开发 | All Services | 3 天   | SRE       |
| 告警规则配置   | All Services | 2 天   | SRE       |
| Agent 路由逻辑 | Agent Engine | 2-3 天 | Backend 1 |

---

#### Sprint 8: 性能压测与优化 (Week 8)

| 任务         | 范围                | 工作量 | 负责人    |
| ------------ | ------------------- | ------ | --------- |
| k6 压测脚本  | All Services        | 2 天   | SRE       |
| 性能基准测试 | All Services        | 2 天   | SRE + All |
| 性能优化     | Bottleneck Services | 2 天   | All       |
| 成本优化     | AI Services         | 1 天   | AI 2      |

**里程碑**: 性能达到 NFR 基线

---

### Phase 3: 前端与用户体验 (Week 9-11)

#### Sprint 9: Web 前端核心 (Week 9)

| 任务       | 模块          | 工作量 | 负责人   |
| ---------- | ------------- | ------ | -------- |
| 认证与布局 | platforms/web | 2 天   | Frontend |
| 对话界面   | platforms/web | 3 天   | Frontend |
| VAD 优化   | Voice Engine  | 2 天   | AI 1     |

---

#### Sprint 10: 知识管理与可视化 (Week 10)

| 任务           | 模块              | 工作量 | 负责人    |
| -------------- | ----------------- | ------ | --------- |
| 文档管理       | platforms/web     | 2 天   | Frontend  |
| Agent 调试面板 | platforms/web     | 2 天   | Frontend  |
| 多模态交互     | platforms/web     | 1 天   | Frontend  |
| 事件补偿机制   | Knowledge Service | 1-2 天 | Backend 2 |

---

#### Sprint 11: 管理后台 (Week 11)

| 任务         | 模块            | 工作量 | 负责人   |
| ------------ | --------------- | ------ | -------- |
| 管理后台     | platforms/admin | 3 天   | Frontend |
| 前端性能优化 | platforms/web   | 1 天   | Frontend |
| 移动端适配   | platforms/web   | 1 天   | Frontend |
| 音频增强     | Voice Engine    | 2-3 天 | AI 1     |

---

### Phase 4: 测试、安全与发布 (Week 12)

#### Sprint 12: 最后冲刺 (Week 12)

| 任务       | 范围         | 工作量 | 负责人          |
| ---------- | ------------ | ------ | --------------- |
| 单元测试   | Core Modules | 2 天   | QA + All        |
| 集成测试   | Key Flows    | 2 天   | QA              |
| 安全审计   | All Services | 1 天   | SRE             |
| CI/CD 完善 | Pipeline     | 1 天   | SRE             |
| 准生产验证 | Staging Env  | 1 天   | Tech Lead + SRE |

**里程碑**: 准生产稳定运行 24h

---

## 🔥 业界对比与借鉴

### 对比 voicehelper 项目

| 功能             | voicehelper | 本项目当前 | 本项目目标 (12 周后) | 来源      |
| ---------------- | ----------- | ---------- | -------------------- | --------- |
| Silero VAD       | ✅ 已实现   | ✅ 已实现  | ✅ 优化配置          | Sprint 1  |
| Redis 任务持久化 | ✅ 已实现   | ❌ 内存    | ✅ 实现              | Sprint 5  |
| 流式 ASR         | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 3  |
| 分布式限流器     | ✅ 已实现   | ❌ 本地    | ✅ 全局限流          | Sprint 5  |
| 长期记忆衰减     | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 2  |
| GLM-4 支持       | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 6  |
| 文档版本管理     | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 8  |
| 病毒扫描         | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 9  |
| Push 通知        | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 10 |
| 情感识别         | ✅ 已实现   | ❌         | ✅ 实现              | Sprint 11 |

**迁移计划**: 详见 [FEATURE_MIGRATION_REPORT.md](docs/FEATURE_MIGRATION_REPORT.md)

---

### 借鉴业界最佳实践

#### LangChain / LangGraph

- **工具生态**: 标准化工具定义 (OpenAI Function Calling 格式)
- **记忆系统**: 短期 + 长期记忆分离
- **状态管理**: StateGraph 工作流

**应用到**: Agent Engine, RAG Engine

---

#### AutoGPT

- **Plan-and-Execute**: 任务分解与执行分离
- **自主目标管理**: 动态调整执行计划
- **持续记忆**: 跨会话记忆管理

**应用到**: Agent Engine

---

#### LlamaIndex

- **Graph RAG**: 知识图谱与向量混合检索
- **多文档 Agent**: 多知识源协同
- **查询路由**: 自适应检索策略

**应用到**: RAG Engine, Retrieval Service

---

#### HayStack

- **Hybrid Retrieval**: 向量 + BM25 + 过滤器
- **Pipeline 架构**: 可配置的检索流水线
- **Answer Post-processing**: 答案后处理

**应用到**: Retrieval Service

---

#### OpenAI Realtime API (2024)

- **全双工对话**: 实时语音交互
- **低延迟流式**: < 500ms 首字节
- **打断机制**: 自然对话体验

**应用到**: Voice Engine (Sprint 11 可选)

---

### AI 客服领域趋势 (2024-2025)

1. **情感智能**: 语音情感识别与回应
2. **多模态交互**: 语音 + 图像 + 视频
3. **超个性化**: 用户画像与记忆
4. **人机协作**: AI 处理简单任务,人工处理复杂问题
5. **行业定制**: 垂直领域深度优化

**应用计划**: 情感识别(Sprint 11), 多模态已支持, 个性化记忆(Sprint 2)

---

## 📊 成功指标 (KPI)

### 技术指标

| 类别      | 指标           | 当前     | 目标 (Sprint 4) | 目标 (Sprint 8) | 目标 (Sprint 12) |
| --------- | -------------- | -------- | --------------- | --------------- | ---------------- |
| **Agent** | 工具数量       | 3 Mock   | 5+ 实际         | 10+ 实际        | 15+ 实际         |
| **Agent** | 任务成功率     | ~40%     | > 70%           | > 80%           | > 85%            |
| **Agent** | 记忆召回率     | N/A      | > 80%           | > 85%           | > 90%            |
| **Voice** | ASR 准确率     | ~85%     | > 90%           | > 92%           | > 95%            |
| **Voice** | TTS 缓存命中率 | 0%       | > 40%           | > 50%           | > 60%            |
| **Voice** | VAD 准确率     | ~85%     | > 95%           | > 96%           | > 98%            |
| **RAG**   | 检索召回率     | ~70%     | > 85%           | > 90%           | > 92%            |
| **RAG**   | 答案准确率     | ~75%     | > 85%           | > 88%           | > 90%            |
| **性能**  | API P95 延迟   | ~2.5s    | < 2.0s          | < 1.5s          | < 1.2s           |
| **性能**  | 并发能力       | ~100 RPS | > 500 RPS       | > 1k RPS        | > 1.5k RPS       |
| **质量**  | 测试覆盖率     | < 5%     | > 30%           | > 50%           | > 70%            |
| **质量**  | TODO 数量      | 228      | < 150           | < 80            | < 30             |

### 业务指标

| 指标              | 当前 | 目标 (Sprint 12) |
| ----------------- | ---- | ---------------- |
| 用户满意度        | N/A  | > 4.0/5.0        |
| 对话完成率        | N/A  | > 85%            |
| 平均对话轮次      | N/A  | > 5 轮           |
| 知识召回准确率    | N/A  | > 90%            |
| 成本 (Token/对话) | N/A  | < $0.05          |
| 服务可用性        | N/A  | > 99.9%          |

---

## 💰 资源需求

### 人力资源

| 角色              | 人数 | 职责                            | 时间投入               |
| ----------------- | ---- | ------------------------------- | ---------------------- |
| Backend Engineer  | 2    | Go 服务、API、基础设施          | 全职 12 周             |
| AI Engineer       | 2    | Python AI 服务、算法优化        | 全职 12 周             |
| Frontend Engineer | 1    | Web 应用、管理后台              | 全职 10 周 (Week 3-12) |
| SRE Engineer      | 1    | 可观测性、CI/CD、部署、压测     | 全职 12 周             |
| QA Engineer       | 1    | 测试用例、自动化测试、质量保证  | 全职 8 周 (Week 5-12)  |
| Tech Lead         | 1    | 技术决策、架构审查、Code Review | 兼职 12 周 (30%)       |

**总人力**: 7-8 人 (6 全职 + 1 兼职)
**总人月**: ~18 人月

---

### 基础设施成本

| 资源                    | 月成本 | 说明                 |
| ----------------------- | ------ | -------------------- |
| K8s 集群 (3 节点)       | $300   | 开发+测试+预发       |
| Redis Sentinel (3 节点) | $150   | 缓存+任务持久化+限流 |
| PostgreSQL (HA)         | $200   | 主数据库             |
| Milvus (2 节点)         | $300   | 向量数据库           |
| Elasticsearch (3 节点)  | $250   | BM25 检索+日志       |
| MinIO (2 节点, 1TB)     | $100   | 对象存储             |
| Neo4j (单节点)          | $150   | 知识图谱             |
| ClamAV 服务器           | $50    | 病毒扫描             |
| Grafana Cloud           | $100   | 可选,简化运维        |
| 带宽与流量              | $200   | 音频数据传输         |

**月总计**: ~$1,800
**3 个月总计**: ~$5,400

---

### API 与第三方服务

| 服务            | 月成本        | 说明                    |
| --------------- | ------------- | ----------------------- |
| OpenAI API      | $1,000-$2,000 | GPT-4/GPT-3.5/Embedding |
| Azure Speech    | $200-$500     | 备用 ASR/TTS            |
| 智谱 AI (GLM-4) | $300-$600     | 国产模型                |
| SerpAPI         | $50           | 搜索工具                |
| OpenWeather API | $0            | 免费                    |
| Firebase FCM    | $0            | 免费                    |
| Apple APNs      | $0            | 免费                    |

**月总计**: ~$1,550-$3,150
**3 个月总计**: ~$4,650-$9,450

---

### 总成本估算

| 类别                | 3 个月成本            |
| ------------------- | --------------------- |
| 人力 (假设年薪$80k) | $120,000              |
| 基础设施            | $5,400                |
| API 与第三方服务    | $4,650-$9,450         |
| **总计**            | **$130,050-$134,850** |

---

## ⚠️ 风险与缓解

### 高风险项

| 风险                | 影响 | 概率 | 缓解措施                                       |
| ------------------- | ---- | ---- | ---------------------------------------------- |
| **人员不足**        | 高   | 高   | 立即招聘 Frontend/QA (Week 1-2 完成)           |
| **技术债务累积**    | 中   | 高   | 每周技术债务审查会议,及时重构                  |
| **第三方 API 限流** | 高   | 中   | 多提供商冗余、降级策略、本地模型备选           |
| **性能不达标**      | 高   | 中   | Sprint 8 提前压测、及时优化、必要时架构调整    |
| **进度延期**        | 中   | 中   | 双周回顾调整优先级、砍掉 P3 功能、延长 Phase 4 |

### 中风险项

| 风险             | 影响 | 概率 | 缓解措施                                  |
| ---------------- | ---- | ---- | ----------------------------------------- |
| **集成问题**     | 中   | 中   | 早期集成测试 (Sprint 4)、持续验证         |
| **测试覆盖不足** | 中   | 中   | 强制 PR 覆盖率门禁、专职 QA (Week 5 开始) |
| **安全漏洞**     | 中   | 低   | 每次 PR 自动扫描、定期安全审查            |
| **文档滞后**     | 低   | 高   | PR 模板强制文档更新、每周文档审查         |
| **成本超支**     | 中   | 中   | 实时成本监控、告警、预算审批流程          |

---

## ✅ 验收标准

### Sprint 4 (MVP) 验收

- ✅ 所有 Go 服务可启动并通过健康检查
- ✅ Kafka 事件系统集成到 3 个核心服务
- ✅ MinIO 文件上传/下载可用
- ✅ Agent 有 5+实际工具可用
- ✅ 流式 ASR 可用 (WebSocket)
- ✅ TTS 缓存命中率 > 40%
- ✅ 端到端 MVP 流程演示成功

### Sprint 8 (性能) 验收

- ✅ Prometheus 指标采集覆盖所有服务
- ✅ Grafana 5 个仪表盘可用
- ✅ Jaeger 追踪端到端链路清晰
- ✅ AlertManager 告警规则测试通过
- ✅ k6 压测达到 NFR 基线:
  - API P95 < 1.5s
  - 并发 ≥ 1k RPS
  - 可用性 ≥ 99.9% (模拟测试)
- ✅ Token 成本降低 20%+

### Sprint 12 (生产就绪) 验收

- ✅ 单元测试覆盖率 ≥ 70% (核心模块)
- ✅ 集成测试覆盖核心流程
- ✅ E2E 测试自动化运行通过
- ✅ 安全扫描无高危漏洞
- ✅ CI/CD 流水线完整且通过
- ✅ 准生产环境灰度发布成功
- ✅ 准生产环境稳定运行 24h+
- ✅ 所有 P0 功能完成
- ✅ 80%+ P1 功能完成
- ✅ TODO 数量 < 30 个

---

## 📚 相关文档

### 服务级文档

- [Agent Engine 迭代计划](SERVICE_AGENT_ENGINE_PLAN.md) ⭐
- [Voice Engine 迭代计划](SERVICE_VOICE_ENGINE_PLAN.md) ⭐
- [RAG Engine 实现总结](algo/rag-engine/IMPLEMENTATION_SUMMARY.md)
- [Retrieval Service 待补充]
- [Knowledge Service 待补充]
- [Model Router 待补充]

### 现有文档

- [未完成功能清单](docs/INCOMPLETE_FEATURES_CHECKLIST.md)
- [后续迭代计划](docs/NEXT_ITERATION_PLAN.md)
- [功能迁移报告](docs/FEATURE_MIGRATION_REPORT.md)
- [迭代计划 V2](docs/roadmap/ITERATION_PLAN_V2.md)
- [任务清单 V2](docs/roadmap/TASK_CHECKLIST_V2.md)

### 架构文档

- [系统架构 V2.0](docs/arch/microservice-architecture-v2.md)
- [NFR 基线](docs/nfr/nfr-baseline.md)
- [团队协作指南](TEAM_COLLABORATION_GUIDE.md)

---

## 📞 项目管理

### 联系方式

| 角色             | 姓名   | 联系方式 | 负责模块             |
| ---------------- | ------ | -------- | -------------------- |
| **Tech Lead**    | [待定] | -        | 整体架构、技术决策   |
| **Backend Lead** | [待定] | -        | Go 服务、基础设施    |
| **AI Lead**      | [待定] | -        | Python AI 服务、算法 |
| **SRE Lead**     | [待定] | -        | 可观测性、部署、性能 |
| **CTO**          | [待定] | -        | 战略方向、资源分配   |

### 会议节奏

- **每日站会**: 每天 10:00 AM (15 分钟)
- **双周回顾**: 每两周五下午 (1 小时)
- **Sprint 计划会**: 每 Sprint 开始 (2 小时)
- **技术债务审查**: 每周三下午 (30 分钟)
- **文档审查**: 每周五上午 (30 分钟)

### 沟通渠道

- **Slack 频道**:
  - #voiceassistant-general
  - #agent-engine-dev
  - #voice-engine-dev
  - #backend-dev
  - #sre-ops
- **Wiki**: 团队 Wiki 文档
- **GitHub Projects**: 任务看板

---

## 🎉 下一步行动

### 立即执行 (本周)

1. **组建项目团队**

   - [ ] 指定 Tech Lead
   - [ ] 分配 Backend Team (2 人)
   - [ ] 分配 AI Team (2 人)
   - [ ] 分配 SRE Team (1 人)
   - [ ] 计划 Frontend/QA 招聘

2. **环境准备**

   - [ ] 部署 Redis Sentinel (3 节点)
   - [ ] 部署 Milvus
   - [ ] 部署 Elasticsearch
   - [ ] 配置 CI/CD 流水线
   - [ ] 准备测试环境

3. **启动 Sprint 1** (下周一)
   - [ ] 召开 Sprint 计划会
   - [ ] 分配任务 (Wire 生成, Proto 生成, MinIO 集成)
   - [ ] 设置 GitHub Project 看板
   - [ ] 开始开发

### 本周关键任务

- [ ] 完成项目团队组建 (周二)
- [ ] 完成环境准备 (周四)
- [ ] 召开项目启动会 (周五)
- [ ] 完成 Sprint 1 任务分解 (周五)

---

## 🔗 快速链接

- [代码仓库](https://github.com/yourorg/VoiceAssistant)
- [项目看板](https://github.com/yourorg/VoiceAssistant/projects)
- [CI/CD](https://github.com/yourorg/VoiceAssistant/actions)
- [Grafana](http://grafana.yourorg.com)
- [API 文档](http://api-docs.yourorg.com)

---

**准备好开始了吗? Let's build something great! 🚀**

---

**文档版本**: v1.0.0
**制定日期**: 2025-10-27
**制定人**: AI Assistant + Tech Lead
**审批**: [待定]
**下次审查**: Sprint 2 结束后 (Week 4)
