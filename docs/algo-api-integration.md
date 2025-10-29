# 算法服务 API 集成指南

## 概述

本文档汇总了所有算法服务的 API 接口，为 Go 服务（特别是 AI-Orchestrator）提供统一的集成方案。

## 算法服务列表

| 服务名称 | 默认端口 | 主要功能 | 状态 |
|---------|---------|---------|------|
| agent-engine | 8010 | Agent执行、工具调用、记忆管理、Multi-Agent、Self-RAG | ✅ 已集成 |
| rag-engine | 8006 | RAG问答、查询改写、上下文构建 | ✅ 已集成 |
| retrieval-service | 8012 | 向量检索、混合检索、重排序 | ✅ 已集成 |
| voice-engine | 8004 | ASR、TTS、VAD、语音流处理 | ⚠️ 部分集成 |
| multimodal-engine | 8007 | OCR、视觉理解、图像分析 | ❌ 待集成 |
| model-adapter | 8005 | LLM适配、协议转换、成本计算 | ✅ 已集成 |
| indexing-service | 8000 | 文档索引、向量化、知识图谱构建 | ❌ 待集成 |
| vector-store-adapter | 8009 | 向量库适配（Milvus/pgvector） | ❌ 待集成 |

---

## 1. Agent Engine (端口: 8010)

### 1.1 核心功能

#### 执行 Agent 任务
```
POST /execute
Content-Type: application/json

Request:
{
  "task": "用户任务描述",
  "mode": "react",              // react/plan_execute/reflexion/simple
  "max_steps": 10,
  "tools": ["search", "calculator"],
  "conversation_id": "conv-123",
  "tenant_id": "tenant-1"
}

Response:
{
  "result": "任务执行结果",
  "steps": [...],
  "metadata": {...}
}
```

#### 流式执行
```
POST /execute/stream
Content-Type: application/json

Response: text/event-stream
data: {"step": 1, "action": "search", "result": "..."}
data: {"step": 2, "action": "analyze", "result": "..."}
```

### 1.2 工具管理

#### 列出工具
```
GET /tools?category=search

Response:
{
  "tools": [
    {
      "name": "web_search",
      "description": "搜索网页",
      "category": "search",
      "parameters": {...}
    }
  ],
  "count": 10
}
```

#### 注册工具
```
POST /tools/register

Request:
{
  "name": "custom_tool",
  "description": "自定义工具",
  "function": "app.tools.custom:my_tool",
  "parameters": {...}
}
```

### 1.3 Multi-Agent 协作

#### 多智能体协作
```
POST /multi-agent/collaborate

Request:
{
  "task": "复杂任务",
  "mode": "sequential",  // sequential/parallel/debate/voting/hierarchical
  "agent_ids": ["agent-1", "agent-2"],
  "priority": 5,
  "tenant_id": "tenant-1"
}

Response:
{
  "task": "复杂任务",
  "mode": "sequential",
  "agents_involved": ["agent-1", "agent-2"],
  "final_result": {...},
  "quality_score": 0.92,
  "completion_time": 5.2,
  "status": "completed"
}
```

#### 注册 Agent
```
POST /multi-agent/agents/register

Request:
{
  "agent_id": "agent-1",
  "role": "coordinator",  // coordinator/researcher/planner/executor/reviewer
  "tools": ["search", "analyze"],
  "tenant_id": "tenant-1"
}
```

#### 列出 Agents
```
GET /multi-agent/agents?tenant_id=tenant-1&user_id=user-1

Response:
{
  "agents": [
    {
      "agent_id": "agent-1",
      "role": "coordinator",
      "tools_count": 5,
      "processed_messages": 100
    }
  ],
  "count": 1
}
```

### 1.4 Self-RAG

#### Self-RAG 查询
```
POST /self-rag/query

Request:
{
  "query": "问题",
  "mode": "adaptive",  // standard/adaptive/strict/fast
  "enable_citations": true,
  "max_refinements": 3,
  "tenant_id": "tenant-1"
}

Response:
{
  "query": "问题",
  "answer": "答案",
  "confidence": 0.95,
  "retrieval_strategy": "adaptive",
  "refinement_count": 1,
  "hallucination_level": "low",
  "is_grounded": true,
  "citations": [...]
}
```

### 1.5 Smart Memory

