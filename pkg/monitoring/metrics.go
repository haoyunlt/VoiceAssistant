package monitoring

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// RequestsTotal counts total requests.
	RequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"service", "method", "path", "status"},
	)

	// RequestDuration measures request duration.
	RequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
		},
		[]string{"service", "method", "path"},
	)

	// ConversationSuccessRate measures conversation success rate.
	ConversationSuccessRate = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "conversation_success_rate",
			Help: "Conversation success rate by mode",
		},
		[]string{"mode", "tenant_id"},
	)

	// LLMCostTotal counts total LLM cost.
	LLMCostTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "llm_cost_dollars_total",
			Help: "Total LLM cost in dollars",
		},
		[]string{"model", "provider", "tenant_id"},
	)

	// MilvusSearchDuration measures Milvus search duration.
	MilvusSearchDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "milvus_search_duration_seconds",
			Help:    "Milvus search duration in seconds",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1},
		},
		[]string{"collection"},
	)
)
