# 未完成功能清单（Incomplete Features Checklist）

> **生成时间**: 2025-10-26  
> **覆盖范围**: 全代码库（Go + Python + 配置）  
> **方法**: 自动扫描 TODO/FIXME/待完善等标记  
> **状态**: 🔴 待实施 | 🟡 部分完成 | 🟢 已完成

---

## 📊 执行摘要（Executive Summary）

### 统计概览
| 类别 | 数量 | 占比 | 优先级分布 |
|------|------|------|-----------|
| **核心功能** | 23 | 35% | P0: 8, P1: 10, P2: 5 |
| **基础设施** | 15 | 23% | P0: 5, P1: 7, P2: 3 |
| **优化改进** | 18 | 27% | P1: 6, P2: 12 |
| **文档/测试** | 10 | 15% | P2: 10 |
| **总计** | **66** | 100% | P0: 13, P1: 23, P2: 30 |

### 关键风险
- 🔴 **P0 阻塞项**: 13 个核心功能未实现，影响 MVP 上线
- 🟡 **安全合规**: Token 黑名单、PII 脱敏等安全功能待完善
- 🟡 **可观测性**: 多个服务健康检查、监控指标未完整实现

---

## 🎯 按优先级分类（Priority-based Classification）

### P0 - 阻塞 MVP（13 项）

#### 1. 身份认证与安全 🔒
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P0-1 | Token 黑名单机制（Redis） | cmd/identity-service/internal/biz/auth_usecase.go:201 | 2d | Redis 配置 |
| P0-2 | JWT 验证实现 | pkg/middleware/auth.go:30 | 1d | 密钥管理 |
| P0-3 | 租户删除用户校验 | cmd/identity-service/internal/biz/tenant_usecase.go:173 | 0.5d | 用户服务查询 |

#### 2. AI 编排核心 🤖
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P0-4 | 流式响应实现 | cmd/ai-orchestrator/main.go:172 | 3d | SSE/WebSocket |
| P0-5 | 流式输出（Agent） | algo/agent-engine/app/workflows/react_agent.py:385 | 2d | LangChain Streaming |
| P0-6 | 模型路由逻辑 | cmd/model-router/main.go:116 | 3d | 负载均衡策略 |

#### 3. 知识管理 📚
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P0-7 | 事件补偿机制 | cmd/knowledge-service/internal/biz/document_usecase.go:147,229 | 2d | Kafka 事务 |
| P0-8 | Kafka 索引完成事件 | algo/indexing-service/app/kafka_consumer.py:281 | 1d | Kafka Producer |
| P0-9 | LLM 关系抽取 | algo/indexing-service/app/core/entity_extractor.py:233 | 3d | LLM 接口 |

#### 4. 语音引擎 🎤
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P0-10 | ASR 流式识别 | algo/voice-engine/app/routers/asr.py:91 | 3d | WebSocket/gRPC |
| P0-11 | 全双工音频播放中断 | algo/voice-engine/app/core/full_duplex_engine.py:205 | 1d | 音频播放器控制 |

#### 5. 实时分析 📊
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P0-12 | Flink 消息统计聚合 | flink-jobs/message-stats/main.py:65 | 2d | ClickHouse Sink |
| P0-13 | ClickHouse 数据写入 | flink-jobs/message-stats/main.py:72 | 1d | ClickHouse 连接 |

---

### P1 - 重要功能（23 项）