#### 添加记忆
```
POST /smart-memory/add

Request:
{
  "content": "记忆内容",
  "tier": "short_term",  // working/short_term/long_term
  "importance": 0.8,
  "tenant_id": "tenant-1"
}
```

#### 检索记忆
```
POST /smart-memory/retrieve

Request:
{
  "query": "查询",
  "top_k": 5,
  "tier_filter": "long_term",
  "min_importance": 0.5,
  "tenant_id": "tenant-1"
}

Response:
{
  "memories": [
    {
      "memory_id": "mem-1",
      "content": "记忆内容",
      "tier": "long_term",
      "importance": 0.9,
      "access_count": 10
    }
  ],
  "count": 5
}
```

---

## 2. RAG Engine (端口: 8006)

### 2.1 RAG 问答

#### 生成答案
```
POST /api/v1/generate

Request:
{
  "query": "用户问题",
  "tenant_id": "tenant-1",
  "history": [
    {"role": "user", "content": "历史消息1"},
    {"role": "assistant", "content": "历史回复1"}
  ],
  "options": {
    "top_k": 5,
    "enable_rerank": true
  }
}

Response:
{
  "answer": "生成的答案",
  "sources": [
    {
      "content": "来源文档内容",
      "document_id": "doc-1",
      "score": 0.95
    }
  ],
  "metadata": {
    "retrieval_time": 0.5,
    "generation_time": 1.2
  }
}
```

### 2.2 Ultimate RAG (v2.0)

#### 增强 RAG
```
POST /api/v2/rag/generate

Request:
{
  "query": "复杂问题",
  "tenant_id": "tenant-1",
  "strategy": "auto",  // auto/dense/sparse/hybrid
  "enable_rerank": true,
  "enable_cache": true
}

Response:
{
  "answer": "答案",
  "confidence": 0.92,
  "sources": [...],
  "strategy_used": "hybrid",
  "cache_hit": false
}
```

---

## 3. Retrieval Service (端口: 8012)

### 3.1 检索

#### 向量检索
```
POST /retrieve

Request:
{
  "query": "查询文本",
  "tenant_id": "tenant-1",
  "top_k": 10,
  "method": "hybrid",  // vector/bm25/hybrid
  "enable_rerank": true
}

Response:
{
  "results": [
    {
      "content": "文档内容",
      "score": 0.95,
      "metadata": {
        "document_id": "doc-1",
        "chunk_id": "chunk-1"
      }
    }
  ],
  "retrieval_time": 0.3
}
```

### 3.2 查询增强

#### 查询改写
```
POST /query/rewrite

Request:
{
  "query": "原始查询",
  "tenant_id": "tenant-1",
  "methods": ["expansion", "decomposition"]
}

Response:
{
  "original_query": "原始查询",
  "rewritten_queries": [
    "改写查询1",
    "改写查询2"
  ],
  "method_used": "expansion"
}
```

---

## 4. Voice Engine (端口: 8004)

### 4.1 ASR (语音识别)

#### 语音转文本
```
POST /asr
Content-Type: multipart/form-data

Request:
- audio: [音频文件]
- language: zh  // zh/en/auto
- model: base   // tiny/base/small/medium/large

Response:
{
  "text": "识别的文本",
  "language": "zh",
  "duration": 5.2,
  "confidence": 0.95
}
```

### 4.2 TTS (语音合成)

#### 文本转语音
```
POST /tts

Request:
{
  "text": "要合成的文本",
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+0%",
  "pitch": "+0Hz"
}

Response: audio/mpeg stream
```

### 4.3 VAD (语音活动检测)

#### 检测语音片段
```
POST /vad
Content-Type: multipart/form-data

Request:
- audio: [音频文件]
- threshold: 0.5

Response:
{
  "segments": [
    {"start": 0.0, "end": 1.5},
    {"start": 2.0, "end": 3.8}
  ],
  "count": 2
}
```

### 4.4 流式处理

#### 流式 ASR
```
WebSocket: ws://localhost:8004/stream/asr

Message Format:
{
  "type": "audio",
  "data": "<base64_encoded_audio>",
  "config": {
    "language": "zh",
    "sample_rate": 16000
  }
}

Response:
{
  "type": "transcript",
  "text": "部分识别结果",
  "is_final": false
}
```

#### 全双工通话
```
WebSocket: ws://localhost:8004/full-duplex

Supports:
- Real-time ASR
- Real-time TTS
- Interruption handling
```

