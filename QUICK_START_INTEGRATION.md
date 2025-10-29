# 快速启动 - Enhanced Agent API集成

## 🎯 集成完成情况

✅ **Proto定义** - 新增12个RPC方法和20个消息类型
✅ **HTTP客户端** - 新增12个API调用方法
✅ **业务Handler** - 完整的业务逻辑封装
✅ **集成测试** - 15+个测试用例 + 性能测试
✅ **完整文档** - 架构说明、使用示例、最佳实践

---

## 🚀 快速开始（3分钟）

### 1. 启动算法服务

```bash
# 启动agent-engine
cd algo/agent-engine
python main.py
# 服务运行在 http://localhost:8003
```

### 2. 运行集成测试

```bash
# 在项目根目录
go test ./tests/integration/... -v -run TestMultiAgentCollaborate
```

### 3. 使用示例

```go
// 在你的Go代码中
import (
    "voicehelper/cmd/ai-orchestrator/internal/application"
    "voicehelper/cmd/ai-orchestrator/internal/infrastructure"
)

// 创建客户端和handler
aiClient := infrastructure.NewAIServiceClientFromEnv()
handler := application.NewEnhancedAgentHandler(aiClient, logger)

// 调用Multi-Agent协作
req := &application.MultiAgentCollaborateRequest{
    Task:     "分析市场趋势",
    Mode:     "parallel",
    Priority: 8,
    TenantID: "tenant-001",
    UserID:   "user-001",
}
resp, err := handler.MultiAgentCollaborate(ctx, req)
```

---

## 📦 新增文件清单

### 核心代码
1. **enhanced_agent_handler.go** (650行)
   - 路径: `cmd/ai-orchestrator/internal/application/`
   - 功能: 业务逻辑封装，12个API方法

2. **ai_service_client.go** (扩展，+400行)
   - 路径: `cmd/ai-orchestrator/internal/infrastructure/`
   - 功能: HTTP客户端，20个结构体，12个调用方法

### 测试
3. **enhanced_agent_integration_test.go** (550行)
   - 路径: `tests/integration/`
   - 功能: 完整集成测试套件

### Proto
4. **agent.proto** (扩展，+250行)
   - 路径: `api/proto/agent/v1/`
   - 功能: gRPC接口定义

### 文档
5. **ENHANCED_AGENT_INTEGRATION.md** (700行)
   - 完整的集成文档
6. **ENHANCED_AGENT_INTEGRATION_SUMMARY.md** (350行)
   - 集成总结
7. **QUICK_START_INTEGRATION.md** (本文件)
   - 快速启动指南

---

## 🎨 三个新增API概览

### 1️⃣ Multi-Agent协作
**用途**: 多Agent协同完成复杂任务

**5种模式**:
- `sequential` - 串行执行
- `parallel` - 并行执行
- `debate` - 辩论讨论
- `voting` - 投票决策
- `hierarchical` - 分层协作

**示例**:
```go
req := &application.MultiAgentCollaborateRequest{
    Task: "分析市场趋势并生成报告",
    Mode: "parallel",
    Priority: 8,
}
resp, _ := handler.MultiAgentCollaborate(ctx, req)
fmt.Printf("质量分数: %.2f\n", resp.QualityScore)
```

### 2️⃣ Self-RAG
**用途**: 自适应检索增强生成，带幻觉检测

**4种模式**:
- `standard` - 标准模式
- `adaptive` - 自适应（推荐）
- `strict` - 严格模式
- `fast` - 快速模式

**示例**:
```go
req := &application.SelfRAGQueryRequest{
    Query: "什么是人工智能？",
    Mode: "adaptive",
    EnableCitations: true,
}
resp, _ := handler.SelfRAGQuery(ctx, req)
fmt.Printf("置信度: %.2f, 引用数: %d\n",
    resp.Confidence, len(resp.Citations))
```

### 3️⃣ Smart Memory
**用途**: 智能记忆管理，支持分层和自动维护

**3个层级**:
- `working` - 工作记忆（秒级）
- `short_term` - 短期记忆（小时级）
- `long_term` - 长期记忆（天级）

**示例**:
```go
// 添加记忆
addReq := &application.AddMemoryRequest{
    Content: "今天学习了Go并发编程",
    Tier: "short_term",
    Importance: 0.8,
}
addResp, _ := handler.AddMemory(ctx, addReq)

// 检索记忆
retrieveReq := &application.RetrieveMemoryRequest{
    Query: "Go语言",
    TopK: 5,
}
retrieveResp, _ := handler.RetrieveMemory(ctx, retrieveReq)
```

---

## 🔧 配置

### 环境变量

```bash
# 服务地址
export AGENT_ENGINE_URL=http://localhost:8003

# 功能开关
export MULTI_AGENT_ENABLED=true
export SELF_RAG_ENABLED=true
export SMART_MEMORY_ENABLED=true

# Self-RAG配置
export SELF_RAG_HALLUCINATION_THRESHOLD=0.7
export SELF_RAG_MAX_REFINEMENTS=2

# Smart Memory配置
export MEMORY_COMPRESSION_ENABLED=true
```