#### 6. RAG 增强 🔍
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P1-1 | 向量相似度检索 | algo/agent-engine/app/memory/memory_manager.py:209 | 3d | Milvus/pgvector |
| P1-2 | 向量存储实现 | algo/agent-engine/app/memory/memory_manager.py:282 | 2d | 向量数据库 |
| P1-3 | 向量检索优化 | algo/agent-engine/app/memory/memory_manager.py:306 | 2d | - |
| P1-4 | Embedding 服务调用 | algo/retrieval-service/app/services/retrieval_service.py:44,88 | 1d | Model Adapter |
| P1-5 | BM25 索引加载 | algo/retrieval-service/app/core/bm25_retriever.py:37 | 2d | Milvus/ES |
| P1-6 | LLM 重排序 | algo/retrieval-service/app/core/reranker.py:85,96 | 3d | LLM 接口 |
| P1-7 | 图谱 NER 实现 | algo/retrieval-service/app/core/graph_retriever.py:67 | 2d | NER 模型 |
| P1-8 | 图谱查询实现 | algo/retrieval-service/app/core/graph_retriever.py:82 | 3d | Neo4j/Nebula |
| P1-9 | 对话历史获取 | algo/rag-engine/app/core/rag_engine.py:246 | 1d | Conversation Service |

#### 7. Agent 工具集成 🛠️
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P1-10 | 真实搜索引擎 | algo/agent-engine/app/tools/tool_registry.py:246 | 2d | Google/Bing API |
| P1-11 | 真实知识库搜索 | algo/agent-engine/app/tools/tool_registry.py:261 | 1d | Knowledge Service |
| P1-12 | 真实天气 API | algo/agent-engine/app/tools/tool_registry.py:267 | 0.5d | OpenWeather API |
| P1-13 | 搜索工具实现 | algo/agent-engine/app/core/tools/builtin_tools.py:34 | 2d | 同 P1-10 |
| P1-14 | 网页抓取工具 | algo/agent-engine/app/core/tools/builtin_tools.py:65 | 1d | Scrapy/BeautifulSoup |
| P1-15 | 文件读取工具 | algo/agent-engine/app/core/tools/builtin_tools.py:79 | 1d | 安全沙箱 |
| P1-16 | 动态工具注册 | algo/agent-engine/main.py:225 | 2d | 插件系统 |
| P1-17 | Plan-Execute 步骤解析 | algo/agent-engine/app/core/executor/plan_execute_executor.py:97 | 3d | LangChain |

#### 8. 模型适配器 🔌
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P1-18 | 智谱 AI (GLM) 适配 | algo/model-adapter/README.md:28 | 2d | GLM SDK |
| P1-19 | 通义千问适配 | algo/model-adapter/README.md:29 | 2d | Qwen SDK |
| P1-20 | 百度文心适配 | algo/model-adapter/README.md:30 | 2d | Wenxin SDK |

#### 9. 报表与分析 📈
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P1-21 | 使用报表生成 | cmd/analytics-service/internal/biz/report_usecase.go:105 | 3d | ClickHouse 查询 |
| P1-22 | 成本报表生成 | cmd/analytics-service/internal/biz/report_usecase.go:119 | 2d | Token 计费 |
| P1-23 | 模型性能报表 | cmd/analytics-service/internal/biz/report_usecase.go:131 | 2d | Prometheus |

---

### P2 - 优化改进（30 项）

#### 10. 语音增强 🎵
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P2-1 | 语音克隆 | algo/voice-engine/app/core/tts_engine.py:347 | 5d | Coqui TTS |
| P2-2 | 音频降噪 | algo/voice-engine/main.py:261 | 3d | Denoiser 模型 |
| P2-3 | 音频增强 | algo/voice-engine/main.py:264 | 2d | Audio Processing |
| P2-4 | 音频时长计算 | algo/voice-engine/app/services/tts_service.py:69 | 0.5d | - |
| P2-5 | Azure Speech SDK | algo/voice-engine/app/services/tts_service.py:132 | 2d | Azure SDK |
| P2-6 | Azure ASR SDK | algo/voice-engine/app/services/asr_service.py:190 | 2d | Azure SDK |

#### 11. 缓存与性能 ⚡
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P2-7 | TTS Redis 缓存 | algo/voice-engine/app/services/tts_service.py:194,199 | 1d | Redis |
| P2-8 | 事件消费延迟策略 | pkg/events/consumer.go:301 | 0.5d | - |
| P2-9 | 上下文压缩策略 | cmd/conversation-service/IMPLEMENTATION_SUMMARY.md:355 | 3d | LLM 摘要 |

