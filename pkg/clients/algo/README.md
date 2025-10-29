# 算法服务客户端 (Algo Clients)

统一的算法服务Go客户端库，提供重试、超时、熔断等企业级特性。

## 目录结构

```
pkg/clients/algo/
├── README.md                           # 本文档
├── base_client.go                      # 基础客户端（HTTP调用、重试、熔断）
├── client_manager.go                   # 客户端管理器（统一入口）
├── voice_engine_client.go              # Voice Engine客户端
├── multimodal_engine_client.go         # Multimodal Engine客户端
├── indexing_service_client.go          # Indexing Service客户端
└── vector_store_adapter_client.go      # Vector Store Adapter客户端
```

## 快速开始

### 1. 创建客户端管理器

#### 从环境变量创建（推荐）

```go
import "voicehelper/pkg/clients/algo"

// 自动从环境变量或默认配置路径加载
manager, err := algo.NewClientManagerFromEnv()
if err != nil {
    log.Fatalf("Failed to create client manager: %v", err)
}
defer manager.Close()
```

#### 从配置文件创建

```go
manager, err := algo.NewClientManagerFromConfig("configs/services.yaml")
if err != nil {
    log.Fatalf("Failed to create client manager: %v", err)
}
defer manager.Close()
```

### 2. 使用各个服务客户端

#### Agent Engine

```go
// 执行Agent任务
req := map[string]interface{}{
    "task": "帮我查询天气",
    "mode": "react",
    "max_steps": 10,
    "tools": []string{"web_search"},
    "tenant_id": "tenant-1",
}

var result map[string]interface{}
err := manager.AgentEngine.Post(ctx, "/execute", req, &result)
```

#### RAG Engine

```go
// RAG问答
req := map[string]interface{}{
    "query": "什么是AI?",
    "tenant_id": "tenant-1",
    "options": map[string]interface{}{
        "top_k": 5,
    },
}

var result map[string]interface{}
err := manager.RAGEngine.Post(ctx, "/api/v1/generate", req, &result)
```

#### Voice Engine

```go
// 语音识别 (ASR)
audioData, _ := os.ReadFile("audio.wav")
asrResult, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
if err != nil {
    log.Printf("ASR failed: %v", err)
} else {
    log.Printf("Recognized text: %s", asrResult.Text)
}

// 文本转语音 (TTS)
ttsReq := &algo.TTSRequest{
    Text:  "你好，世界",
    Voice: "zh-CN-XiaoxiaoNeural",
    Rate:  "+0%",
    Pitch: "+0Hz",
}
audioData, err := manager.VoiceEngine.TextToSpeech(ctx, ttsReq)

// 语音活动检测 (VAD)
vadResult, err := manager.VoiceEngine.VoiceActivityDetection(ctx, audioData, 0.5)
```

#### Multimodal Engine

```go
// OCR文字识别
imageData, _ := os.ReadFile("image.jpg")
ocrResult, err := manager.MultimodalEngine.OCRExtract(ctx, imageData, "zh")
if err != nil {
    log.Printf("OCR failed: %v", err)
} else {
    log.Printf("Extracted text: %s", ocrResult.Text)
}

// 视觉理解
visionResult, err := manager.MultimodalEngine.VisionAnalyze(ctx, imageData, "caption")

// 视觉问答 (VQA)
vqaResult, err := manager.MultimodalEngine.VQA(ctx, imageData, "图片中有什么?")
```

#### Indexing Service

```go
// 触发文档索引
err := manager.IndexingService.TriggerIndexing(ctx, "doc-123")

// 增量更新
updateReq := &algo.IncrementalUpdateRequest{
    DocumentID: "doc-123",
    TenantID:   "tenant-1",
    Chunks: []algo.DocumentChunk{
        {
            Content: "文档内容",
            Metadata: map[string]interface{}{
                "page": 1,
            },
        },
    },
}
result, err := manager.IndexingService.IncrementalUpdate(ctx, updateReq)
```

#### Vector Store Adapter

```go
// 插入向量
insertReq := &algo.InsertVectorsRequest{
    Backend: "milvus",
    Data: []algo.VectorData{
        {
            ID:     "vec-1",
            Vector: []float64{0.1, 0.2, 0.3, /* ... */},
            Metadata: map[string]interface{}{
                "document_id": "doc-1",
                "tenant_id":   "tenant-1",
            },
        },
    },
}
result, err := manager.VectorStoreAdapter.InsertVectors(ctx, "documents", insertReq)

// 检索向量
searchReq := &algo.SearchVectorsRequest{
    Backend:     "milvus",
    QueryVector: []float64{0.1, 0.2, 0.3, /* ... */},
    TopK:        10,
    TenantID:    "tenant-1",
}
searchResult, err := manager.VectorStoreAdapter.SearchVectors(ctx, "documents", searchReq)
```

### 3. 健康检查

```go
// 获取所有服务的健康状态
healthStatus := manager.GetHealthStatus()
for service, healthy := range healthStatus {
    log.Printf("Service %s: healthy=%v", service, healthy)
}

// 检查单个服务是否健康
if manager.IsServiceHealthy("agent-engine") {
    // 调用服务
}

// 获取详细状态
statuses := manager.GetAllServiceStatus(ctx)
for _, status := range statuses {
    log.Printf("Service: %s, Healthy: %v, URL: %s, CircuitBreaker: %s",
        status.Name,
        status.Healthy,
        status.BaseURL,
        status.CircuitBreakerState,
    )
}
```

