package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"voicehelper/pkg/clients/algo"
)

func main() {
	// 创建客户端管理器
	// 方式1: 从环境变量创建
	manager, err := algo.NewClientManagerFromEnv()
	if err != nil {
		log.Fatalf("Failed to create client manager: %v", err)
	}
	defer manager.Close()

	// 方式2: 从配置文件创建
	// manager, err := algo.NewClientManagerFromConfig("configs/algo-services.yaml")

	log.Println("🚀 Algorithm Service Client Example")
	log.Println("=" + string(make([]byte, 50)) + "=")

	ctx := context.Background()

	// 1. 健康检查示例
	demonstrateHealthCheck(ctx, manager)

	// 2. Agent Engine 示例
	demonstrateAgentEngine(ctx, manager)

	// 3. RAG Engine 示例
	demonstrateRAGEngine(ctx, manager)

	// 4. Retrieval Service 示例
	demonstrateRetrievalService(ctx, manager)

	// 5. Voice Engine 示例
	demonstrateVoiceEngine(ctx, manager)

	// 6. Multimodal Engine 示例
	demonstrateMultimodalEngine(ctx, manager)

	// 7. Indexing Service 示例
	demonstrateIndexingService(ctx, manager)

	// 8. Vector Store Adapter 示例
	demonstrateVectorStoreAdapter(ctx, manager)

	log.Println("\n✅ All examples completed!")
}

// demonstrateHealthCheck 演示健康检查
func demonstrateHealthCheck(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n📊 1. Health Check")
	log.Println("-" + string(make([]byte, 50)) + "-")

	// 获取所有服务状态
	statuses := manager.GetAllServiceStatus(ctx)

	healthyCount := 0
	for name, status := range statuses {
		statusIcon := "❌"
		if status.Healthy {
			statusIcon = "✅"
			healthyCount++
		}
		log.Printf("%s %s: %s (Circuit Breaker: %s)",
			statusIcon,
			name,
			status.BaseURL,
			status.CircuitBreakerState,
		)
	}

	log.Printf("\nSummary: %d/%d services are healthy", healthyCount, len(statuses))
}

// demonstrateAgentEngine 演示Agent Engine
func demonstrateAgentEngine(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n🤖 2. Agent Engine")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("agent-engine") {
		log.Println("⚠️  Agent Engine is not healthy, skipping...")
		return
	}

	// 列出可用工具
	var toolsResult struct {
		Tools []map[string]interface{} `json:"tools"`
		Count int                      `json:"count"`
	}

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	err := manager.AgentEngine.Get(ctx, "/tools", &toolsResult)
	if err != nil {
		log.Printf("❌ Failed to list tools: %v", err)
		return
	}

	log.Printf("✅ Found %d tools", toolsResult.Count)
	if len(toolsResult.Tools) > 0 {
		log.Printf("   First tool: %v", toolsResult.Tools[0]["name"])
	}

	// 获取统计信息
	var statsResult map[string]interface{}
	err = manager.AgentEngine.Get(ctx, "/stats", &statsResult)
	if err != nil {
		log.Printf("⚠️  Failed to get stats: %v", err)
	} else {
		log.Printf("✅ Agent stats: %v", statsResult)
	}
}

// demonstrateRAGEngine 演示RAG Engine
func demonstrateRAGEngine(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n📚 3. RAG Engine")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("rag-engine") {
		log.Println("⚠️  RAG Engine is not healthy, skipping...")
		return
	}

	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// 注意：这是一个示例请求，实际使用时需要确保有相关的文档数据
	req := map[string]interface{}{
		"query":     "测试查询",
		"tenant_id": "example-tenant",
		"options": map[string]interface{}{
			"top_k": 5,
		},
	}

	var result map[string]interface{}
	err := manager.RAGEngine.Post(ctx, "/api/v1/generate", req, &result)
	if err != nil {
		log.Printf("⚠️  RAG query failed (expected if no data): %v", err)
	} else {
		log.Printf("✅ RAG query succeeded")
		if answer, ok := result["answer"].(string); ok {
			log.Printf("   Answer: %s", answer)
		}
	}
}

// demonstrateRetrievalService 演示Retrieval Service
func demonstrateRetrievalService(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n🔍 4. Retrieval Service")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("retrieval-service") {
		log.Println("⚠️  Retrieval Service is not healthy, skipping...")
		return
	}

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	req := map[string]interface{}{
		"query":     "测试检索",
		"tenant_id": "example-tenant",
		"top_k":     10,
		"method":    "hybrid",
	}

	var result map[string]interface{}
	err := manager.RetrievalService.Post(ctx, "/retrieve", req, &result)
	if err != nil {
		log.Printf("⚠️  Retrieval failed (expected if no data): %v", err)
	} else {
		log.Printf("✅ Retrieval succeeded")
	}
}

// demonstrateVoiceEngine 演示Voice Engine
func demonstrateVoiceEngine(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n🎤 5. Voice Engine")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("voice-engine") {
		log.Println("⚠️  Voice Engine is not healthy, skipping...")
		return
	}

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// 列出可用语音
	voices, err := manager.VoiceEngine.ListVoices(ctx)
	if err != nil {
		log.Printf("❌ Failed to list voices: %v", err)
		return
	}

	log.Printf("✅ Found %d voices", len(voices))
	if len(voices) > 0 {
		log.Printf("   First voice: %s (%s)", voices[0].Name, voices[0].Language)
	}

	// 获取统计信息
	stats, err := manager.VoiceEngine.GetStats(ctx)
	if err != nil {
		log.Printf("⚠️  Failed to get stats: %v", err)
	} else {
		log.Printf("✅ Voice Engine stats retrieved")
	}

	// TTS示例（如果需要）
	// ttsReq := &algo.TTSRequest{
	// 	Text:  "你好，世界",
	// 	Voice: "zh-CN-XiaoxiaoNeural",
	// }
	// audioData, err := manager.VoiceEngine.TextToSpeech(ctx, ttsReq)
	// if err == nil {
	// 	log.Printf("✅ TTS generated %d bytes of audio", len(audioData))
	// }
}