### 4.5 高级功能

#### 说话人分离
```
POST /diarization

Request:
- audio: [音频文件]
- num_speakers: 2

Response:
{
  "segments": [
    {
      "speaker": "SPEAKER_0",
      "start": 0.0,
      "end": 2.5,
      "text": "说话内容"
    }
  ]
}
```

#### 情感识别
```
POST /emotion

Request:
- audio: [音频文件]

Response:
{
  "emotion": "happy",
  "confidence": 0.87,
  "emotions": {
    "happy": 0.87,
    "neutral": 0.10,
    "sad": 0.03
  }
}
```

---

## 5. Multimodal Engine (端口: 8007)

### 5.1 OCR

#### 文字识别
```
POST /ocr/extract
Content-Type: multipart/form-data

Request:
- image: [图片文件]
- language: zh  // zh/en/auto

Response:
{
  "text": "识别的文字",
  "regions": [
    {
      "bbox": [x1, y1, x2, y2],
      "text": "区域文字",
      "confidence": 0.95
    }
  ],
  "processing_time": 0.5
}
```

### 5.2 Vision

#### 视觉理解
```
POST /vision/analyze
Content-Type: multipart/form-data

Request:
- image: [图片文件]
- task: caption  // caption/detect/classify/vqa

Response:
{
  "caption": "图片描述",
  "objects": [
    {
      "label": "person",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.92
    }
  ],
  "processing_time": 0.8
}
```

#### 视觉问答 (VQA)
```
POST /vision/vqa

Request:
- image: [图片文件]
- question: "图片中有什么?"

Response:
{
  "question": "图片中有什么?",
  "answer": "一个人在跑步",
  "confidence": 0.89
}
```

### 5.3 综合分析

#### 多模态分析
```
POST /analysis/multimodal

Request:
- image: [图片文件]
- text: "相关文本"

Response:
{
  "ocr_text": "图片中的文字",
  "caption": "图片描述",
  "objects": [...],
  "analysis": "综合分析结果"
}
```

---

## 6. Model Adapter (端口: 8005)

### 6.1 LLM 调用

#### 生成文本 (非流式)
```
POST /api/v1/generate

Request:
{
  "model": "gpt-4",
  "provider": "openai",  // openai/claude/zhipu/qwen
  "messages": [
    {"role": "user", "content": "问题"}
  ],
  "temperature": 0.7,
  "max_tokens": 2000
}

Response:
{
  "provider": "openai",
  "model": "gpt-4",
  "content": "生成的内容",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  }
}
```

#### 生成文本 (流式)
```
POST /api/v1/generate/stream

Response: text/event-stream
data: {"content": "生成", "finish_reason": null}
data: {"content": "的内容", "finish_reason": null}
data: {"content": "", "finish_reason": "stop"}
```

### 6.2 Embedding

#### 创建向量
```
POST /api/v1/embeddings

Request:
{
  "model": "text-embedding-ada-002",
  "provider": "openai",
  "input": "要向量化的文本"
}

Response:
{
  "embeddings": [[0.1, 0.2, ...]],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 5,
    "total_tokens": 5
  }
}
```

### 6.3 工具功能

#### 协议转换
```
POST /api/v1/convert

Request:
{
  "target_provider": "claude",
  "messages": [...],
  "parameters": {...}
}

Response:
{
  "converted_format": {...}
}
```

#### 成本计算
```
POST /api/v1/cost/calculate

Request:
{
  "model": "gpt-4",
  "input_tokens": 100,
  "output_tokens": 200
}

Response:
{
  "model": "gpt-4",
  "input_cost": 0.003,
  "output_cost": 0.012,
  "total_cost": 0.015,
  "currency": "USD"
}
```

### 6.4 提供商管理

#### 列出提供商
```
GET /api/v1/providers

Response:
{
  "providers": [
    {
      "name": "openai",
      "status": "healthy",
      "models": ["gpt-4", "gpt-3.5-turbo"],
      "capabilities": ["chat", "embedding"]
    }
  ],
  "count": 5
}
```

---

## 7. Indexing Service (端口: 8000)

### 7.1 文档处理

#### 触发索引
```
POST /trigger?document_id=doc-1

Response:
{
  "status": "success",
  "document_id": "doc-1"
}
```

