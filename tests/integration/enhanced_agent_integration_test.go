package integration

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"voicehelper/cmd/ai-orchestrator/internal/application"
	"voicehelper/cmd/ai-orchestrator/internal/infrastructure"
	"voicehelper/pkg/config"
)

// 测试配置
var (
	testTenantID = "test-tenant-001"
	testUserID   = "test-user-001"
)

// setupTestHandler 设置测试handler
func setupTestHandler(t *testing.T) *application.EnhancedAgentHandler {
	// 从环境变量或配置文件加载服务地址
	cfg, err := config.LoadServicesConfigFromEnv()
	if err != nil {
		// 回退到默认地址（仅用于测试）
		cfg = &config.ServicesConfig{
			Services: []config.ServiceConfig{
				{Name: "agent-engine", Type: "http", Address: getEnv("AGENT_ENGINE_URL", "http://localhost:8003")},
				{Name: "model-adapter", Type: "http", Address: getEnv("MODEL_ADAPTER_URL", "http://localhost:8005")},
				{Name: "rag-engine", Type: "http", Address: getEnv("RAG_ENGINE_URL", "http://localhost:8006")},
			},
		}
	}

	// 创建AI服务客户端
	aiClient := infrastructure.NewAIServiceClientFromConfig(
		cfg.GetHTTPServiceURLs(),
		60*time.Second,
	)

	// 创建handler
	logger := newTestLogger()
	handler := application.NewEnhancedAgentHandler(aiClient, logger)

	return handler
}

// getEnv 获取环境变量，如果不存在则返回默认值
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// newTestLogger 创建测试logger
func newTestLogger() *testLogger {
	return &testLogger{}
}

// testLogger 简单的测试logger实现
type testLogger struct{}

func (l *testLogger) Log(level string, keyvals ...interface{}) error {
	fmt.Printf("[%s] %v\n", level, keyvals)
	return nil
}

// ============ Multi-Agent 协作测试 ============

func TestMultiAgentCollaborate(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	handler := setupTestHandler(t)
	ctx := context.Background()

	tests := []struct {
		name     string
		request  *application.MultiAgentCollaborateRequest
		wantErr  bool
		validate func(t *testing.T, resp *application.MultiAgentCollaborateResponse)
	}{
		{
			name: "并行模式协作",
			request: &application.MultiAgentCollaborateRequest{
				Task:     "分析市场趋势并生成报告",
				Mode:     "parallel",
				Priority: 8,
				TenantID: testTenantID,
				UserID:   testUserID,
			},
			wantErr: false,
			validate: func(t *testing.T, resp *application.MultiAgentCollaborateResponse) {
				assert.NotEmpty(t, resp.FinalResult)
				assert.Equal(t, "parallel", resp.Mode)
				assert.Greater(t, len(resp.AgentsInvolved), 0)
				assert.NotEmpty(t, resp.Status)
			},
		},
		{
			name: "串行模式协作",
			request: &application.MultiAgentCollaborateRequest{
				Task:     "执行复杂任务流程",
				Mode:     "sequential",
				Priority: 5,
				TenantID: testTenantID,
				UserID:   testUserID,
			},
			wantErr: false,
			validate: func(t *testing.T, resp *application.MultiAgentCollaborateResponse) {
				assert.NotEmpty(t, resp.FinalResult)
				assert.Equal(t, "sequential", resp.Mode)
			},
		},
		{
			name: "空任务应该失败",
			request: &application.MultiAgentCollaborateRequest{
				Task:     "",
				Mode:     "parallel",
				TenantID: testTenantID,
				UserID:   testUserID,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := handler.MultiAgentCollaborate(ctx, tt.request)

			if tt.wantErr {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, resp)

			if tt.validate != nil {
				tt.validate(t, resp)
			}
		})
	}
}