#### 12. 多模态 🖼️
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P2-10 | EasyOCR 集成 | algo/multimodal-engine/app/services/ocr_service.py:181 | 2d | EasyOCR |
| P2-11 | 批量 OCR 处理 | algo/multimodal-engine/README.md:284 | 2d | 队列系统 |

#### 13. 告警与监控 🚨
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P2-12 | 成本优化告警 | cmd/model-router/internal/application/cost_optimizer.go:96 | 1d | AlertManager |
| P2-13 | ASR/TTS 健康检查 | algo/voice-engine/app/routers/health.py:25 | 0.5d | - |
| P2-14 | OCR 健康检查 | algo/multimodal-engine/app/routers/health.py:25 | 0.5d | - |
| P2-15 | Retrieval 健康检查 | algo/retrieval-service/app/routers/health.py:25 | 1d | Milvus/ES |

#### 14. 实时流分析 🔄
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P2-16 | 文档分析 Flink 作业 | flink-jobs/document-analysis/main.py:17 | 3d | Flink API |
| P2-17 | 用户行为 Flink 作业 | flink-jobs/user-behavior/main.py:17 | 3d | Flink API |

#### 15. 服务发现与配置 🔧
| ID | 功能 | 位置 | 工作量 | 依赖 |
|----|------|------|--------|------|
| P2-18 | AI Orchestrator 服务发现 | cmd/ai-orchestrator/IMPLEMENTATION_SUMMARY.md:288 | 2d | Consul/Nacos |
| P2-19 | 模型路由存储层 | cmd/model-router/main.go:158 | 2d | PostgreSQL |
| P2-20 | 模型健康检查 | cmd/model-router/main.go:172 | 1d | HTTP Client |

#### 其他优化项（P2-21 ~ P2-30）
- P2-21: 文档清理任务 (2d)
- P2-22: SMS 短信发送 (2d)
- P2-23: Push 移动推送 (2d)
- P2-24: Web 前端完整实现 (14d)
- P2-25: 3 个 BFF 层实现 (6d)
- P2-26: Wire 依赖注入完善 (3d)
- P2-27: Redis 缓存策略优化 (2d)
- P2-28: Token 黑名单优化 (2d)
- P2-29: 团队联系信息 (0.5d)
- P2-30: gRPC 服务实现完善 (1d)

---

## 💰 工作量估算（Effort Estimation）

| 优先级 | 人天 | 人周 | 建议人力 |
|--------|------|------|----------|
| **P0** | 26.5 | 3.3 | 2 人 × 2 周 |
| **P1** | 43.5 | 5.4 | 2 人 × 3 周 |
| **P2** | 54.5 | 6.8 | 2 人 × 4 周 |
| **总计** | **124.5** | **15.6** | **2 人 × 8 周** |

---

## 🎯 快速启动指南（Quick Start）

### 1. 立即开始（本周）
```bash
# 实现 Token 黑名单
cd cmd/identity-service
# 编辑 internal/biz/auth_usecase.go

# 运行测试
make test

# 提交 PR
git commit -m "feat(identity): implement token blacklist with Redis"
```

### 2. 并行任务分配
- **开发者 A**: P0-1~3（安全）+ P0-4~6（编排）
- **开发者 B**: P0-7~9（知识）+ P0-10~13（语音 + 分析）
- **开发者 C**: P1-1~9（RAG）并行开始

---

**注意事项**:
1. 本清单基于代码注释自动生成，可能存在遗漏或过时信息
2. 工作量估算为粗略估计，实际开发需要 Buffer（建议 1.5x）
3. 优先级仅供参考，请结合业务需求调整

**下一步行动**:
- [ ] 召开 Planning Meeting，确认优先级
- [ ] 分配任务到具体开发者
- [ ] 在 GitHub Issues 创建对应 Task