#### 增量更新
```
POST /incremental/update

Request:
{
  "document_id": "doc-1",
  "tenant_id": "tenant-1",
  "chunks": [
    {
      "content": "文档块内容",
      "metadata": {...}
    }
  ]
}

Response:
{
  "document_id": "doc-1",
  "chunks_processed": 10,
  "vectors_stored": 10
}
```

#### 删除文档
```
DELETE /incremental/delete?document_id=doc-1&tenant_id=tenant-1

Response:
{
  "status": "success",
  "document_id": "doc-1"
}
```

### 7.2 统计信息

#### 获取统计
```
GET /stats

Response:
{
  "documents_processed": 1000,
  "chunks_created": 5000,
  "vectors_stored": 5000,
  "processing_time_avg": 2.5
}
```

---

## 8. Vector Store Adapter (端口: 8009)

### 8.1 向量操作

#### 插入向量
```
POST /collections/{collection_name}/insert

Request:
{
  "backend": "milvus",  // milvus/pgvector
  "data": [
    {
      "id": "vec-1",
      "vector": [0.1, 0.2, ...],
      "metadata": {
        "document_id": "doc-1",
        "tenant_id": "tenant-1"
      }
    }
  ]
}

Response:
{
  "status": "success",
  "collection": "documents",
  "backend": "milvus",
  "inserted": 1
}
```

#### 检索向量
```
POST /collections/{collection_name}/search

Request:
{
  "backend": "milvus",
  "query_vector": [0.1, 0.2, ...],
  "top_k": 10,
  "tenant_id": "tenant-1",
  "filters": {
    "document_type": "pdf"
  }
}

Response:
{
  "status": "success",
  "results": [
    {
      "id": "vec-1",
      "score": 0.95,
      "metadata": {...}
    }
  ],
  "count": 10
}
```

#### 删除向量
```
DELETE /collections/{collection_name}/documents/{document_id}?backend=milvus

Response:
{
  "status": "success",
  "document_id": "doc-1",
  "deleted_count": 10
}
```

### 8.2 集合管理

#### 获取集合统计
```
GET /collections/{collection_name}/count?backend=milvus

Response:
{
  "status": "success",
  "collection": "documents",
  "backend": "milvus",
  "count": 5000
}
```

---

## 健康检查

所有服务都提供统一的健康检查接口：

### 基础健康检查
```
GET /health

Response:
{
  "status": "healthy",
  "service": "service-name",
  "version": "1.0.0"
}
```

### 就绪检查
```
GET /ready

Response:
{
  "ready": true,
  "checks": {
    "database": true,
    "cache": true,
    "dependencies": true
  }
}
```

---

## 集成最佳实践

### 1. 错误处理
- 所有服务使用统一的错误响应格式
- 包含错误码、消息和详细信息
- 支持重试和熔断机制

### 2. 超时配置
- 短任务: 5-10秒
- 中等任务: 30-60秒
- 长任务: 300秒+

### 3. 重试策略
- 最大重试次数: 3
- 退避策略: 指数退避
- 可重试的错误: 超时、临时网络错误

### 4. 熔断器
- 失败率阈值: 60%
- 最小请求数: 5
- 半开状态测试请求: 3
- 恢复时间: 30秒

### 5. 监控指标
- 请求计数
- 响应时间 (P50, P95, P99)
- 错误率
- 熔断器状态

---

## 配置示例

### services.yaml
```yaml
services:
  http:
    agent-engine:
      url: "http://agent-engine:8010"
      timeout: 60s
    rag-engine:
      url: "http://rag-engine:8006"
      timeout: 30s
    retrieval-service:
      url: "http://retrieval-service:8012"
      timeout: 10s
    voice-engine:
      url: "http://voice-engine:8004"
      timeout: 30s
    multimodal-engine:
      url: "http://multimodal-engine:8007"
      timeout: 20s
    model-adapter:
      url: "http://model-adapter:8005"
      timeout: 60s
    indexing-service:
      url: "http://indexing-service:8000"
      timeout: 300s
    vector-store-adapter:
      url: "http://vector-store-adapter:8009"
      timeout: 10s
```

---

## 下一步

1. ✅ 完善现有客户端 (agent-engine, rag-engine, retrieval-service, model-adapter)
2. 🔨 实现缺失的客户端 (voice-engine, multimodal-engine, indexing-service, vector-store-adapter)
3. 🔨 添加集成测试
4. 🔨 添加健康检查聚合
5. 📝 更新 API 文档