func TestAgentLifecycle(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	handler := setupTestHandler(t)
	ctx := context.Background()

	agentID := fmt.Sprintf("test-agent-%d", time.Now().Unix())

	// 1. 注册Agent
	t.Run("RegisterAgent", func(t *testing.T) {
		req := &application.RegisterAgentRequest{
			AgentID:  agentID,
			Role:     "researcher",
			Tools:    []string{"search", "analyze"},
			TenantID: testTenantID,
			UserID:   testUserID,
		}

		resp, err := handler.RegisterAgent(ctx, req)
		require.NoError(t, err)
		assert.Equal(t, agentID, resp.AgentID)
		assert.Equal(t, "researcher", resp.Role)
	})

	// 2. 列出Agents
	t.Run("ListAgents", func(t *testing.T) {
		resp, err := handler.ListAgents(ctx, testTenantID, testUserID)
		require.NoError(t, err)
		assert.Greater(t, resp.Count, 0)

		// 验证刚注册的agent在列表中
		found := false
		for _, agent := range resp.Agents {
			if agent.AgentID == agentID {
				found = true
				assert.Equal(t, "researcher", agent.Role)
				break
			}
		}
		assert.True(t, found, "Registered agent should be in the list")
	})

	// 3. 获取统计信息
	t.Run("GetMultiAgentStats", func(t *testing.T) {
		resp, err := handler.GetMultiAgentStats(ctx, testTenantID, testUserID)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, resp.ActiveAgents, 1)
	})

	// 4. 注销Agent
	t.Run("UnregisterAgent", func(t *testing.T) {
		err := handler.UnregisterAgent(ctx, agentID, testTenantID, testUserID)
		require.NoError(t, err)
	})
}

// ============ Self-RAG 测试 ============

func TestSelfRAGQuery(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	handler := setupTestHandler(t)
	ctx := context.Background()

	tests := []struct {
		name     string
		request  *application.SelfRAGQueryRequest
		wantErr  bool
		validate func(t *testing.T, resp *application.SelfRAGQueryResponse)
	}{
		{
			name: "自适应模式查询",
			request: &application.SelfRAGQueryRequest{
				Query:           "什么是人工智能？",
				Mode:            "adaptive",
				EnableCitations: true,
				MaxRefinements:  2,
				TenantID:        testTenantID,
				UserID:          testUserID,
			},
			wantErr: false,
			validate: func(t *testing.T, resp *application.SelfRAGQueryResponse) {
				assert.NotEmpty(t, resp.Answer)
				assert.Greater(t, resp.Confidence, 0.0)
				assert.NotEmpty(t, resp.RetrievalStrategy)
				assert.GreaterOrEqual(t, resp.RefinementCount, 0)
			},
		},
		{
			name: "快速模式查询",
			request: &application.SelfRAGQueryRequest{
				Query:           "今天天气怎么样？",
				Mode:            "fast",
				EnableCitations: false,
				TenantID:        testTenantID,
				UserID:          testUserID,
			},
			wantErr: false,
			validate: func(t *testing.T, resp *application.SelfRAGQueryResponse) {
				assert.NotEmpty(t, resp.Answer)
			},
		},
		{
			name: "空查询应该失败",
			request: &application.SelfRAGQueryRequest{
				Query:    "",
				TenantID: testTenantID,
				UserID:   testUserID,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := handler.SelfRAGQuery(ctx, tt.request)

			if tt.wantErr {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, resp)

			if tt.validate != nil {
				tt.validate(t, resp)
			}
		})
	}
}

func TestSelfRAGStats(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	handler := setupTestHandler(t)
	ctx := context.Background()

	resp, err := handler.GetSelfRAGStats(ctx, testTenantID, testUserID)
	require.NoError(t, err)
	assert.GreaterOrEqual(t, resp.TotalQueries, 0)
	assert.GreaterOrEqual(t, resp.CacheHitRate, 0.0)
	assert.LessOrEqual(t, resp.CacheHitRate, 1.0)
}

// ============ Smart Memory 测试 ============

