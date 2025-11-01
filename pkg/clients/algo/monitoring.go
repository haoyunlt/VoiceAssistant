package algo

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/sony/gobreaker"
)

// CircuitBreakerStats 熔断器统计信息
type CircuitBreakerStats struct {
	Name  string `json:"name"`
	State string `json:"state"`
	gobreaker.Counts
}

// GetCircuitBreakerStats 获取所有服务的熔断器状态
func (m *ClientManager) GetCircuitBreakerStats() map[string]CircuitBreakerStats {
	stats := make(map[string]CircuitBreakerStats)

	clients := []struct {
		name   string
		client *BaseClient
	}{
		{"agent-engine", m.AgentEngine},
		{"retrieval-service", m.RetrievalService},
		{"model-adapter", m.ModelAdapter},
	}

	for _, c := range clients {
		if c.client != nil {
			stats[c.name] = CircuitBreakerStats{
				Name:   c.name,
				State:  c.client.GetCircuitBreakerState().String(),
				Counts: c.client.circuitBreaker.Counts(),
			}
		}
	}

	// Voice Engine
	if m.VoiceEngine != nil {
		stats["voice-engine"] = CircuitBreakerStats{
			Name:   "voice-engine",
			State:  m.VoiceEngine.GetCircuitBreakerState().String(),
			Counts: m.VoiceEngine.circuitBreaker.Counts(),
		}
	}

	// Multimodal Engine
	if m.MultimodalEngine != nil {
		stats["multimodal-engine"] = CircuitBreakerStats{
			Name:   "multimodal-engine",
			State:  m.MultimodalEngine.GetCircuitBreakerState().String(),
			Counts: m.MultimodalEngine.circuitBreaker.Counts(),
		}
	}

	// Indexing Service
	if m.IndexingService != nil {
		stats["indexing-service"] = CircuitBreakerStats{
			Name:   "indexing-service",
			State:  m.IndexingService.GetCircuitBreakerState().String(),
			Counts: m.IndexingService.circuitBreaker.Counts(),
		}
	}

	// Vector Store Adapter
	if m.VectorStoreAdapter != nil {
		stats["vector-store-adapter"] = CircuitBreakerStats{
			Name:   "vector-store-adapter",
			State:  m.VectorStoreAdapter.GetCircuitBreakerState().String(),
			Counts: m.VectorStoreAdapter.circuitBreaker.Counts(),
		}
	}

	// Knowledge Service
	if m.KnowledgeService != nil {
		stats["knowledge-service"] = CircuitBreakerStats{
			Name:   "knowledge-service",
			State:  m.KnowledgeService.GetCircuitBreakerState().String(),
			Counts: m.KnowledgeService.circuitBreaker.Counts(),
		}
	}

	return stats
}

// HTTPHandler 提供 HTTP 端点获取熔断器状态
func (m *ClientManager) HTTPHandler() http.Handler {
	mux := http.NewServeMux()

	// 熔断器状态
	mux.HandleFunc("/circuit-breakers", func(w http.ResponseWriter, r *http.Request) {
		stats := m.GetCircuitBreakerStats()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(stats)
	})

	// 服务健康状态
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		healthStatus := m.GetHealthStatus()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":   "healthy",
			"services": healthStatus,
		})
	})

	// 详细服务状态
	mux.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		if ctx == nil {
			ctx = context.Background()
		}
		status := m.GetAllServiceStatus(ctx)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(status)
	})

	return mux
}