// demonstrateMultimodalEngine 演示Multimodal Engine
func demonstrateMultimodalEngine(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n🖼️  6. Multimodal Engine")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("multimodal-engine") {
		log.Println("⚠️  Multimodal Engine is not healthy, skipping...")
		return
	}

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// 健康检查
	err := manager.MultimodalEngine.HealthCheck(ctx)
	if err != nil {
		log.Printf("❌ Health check failed: %v", err)
		return
	}

	log.Printf("✅ Multimodal Engine is healthy")

	// OCR示例（需要实际的图片数据）
	// imageData, err := os.ReadFile("test_image.jpg")
	// if err == nil {
	// 	result, err := manager.MultimodalEngine.OCRExtract(ctx, imageData, "zh")
	// 	if err == nil {
	// 		log.Printf("✅ OCR extracted text: %s", result.Text)
	// 	}
	// }
}

// demonstrateIndexingService 演示Indexing Service
func demonstrateIndexingService(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n📄 7. Indexing Service")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("indexing-service") {
		log.Println("⚠️  Indexing Service is not healthy, skipping...")
		return
	}

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// 获取统计信息
	stats, err := manager.IndexingService.GetStats(ctx)
	if err != nil {
		log.Printf("⚠️  Failed to get stats: %v", err)
	} else {
		log.Printf("✅ Indexing stats:")
		log.Printf("   Documents processed: %d", stats.DocumentsProcessed)
		log.Printf("   Chunks created: %d", stats.ChunksCreated)
		log.Printf("   Vectors stored: %d", stats.VectorsStored)
		log.Printf("   Avg processing time: %.2fs", stats.ProcessingTimeAvg)
	}

	// 增量更新示例
	// updateReq := &algo.IncrementalUpdateRequest{
	// 	DocumentID: "doc-example",
	// 	TenantID:   "example-tenant",
	// 	Chunks: []algo.DocumentChunk{
	// 		{
	// 			Content: "示例文档内容",
	// 			Metadata: map[string]interface{}{
	// 				"page": 1,
	// 			},
	// 		},
	// 	},
	// }
	// result, err := manager.IndexingService.IncrementalUpdate(ctx, updateReq)
}

// demonstrateVectorStoreAdapter 演示Vector Store Adapter
func demonstrateVectorStoreAdapter(ctx context.Context, manager *algo.ClientManager) {
	log.Println("\n🗄️  8. Vector Store Adapter")
	log.Println("-" + string(make([]byte, 50)) + "-")

	if !manager.IsServiceHealthy("vector-store-adapter") {
		log.Println("⚠️  Vector Store Adapter is not healthy, skipping...")
		return
	}

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// 获取统计信息
	stats, err := manager.VectorStoreAdapter.GetStats(ctx)
	if err != nil {
		log.Printf("⚠️  Failed to get stats: %v", err)
	} else {
		log.Printf("✅ Vector Store stats retrieved")
	}

	// 获取集合计数示例
	// countResult, err := manager.VectorStoreAdapter.GetCollectionCount(ctx, "documents", "milvus")
	// if err == nil {
	// 	log.Printf("✅ Collection 'documents' has %d vectors", countResult.Count)
	// }

	// 插入向量示例
	// insertReq := &algo.InsertVectorsRequest{
	// 	Backend: "milvus",
	// 	Data: []algo.VectorData{
	// 		{
	// 			ID:     "vec-example",
	// 			Vector: make([]float64, 768), // 示例向量
	// 			Metadata: map[string]interface{}{
	// 				"document_id": "doc-1",
	// 				"tenant_id":   "example-tenant",
	// 			},
	// 		},
	// 	},
	// }
	// result, err := manager.VectorStoreAdapter.InsertVectors(ctx, "documents", insertReq)
}

// init 初始化环境
func init() {
	// 如果未设置配置路径，尝试使用默认路径
	if os.Getenv("SERVICES_CONFIG_PATH") == "" {
		configPaths := []string{
			"configs/algo-services.yaml",
			"../configs/algo-services.yaml",
			"../../configs/algo-services.yaml",
		}

		for _, path := range configPaths {
			if _, err := os.Stat(path); err == nil {
				os.Setenv("SERVICES_CONFIG_PATH", path)
				fmt.Printf("Using config: %s\n", path)
				break
			}
		}
	}

	// 如果仍未找到配置，设置默认服务URL
	if os.Getenv("SERVICES_CONFIG_PATH") == "" {
		fmt.Println("Config file not found, using default service URLs")
		setDefaultServiceURLs()
	}
}

// setDefaultServiceURLs 设置默认服务URL
func setDefaultServiceURLs() {
	defaults := map[string]string{
		"AGENT_ENGINE_URL":         "http://localhost:8010",
		"RAG_ENGINE_URL":           "http://localhost:8006",
		"RETRIEVAL_SERVICE_URL":    "http://localhost:8012",
		"MODEL_ADAPTER_URL":        "http://localhost:8005",
		"VOICE_ENGINE_URL":         "http://localhost:8004",
		"MULTIMODAL_ENGINE_URL":    "http://localhost:8007",
		"INDEXING_SERVICE_URL":     "http://localhost:8000",
		"VECTOR_STORE_ADAPTER_URL": "http://localhost:8009",
	}

	for key, value := range defaults {
		if os.Getenv(key) == "" {
			os.Setenv(key, value)
		}
	}
}