func TestSmartMemoryLifecycle(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	handler := setupTestHandler(t)
	ctx := context.Background()

	var memoryID string

	// 1. 添加记忆
	t.Run("AddMemory", func(t *testing.T) {
		req := &application.AddMemoryRequest{
			Content:    "今天学习了Go语言的并发编程",
			Tier:       "short_term",
			Importance: 0.8,
			Metadata: map[string]interface{}{
				"category": "learning",
				"topic":    "golang",
			},
			TenantID: testTenantID,
			UserID:   testUserID,
		}

		resp, err := handler.AddMemory(ctx, req)
		require.NoError(t, err)
		assert.NotEmpty(t, resp.MemoryID)
		assert.Equal(t, "short_term", resp.Tier)
		assert.Greater(t, resp.Importance, 0.0)

		memoryID = resp.MemoryID
	})

	// 2. 检索记忆
	t.Run("RetrieveMemory", func(t *testing.T) {
		req := &application.RetrieveMemoryRequest{
			Query:         "Go语言",
			TopK:          5,
			MinImportance: 0.5,
			TenantID:      testTenantID,
			UserID:        testUserID,
		}

		resp, err := handler.RetrieveMemory(ctx, req)
		require.NoError(t, err)
		assert.Greater(t, resp.Count, 0)

		// 验证刚添加的记忆在结果中
		found := false
		for _, mem := range resp.Memories {
			if mem.MemoryID == memoryID {
				found = true
				assert.Contains(t, mem.Content, "Go语言")
				assert.Equal(t, "short_term", mem.Tier)
				break
			}
		}
		assert.True(t, found, "Added memory should be retrievable")
	})

	// 3. 获取统计信息
	t.Run("GetMemoryStats", func(t *testing.T) {
		resp, err := handler.GetMemoryStats(ctx, testTenantID, testUserID)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, resp.TotalAdded, 1)
		assert.GreaterOrEqual(t, resp.TotalMemories, 1)
	})

	// 4. 维护记忆
	t.Run("MaintainMemory", func(t *testing.T) {
		resp, err := handler.MaintainMemory(ctx, testTenantID, testUserID)
		require.NoError(t, err)
		assert.NotNil(t, resp)
	})
}

func TestMemoryCompress(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	handler := setupTestHandler(t)
	ctx := context.Background()

	// 先添加一些记忆
	for i := 0; i < 5; i++ {
		req := &application.AddMemoryRequest{
			Content:    fmt.Sprintf("测试记忆 %d", i),
			Tier:       "short_term",
			Importance: 0.5,
			TenantID:   testTenantID,
			UserID:     testUserID,
		}
		_, err := handler.AddMemory(ctx, req)
		require.NoError(t, err)
	}

	// 压缩记忆
	t.Run("CompressMemory", func(t *testing.T) {
		resp, err := handler.CompressMemory(ctx, "short_term", testTenantID, testUserID)
		require.NoError(t, err)
		assert.NotNil(t, resp)
		// 压缩可能不会立即执行（取决于记忆数量阈值）
		// 所以只验证返回了响应
	})
}

// ============ 性能测试 ============

func BenchmarkMultiAgentCollaborate(b *testing.B) {
	handler := setupTestHandler(&testing.T{})
	ctx := context.Background()

	req := &application.MultiAgentCollaborateRequest{
		Task:     "生成简单报告",
		Mode:     "parallel",
		Priority: 5,
		TenantID: testTenantID,
		UserID:   testUserID,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := handler.MultiAgentCollaborate(ctx, req)
		if err != nil {
			b.Fatalf("MultiAgentCollaborate failed: %v", err)
		}
	}
}

func BenchmarkSelfRAGQuery(b *testing.B) {
	handler := setupTestHandler(&testing.T{})
	ctx := context.Background()

	req := &application.SelfRAGQueryRequest{
		Query:    "简单问题",
		Mode:     "fast",
		TenantID: testTenantID,
		UserID:   testUserID,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := handler.SelfRAGQuery(ctx, req)
		if err != nil {
			b.Fatalf("SelfRAGQuery failed: %v", err)
		}
	}
}

func BenchmarkAddMemory(b *testing.B) {
	handler := setupTestHandler(&testing.T{})
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req := &application.AddMemoryRequest{
			Content:  fmt.Sprintf("测试记忆 %d", i),
			Tier:     "short_term",
			TenantID: testTenantID,
			UserID:   testUserID,
		}
		_, err := handler.AddMemory(ctx, req)
		if err != nil {
			b.Fatalf("AddMemory failed: %v", err)
		}
	}
}

