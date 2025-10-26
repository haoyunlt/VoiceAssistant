# AI Orchestrator Service

AI 任务编排服务 - 统一调度和编排所有 AI 引擎

## 功能特性

### 1. 任务路由
- 根据任务类型自动路由到对应引擎
- 支持的任务类型：
  - `agent` - Agent 任务
  - `rag` - RAG 检索增强生成
  - `voice` - 语音处理（ASR/TTS）
  - `multimodal` - 多模态理解

### 2. 工作流编排
- 多步骤任务串行执行
- 条件分支
- 并行执行
- 错误处理与重试

### 3. 任务管理
- 任务状态跟踪
- 进度查询
- 任务取消
- 超时控制

### 4. 结果聚合
- 多引擎结果汇总
- 结果转换与格式化
- 引用来源管理

## API 接口

### POST /api/v1/execute
执行单个 AI 任务

**请求**:
```json
{
  "task_type": "rag",
  "query": "What is RAG?",
  "options": {
    "top_k": 5,
    "rerank": true
  },
  "user_id": "user_123",
  "tenant_id": "tenant_456"
}
```

**响应**:
```json
{
  "task_id": "task_123",
  "status": "completed",
  "engine": "rag",
  "result": {
    "response": "RAG stands for...",
    "citations": [...]
  },
  "duration": 1500
}
```

### POST /api/v1/workflows
创建工作流

**请求**:
```json
{
  "name": "Document Q&A Workflow",
  "steps": [
    {
      "type": "rag",
      "query": "{{user_query}}",
      "top_k": 5
    },
    {
      "type": "agent",
      "task": "Summarize the retrieved context",
      "context": "{{previous_result}}"
    },
    {
      "type": "voice",
      "action": "tts",
      "text": "{{previous_result}}"
    }
  ]
}
```

## 配置

```yaml
engines:
  agent:
    url: http://agent-engine:8000
    timeout: 30s
  rag:
    url: http://rag-engine:8000
    timeout: 10s
  voice:
    url: http://voice-engine:8000
    timeout: 20s
  multimodal:
    url: http://multimodal-engine:8000
    timeout: 15s

orchestrator:
  max_concurrent_tasks: 100
  task_timeout: 5m
  retry_times: 3
  circuit_breaker:
    threshold: 50%
    timeout: 60s
```

## 部署

### Docker
```bash
docker build -t ai-orchestrator:latest .
docker run -p 9003:9003 ai-orchestrator:latest
```

### Kubernetes
```bash
kubectl apply -f deployments/k8s/ai-orchestrator.yaml
```

## 监控

Prometheus 指标暴露在 `/metrics`：

- `ai_orchestrator_tasks_total` - 总任务数
- `ai_orchestrator_task_duration_seconds` - 任务执行时长
- `ai_orchestrator_engine_calls_total` - 引擎调用次数
- `ai_orchestrator_workflow_steps_total` - 工作流步骤数

## 开发

### 编译
```bash
go build -o ai-orchestrator ./cmd/ai-orchestrator
```

### 运行
```bash
./ai-orchestrator
```

### 测试
```bash
go test ./...
```
