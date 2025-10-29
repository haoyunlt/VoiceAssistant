# 算法服务客户端快速入门

> 5分钟快速上手算法服务Go客户端

## 🚀 快速开始

### 1. 配置服务地址

**方式一：使用配置文件（推荐）**

```yaml
# configs/algo-services.yaml
services:
  http:
    agent-engine:
      url: "http://localhost:8010"
    voice-engine:
      url: "http://localhost:8004"
    # ... 其他服务
```

**方式二：使用环境变量**

```bash
export AGENT_ENGINE_URL=http://localhost:8010
export RAG_ENGINE_URL=http://localhost:8006
export VOICE_ENGINE_URL=http://localhost:8004
# ... 其他服务
```

### 2. 使用客户端

```go
package main

import (
    "context"
    "log"
    "voicehelper/pkg/clients/algo"
)

func main() {
    // 创建客户端管理器
    manager, err := algo.NewClientManagerFromEnv()
    if err != nil {
        log.Fatal(err)
    }
    defer manager.Close()

    ctx := context.Background()

    // 调用语音识别
    audioData := []byte{/* ... */}
    result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
    if err != nil {
        log.Printf("ASR failed: %v", err)
        return
    }

    log.Printf("识别结果: %s", result.Text)
}
```

### 3. 测试连接

运行测试脚本，检查所有服务是否正常：

```bash
./scripts/test-algo-clients.sh
```

## 📚 核心功能

### 语音识别 (ASR)

```go
audioData, _ := os.ReadFile("audio.wav")
result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
if err == nil {
    log.Printf("识别文本: %s (置信度: %.2f)", result.Text, result.Confidence)
}
```

### 文本转语音 (TTS)

```go
ttsReq := &algo.TTSRequest{
    Text:  "你好，世界",
    Voice: "zh-CN-XiaoxiaoNeural",
    Rate:  "+0%",
    Pitch: "+0Hz",
}
audioData, err := manager.VoiceEngine.TextToSpeech(ctx, ttsReq)
if err == nil {
    os.WriteFile("output.mp3", audioData, 0644)
}
```

### RAG 问答

```go
ragReq := map[string]interface{}{
    "query":     "什么是人工智能?",
    "tenant_id": "tenant-1",
    "options": map[string]interface{}{
        "top_k": 5,
    },
}

var result map[string]interface{}
err := manager.RAGEngine.Post(ctx, "/api/v1/generate", ragReq, &result)
if err == nil {
    log.Printf("答案: %v", result["answer"])
}
```

### Agent 执行

```go
agentReq := map[string]interface{}{
    "task": "帮我查询明天的天气",
    "mode": "react",
    "tools": []string{"web_search"},
    "tenant_id": "tenant-1",
}

var result map[string]interface{}
err := manager.AgentEngine.Post(ctx, "/execute", agentReq, &result)
```

### OCR 文字识别

```go
imageData, _ := os.ReadFile("image.jpg")
result, err := manager.MultimodalEngine.OCRExtract(ctx, imageData, "zh")
if err == nil {
    log.Printf("识别文字: %s", result.Text)
    for _, region := range result.Regions {
        log.Printf("  区域: %v, 文字: %s", region.BBox, region.Text)
    }
}
```

## 🛡️ 高级特性

### 健康检查

```go
// 检查单个服务
if !manager.IsServiceHealthy("voice-engine") {
    log.Println("Voice Engine 不可用")
    return
}

// 获取所有服务状态
statuses := manager.GetAllServiceStatus(ctx)
for name, status := range statuses {
    log.Printf("%s: healthy=%v, url=%s",
        name, status.Healthy, status.BaseURL)
}
```

### 超时控制

```go
// 设置5秒超时
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
```

### 错误处理

```go
result, err := manager.VoiceEngine.SpeechToText(ctx, audioData, "zh", "base")
if err != nil {
    // 检查是否为熔断器错误
    if err == gobreaker.ErrOpenState {
        log.Println("熔断器开启，服务暂时不可用")
        return
    }

    // 检查是否为超时
    if err == context.DeadlineExceeded {
        log.Println("请求超时")
        return
    }

    // 其他错误
    log.Printf("请求失败: %v", err)
    return
}
```

## 🧪 运行测试

### 单元测试

```bash
go test ./pkg/clients/algo/...
```

### 集成测试

```bash
# 确保所有算法服务正在运行
go test -v ./tests/integration/algo_clients_integration_test.go
```

### 运行示例

```bash
go run examples/algo_client_example.go
```

## 📖 深入学习

### 文档

- **API集成指南**: [docs/algo-api-integration.md](docs/algo-api-integration.md)
- **客户端详细文档**: [pkg/clients/algo/README.md](pkg/clients/algo/README.md)
- **完整总结**: [ALGO_INTEGRATION_SUMMARY.md](ALGO_INTEGRATION_SUMMARY.md)

### 代码示例

- **基础示例**: [examples/algo_client_example.go](examples/algo_client_example.go)
- **AI-Orchestrator集成**: [cmd/ai-orchestrator/internal/application/algo_client_handler.go](cmd/ai-orchestrator/internal/application/algo_client_handler.go)

## 🔧 故障排查

### 问题1: 连接失败

```
Error: dial tcp: connect: connection refused
```

**解决方法**:
1. 检查服务是否启动
2. 验证服务URL配置
3. 确认端口未被占用

### 问题2: 超时

```
Error: context deadline exceeded
```

**解决方法**:
1. 增加context超时时间
2. 检查网络延迟
3. 确认服务负载

### 问题3: 熔断器开启

```
Error: circuit breaker is open
```

**解决方法**:
1. 等待30秒让熔断器恢复
2. 检查服务日志
3. 确认服务运行正常

## ✅ 检查清单

在生产环境部署前，请确认：

- [ ] 所有服务URL配置正确
- [ ] 健康检查正常
- [ ] 超时时间合理设置
- [ ] 错误处理完善
- [ ] 日志记录充分
- [ ] 集成测试通过
- [ ] 监控指标就位

## 🆘 获取帮助

- **文档**: 查看 `docs/` 目录
- **示例**: 查看 `examples/` 目录
- **测试**: 查看 `tests/integration/` 目录
- **Issue**: 在项目中创建Issue

## 🎯 下一步

1. 阅读完整文档: [docs/algo-api-integration.md](docs/algo-api-integration.md)
2. 查看示例代码: [examples/algo_client_example.go](examples/algo_client_example.go)
3. 运行集成测试: `./scripts/test-algo-clients.sh`
4. 在你的服务中集成客户端

---

**最后更新**: 2025-10-29
**版本**: 1.0.0
