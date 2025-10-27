package biz

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// TaskCreatedTotal 创建任务总数
	TaskCreatedTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "task",
			Name:      "created_total",
			Help:      "Total number of tasks created",
		},
		[]string{"type", "tenant_id"},
	)

	// TaskExecutionDuration 任务执行时长
	TaskExecutionDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "task",
			Name:      "execution_duration_seconds",
			Help:      "Task execution duration in seconds",
			Buckets:   []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300},
		},
		[]string{"type", "status", "tenant_id"},
	)

	// TaskStatusTotal 任务状态计数
	TaskStatusTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "task",
			Name:      "status_total",
			Help:      "Total number of tasks by status",
		},
		[]string{"type", "status", "tenant_id"},
	)

	// TaskTokensUsed 任务Token使用量
	TaskTokensUsed = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "task",
			Name:      "tokens_used",
			Help:      "Number of tokens used per task",
			Buckets:   []float64{100, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000},
		},
		[]string{"type", "model", "tenant_id"},
	)

	// TaskCostUSD 任务成本
	TaskCostUSD = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "task",
			Name:      "cost_usd",
			Help:      "Task cost in USD",
			Buckets:   []float64{0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1, 5, 10},
		},
		[]string{"type", "model", "tenant_id"},
	)

	// PipelineStepDuration Pipeline步骤执行时长
	PipelineStepDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "pipeline",
			Name:      "step_duration_seconds",
			Help:      "Pipeline step execution duration in seconds",
			Buckets:   []float64{0.05, 0.1, 0.5, 1, 2, 5, 10, 30},
		},
		[]string{"pipeline", "step", "service", "status"},
	)

	// ServiceCallTotal 服务调用总数
	ServiceCallTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "service",
			Name:      "call_total",
			Help:      "Total number of service calls",
		},
		[]string{"service", "method", "status"},
	)

	// ServiceCallDuration 服务调用时长
	ServiceCallDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "service",
			Name:      "call_duration_seconds",
			Help:      "Service call duration in seconds",
			Buckets:   []float64{0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10},
		},
		[]string{"service", "method"},
	)

	// CircuitBreakerStateGauge 熔断器状态
	CircuitBreakerStateGauge = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Namespace: "ai_orchestrator",
			Subsystem: "circuit_breaker",
			Name:      "state",
			Help:      "Circuit breaker state (0=closed, 1=half-open, 2=open)",
		},
		[]string{"service"},
	)
)
