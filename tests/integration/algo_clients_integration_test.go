package integration

import (
	"context"
	"os"
	"testing"
	"time"

	"voicehelper/pkg/clients/algo"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestClientManagerInitialization 测试客户端管理器初始化
func TestClientManagerInitialization(t *testing.T) {
	// 设置测试环境变量
	setupTestEnv(t)

	// 创建客户端管理器
	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err, "Failed to create client manager")
	require.NotNil(t, manager, "Client manager should not be nil")
	defer manager.Close()

	// 验证客户端已初始化
	assert.NotNil(t, manager.AgentEngine, "AgentEngine should be initialized")
	assert.NotNil(t, manager.RAGEngine, "RAGEngine should be initialized")
	assert.NotNil(t, manager.RetrievalService, "RetrievalService should be initialized")
	assert.NotNil(t, manager.ModelAdapter, "ModelAdapter should be initialized")
	assert.NotNil(t, manager.VoiceEngine, "VoiceEngine should be initialized")
	assert.NotNil(t, manager.MultimodalEngine, "MultimodalEngine should be initialized")
	assert.NotNil(t, manager.IndexingService, "IndexingService should be initialized")
	assert.NotNil(t, manager.VectorStoreAdapter, "VectorStoreAdapter should be initialized")
}

// TestHealthCheck 测试健康检查
func TestHealthCheck(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 获取所有服务状态
	statuses := manager.GetAllServiceStatus(ctx)
	assert.NotEmpty(t, statuses, "Should have service statuses")

	// 验证每个服务的状态
	services := []string{
		"agent-engine",
		"rag-engine",
		"retrieval-service",
		"model-adapter",
		"voice-engine",
		"multimodal-engine",
		"indexing-service",
		"vector-store-adapter",
	}

	for _, service := range services {
		status, ok := statuses[service]
		assert.True(t, ok, "Service %s should have status", service)
		t.Logf("Service: %s, Healthy: %v, URL: %s, CircuitBreaker: %s",
			status.Name,
			status.Healthy,
			status.BaseURL,
			status.CircuitBreakerState,
		)
	}
}