### 服务配置（可选）

编辑 `configs/services.yaml`:
```yaml
services:
  - name: agent-engine
    type: http
    address: http://localhost:8003
    timeout: 60s
```

---

## 🧪 测试

### 运行全部测试
```bash
go test ./tests/integration/... -v
```

### 运行特定测试
```bash
# Multi-Agent测试
go test ./tests/integration/... -v -run TestMultiAgentCollaborate

# Self-RAG测试
go test ./tests/integration/... -v -run TestSelfRAGQuery

# Smart Memory测试
go test ./tests/integration/... -v -run TestSmartMemoryLifecycle
```

### 性能测试
```bash
go test ./tests/integration/... -bench=. -benchtime=10s
```

### 跳过集成测试（CI环境）
```bash
go test ./tests/integration/... -short
```

---

## 📊 监控

### Prometheus指标

访问 `http://localhost:8003/metrics` 查看：

```
# Multi-Agent
multi_agent_tasks_total{mode, status, tenant_id}
multi_agent_task_duration_seconds{mode, tenant_id}

# Self-RAG
self_rag_queries_total{mode, status, tenant_id}
self_rag_hallucination_rate{tenant_id}
self_rag_cache_hit_rate{tenant_id}

# Smart Memory
smart_memory_operations_total{operation, status, tenant_id}
smart_memory_size{tier, tenant_id}
```

---

## 🐛 常见问题

### 1. 连接超时
```
Error: context deadline exceeded
```
**解决**: 确保agent-engine服务已启动
```bash
cd algo/agent-engine && python main.py
```

### 2. 端口冲突
```
Error: bind: address already in use
```
**解决**: 修改端口配置
```bash
export PORT=8004  # 改用其他端口
```

### 3. 依赖缺失
```
Error: module not found
```
**解决**: 安装依赖
```bash
cd algo/agent-engine
pip install -r requirements.txt
```

---

## 📚 文档索引

- **完整集成文档**: [docs/ENHANCED_AGENT_INTEGRATION.md](docs/ENHANCED_AGENT_INTEGRATION.md)
- **集成总结**: [ENHANCED_AGENT_INTEGRATION_SUMMARY.md](ENHANCED_AGENT_INTEGRATION_SUMMARY.md)
- **Proto定义**: [api/proto/agent/v1/agent.proto](api/proto/agent/v1/agent.proto)
- **Handler代码**: [cmd/ai-orchestrator/internal/application/enhanced_agent_handler.go](cmd/ai-orchestrator/internal/application/enhanced_agent_handler.go)
- **客户端代码**: [cmd/ai-orchestrator/internal/infrastructure/ai_service_client.go](cmd/ai-orchestrator/internal/infrastructure/ai_service_client.go)
- **集成测试**: [tests/integration/enhanced_agent_integration_test.go](tests/integration/enhanced_agent_integration_test.go)

---

## 🎯 下一步

### 1. 生成Proto代码
```bash
cd api
./scripts/proto-gen.sh
```

### 2. 集成到现有服务
在 `cmd/ai-orchestrator/main.go` 中:
```go
// 创建handler
enhancedHandler := application.NewEnhancedAgentHandler(aiClient, logger)

// 注册路由
http.HandleFunc("/api/v1/multi-agent/collaborate",
    enhancedHandler.MultiAgentCollaborate)
http.HandleFunc("/api/v1/self-rag/query",
    enhancedHandler.SelfRAGQuery)
// ... 其他路由
```

### 3. 部署到Kubernetes
```bash
# 更新部署配置
kubectl apply -f deployments/k8s/ai-orchestrator-deployment.yaml

# 验证部署
kubectl get pods -l app=ai-orchestrator
```

---

## 🌟 核心特性

- ✅ **完整性**: 覆盖所有新增API端点
- ✅ **可靠性**: 熔断、重试、超时保护
- ✅ **可观测**: 日志、指标、追踪
- ✅ **可测试**: 完整的测试套件
- ✅ **高性能**: 并发、缓存、连接池

---

## 💡 使用技巧

### Multi-Agent
- 独立任务用 `parallel` 模式
- 依赖任务用 `sequential` 模式
- 关注 `quality_score`，低于0.6需要调整

### Self-RAG
- 默认使用 `adaptive` 模式
- 重要查询启用 `enable_citations`
- `max_refinements` 设为2-3次

### Smart Memory
- 临时数据用 `working` 层级
- 重要数据用 `long_term` 层级
- 定期执行 `/maintain` 维护

---

## 📞 联系支持

- **文档**: 查看 [docs/ENHANCED_AGENT_INTEGRATION.md](docs/ENHANCED_AGENT_INTEGRATION.md)
- **Issue**: 提交到项目Issue跟踪系统
- **测试**: 运行 `go test ./tests/integration/... -v`

---

**状态**: ✅ 已完成并可用
**最后更新**: 2025-10-29
**代码行数**: ~2000行（核心代码 + 测试 + 文档）