## 高级特性

### 1. 自动重试

所有客户端默认支持自动重试：
- 最大重试次数: 3次
- 退避策略: 指数退避（100ms, 200ms, 400ms）
- 最大退避时间: 5秒

```go
// 可以在创建BaseClient时自定义重试参数
client := algo.NewBaseClient(algo.BaseClientConfig{
    ServiceName: "my-service",
    BaseURL:     "http://localhost:8000",
    Timeout:     30 * time.Second,
    MaxRetries:  5,          // 自定义重试次数
    RetryDelay:  200 * time.Millisecond, // 自定义初始延迟
})
```

### 2. 熔断器

每个客户端都内置熔断器保护：
- 失败率阈值: 60%
- 最小请求数: 5
- 熔断恢复时间: 30秒
- 半开状态测试请求: 3个

```go
// 检查熔断器状态
state := manager.AgentEngine.GetCircuitBreakerState()
log.Printf("Circuit breaker state: %s", state.String())
// 可能的状态: closed, open, half-open
```

### 3. 超时控制

```go
// 使用context控制超时
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()

result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
```

### 4. 健康检查自动监控

客户端管理器可以自动定期执行健康检查：

```go
// 创建时启用自动健康检查
manager, err := algo.NewClientManager(&algo.ClientManagerConfig{
    ConfigPath:          "configs/services.yaml",
    HealthCheckInterval: 30 * time.Second, // 每30秒检查一次
})
```

## 配置

### 环境变量配置

```bash
# 配置文件路径（可选）
export SERVICES_CONFIG_PATH=/path/to/services.yaml

# 或者直接设置服务URL
export AGENT_ENGINE_URL=http://localhost:8010
export RAG_ENGINE_URL=http://localhost:8006
export RETRIEVAL_SERVICE_URL=http://localhost:8012
export MODEL_ADAPTER_URL=http://localhost:8005
export VOICE_ENGINE_URL=http://localhost:8004
export MULTIMODAL_ENGINE_URL=http://localhost:8007
export INDEXING_SERVICE_URL=http://localhost:8000
export VECTOR_STORE_ADAPTER_URL=http://localhost:8009
```

### YAML配置文件

```yaml
# configs/services.yaml
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

## 错误处理

```go
result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
if err != nil {
    // 检查是否为熔断器错误
    if err == gobreaker.ErrOpenState {
        log.Printf("Circuit breaker is open for voice-engine")
        return
    }

    // 检查是否为超时错误
    if err == context.DeadlineExceeded {
        log.Printf("Request timeout")
        return
    }

    // 其他错误
    log.Printf("ASR failed: %v", err)
    return
}
```

## 最佳实践

### 1. 使用健康检查避免无效调用

```go
if !manager.IsServiceHealthy("voice-engine") {
    return fmt.Errorf("voice-engine is not available")
}

result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
```

### 2. 合理设置超时

```go
// 短任务
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

// 长任务
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
defer cancel()
```

### 3. 优雅关闭

```go
func main() {
    manager, err := algo.NewClientManagerFromEnv()
    if err != nil {
        log.Fatal(err)
    }
    defer manager.Close() // 停止健康检查协程

    // ... 使用客户端
}
```

### 4. 日志和监控

```go
// 定期记录服务状态
go func() {
    ticker := time.NewTicker(1 * time.Minute)
    defer ticker.Stop()

    for range ticker.C {
        healthStatus := manager.GetHealthStatus()
        for service, healthy := range healthStatus {
            if !healthy {
                log.Printf("WARNING: Service %s is unhealthy", service)
            }
        }
    }
}()
```

## 测试

运行集成测试：

```bash
# 运行所有集成测试
go test -v ./tests/integration/...

# 运行特定测试
go test -v ./tests/integration/... -run TestVoiceEngineClient

# 设置超时
go test -v -timeout 5m ./tests/integration/...
```

## API文档

详细的API文档请参考：
- [算法服务API集成指南](../../../docs/algo-api-integration.md)
- 各服务的OpenAPI文档：
  - Agent Engine: http://localhost:8010/docs
  - RAG Engine: http://localhost:8006/docs
  - Voice Engine: http://localhost:8004/docs
  - Multimodal Engine: http://localhost:8007/docs
  - 等等

## 故障排查

### 1. 连接失败

```
Error: failed after 3 attempts: do request: dial tcp: connect: connection refused
```

**解决方法**:
- 检查服务是否启动
- 检查服务URL配置是否正确
- 检查网络连接

### 2. 熔断器开启

```
Error: circuit breaker is open
```

**解决方法**:
- 等待30秒让熔断器自动恢复
- 检查服务健康状态
- 查看服务日志确认问题

### 3. 超时

```
Error: context deadline exceeded
```

**解决方法**:
- 增加context超时时间
- 检查网络延迟
- 确认服务负载是否过高

## 贡献

欢迎贡献代码！提交PR前请：
1. 运行所有测试: `go test ./pkg/clients/algo/...`
2. 运行集成测试: `go test ./tests/integration/...`
3. 确保代码通过lint检查: `golangci-lint run ./pkg/clients/algo/...`

## 许可证

MIT License