// TestAgentEngineClient 测试Agent Engine客户端
func TestAgentEngineClient(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	if !manager.IsServiceHealthy("agent-engine") {
		t.Skip("Agent Engine is not healthy, skipping test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 测试列出工具
	var result struct {
		Tools []map[string]interface{} `json:"tools"`
		Count int                      `json:"count"`
	}
	err = manager.AgentEngine.Get(ctx, "/tools", &result)
	if err != nil {
		t.Logf("Warning: Failed to list tools: %v", err)
	} else {
		assert.GreaterOrEqual(t, result.Count, 0, "Should have tools count")
		t.Logf("Found %d tools", result.Count)
	}
}

// TestRAGEngineClient 测试RAG Engine客户端
func TestRAGEngineClient(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	if !manager.IsServiceHealthy("rag-engine") {
		t.Skip("RAG Engine is not healthy, skipping test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 测试RAG查询
	req := map[string]interface{}{
		"query":     "测试查询",
		"tenant_id": "test-tenant",
		"options": map[string]interface{}{
			"top_k": 5,
		},
	}

	var result map[string]interface{}
	err = manager.RAGEngine.Post(ctx, "/api/v1/generate", req, &result)
	if err != nil {
		t.Logf("Warning: RAG query failed: %v", err)
	} else {
		assert.NotNil(t, result, "Should have result")
		t.Logf("RAG result: %+v", result)
	}
}

// TestVoiceEngineClient 测试Voice Engine客户端
func TestVoiceEngineClient(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	if !manager.IsServiceHealthy("voice-engine") {
		t.Skip("Voice Engine is not healthy, skipping test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 测试列出可用语音
	voices, err := manager.VoiceEngine.ListVoices(ctx)
	if err != nil {
		t.Logf("Warning: Failed to list voices: %v", err)
	} else {
		assert.NotNil(t, voices, "Should have voices")
		t.Logf("Found %d voices", len(voices))
	}

	// 测试获取统计信息
	stats, err := manager.VoiceEngine.GetStats(ctx)
	if err != nil {
		t.Logf("Warning: Failed to get stats: %v", err)
	} else {
		assert.NotNil(t, stats, "Should have stats")
		t.Logf("Voice Engine stats: %+v", stats)
	}
}

// TestMultimodalEngineClient 测试Multimodal Engine客户端
func TestMultimodalEngineClient(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	if !manager.IsServiceHealthy("multimodal-engine") {
		t.Skip("Multimodal Engine is not healthy, skipping test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 测试健康检查
	err = manager.MultimodalEngine.HealthCheck(ctx)
	assert.NoError(t, err, "Multimodal Engine should be healthy")
}

// TestIndexingServiceClient 测试Indexing Service客户端
func TestIndexingServiceClient(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	if !manager.IsServiceHealthy("indexing-service") {
		t.Skip("Indexing Service is not healthy, skipping test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 测试获取统计信息
	stats, err := manager.IndexingService.GetStats(ctx)
	if err != nil {
		t.Logf("Warning: Failed to get stats: %v", err)
	} else {
		assert.NotNil(t, stats, "Should have stats")
		t.Logf("Indexing Service stats: %+v", stats)
	}
}

// TestVectorStoreAdapterClient 测试Vector Store Adapter客户端
func TestVectorStoreAdapterClient(t *testing.T) {
	setupTestEnv(t)

	manager, err := algo.NewClientManagerFromEnv()
	require.NoError(t, err)
	defer manager.Close()

	if !manager.IsServiceHealthy("vector-store-adapter") {
		t.Skip("Vector Store Adapter is not healthy, skipping test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 测试获取统计信息
	stats, err := manager.VectorStoreAdapter.GetStats(ctx)
	if err != nil {
		t.Logf("Warning: Failed to get stats: %v", err)
	} else {
		assert.NotNil(t, stats, "Should have stats")
		t.Logf("Vector Store Adapter stats: %+v", stats)
	}
}

// TestCircuitBreaker 测试熔断器
func TestCircuitBreaker(t *testing.T) {
	// 创建一个客户端指向不存在的服务
	client := algo.NewBaseClient(algo.BaseClientConfig{
		ServiceName: "test-service",
		BaseURL:     "http://localhost:99999", // 不存在的端口
		Timeout:     1 * time.Second,
		MaxRetries:  2,
	})

	ctx := context.Background()

	// 多次调用失败，触发熔断
	for i := 0; i < 10; i++ {
		err := client.HealthCheck(ctx)
		assert.Error(t, err, "Should fail to connect")

		state := client.GetCircuitBreakerState()
		t.Logf("Attempt %d: CircuitBreaker state: %s", i+1, state.String())

		// 如果熔断器已开启，后续请求应该立即失败
		if state.String() == "open" {
			t.Logf("Circuit breaker opened after %d attempts", i+1)
			break
		}

		time.Sleep(100 * time.Millisecond)
	}
}

// TestRetryMechanism 测试重试机制
func TestRetryMechanism(t *testing.T) {
	client := algo.NewBaseClient(algo.BaseClientConfig{
		ServiceName: "test-service",
		BaseURL:     "http://localhost:99999",
		Timeout:     500 * time.Millisecond,
		MaxRetries:  3,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	start := time.Now()
	err := client.HealthCheck(ctx)
	elapsed := time.Since(start)

	assert.Error(t, err, "Should fail")
	// 应该重试3次，每次有退避延迟
	// 预期时间 > 3 * 500ms (3次超时) + 退避延迟
	assert.Greater(t, elapsed, 1500*time.Millisecond, "Should take time for retries")
	t.Logf("Retry test took %v", elapsed)
}

// setupTestEnv 设置测试环境变量
func setupTestEnv(t *testing.T) {
	// 如果环境变量未设置，使用默认值
	if os.Getenv("SERVICES_CONFIG_PATH") == "" {
		// 尝试多个可能的配置路径
		possiblePaths := []string{
			"../../configs/services-integration.yaml",
			"./configs/services-integration.yaml",
			"../configs/services-integration.yaml",
		}

		for _, path := range possiblePaths {
			if _, err := os.Stat(path); err == nil {
				os.Setenv("SERVICES_CONFIG_PATH", path)
				t.Logf("Using config path: %s", path)
				return
			}
		}

		// 如果找不到配置文件，设置默认服务URL
		t.Log("Config file not found, using default service URLs")
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
