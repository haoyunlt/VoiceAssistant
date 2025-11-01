package middleware

import (
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// HTTP 请求计数
	httpRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "conversation_http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status", "tenant_id"},
	)

	// HTTP 请求延迟
	httpRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "conversation_http_request_duration_seconds",
			Help:    "HTTP request latency",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2, 5},
		},
		[]string{"method", "path", "tenant_id"},
	)

	// 对话操作计数
	conversationOperations = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "conversation_operations_total",
			Help: "Total number of conversation operations",
		},
		[]string{"operation", "status", "tenant_id"},
	)

	// 对话创建延迟
	conversationCreateDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "conversation_create_duration_seconds",
			Help:    "Conversation creation duration",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"tenant_id"},
	)

	// 消息发送延迟
	messageSendDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "message_send_duration_seconds",
			Help:    "Message send duration",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"tenant_id"},
	)

	// 活跃对话数
	activeConversations = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "conversation_active_total",
			Help: "Number of active conversations",
		},
		[]string{"tenant_id"},
	)

	// WebSocket 连接数
	websocketConnections = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "conversation_websocket_connections",
			Help: "Current number of WebSocket connections",
		},
		[]string{"tenant_id"},
	)

	// 缓存命中率
	cacheHits = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "conversation_cache_hits_total",
			Help: "Total cache hits",
		},
		[]string{"cache_type", "result"}, // result: hit/miss
	)

	// Redis 操作延迟
	redisOperationDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "conversation_redis_operation_duration_seconds",
			Help:    "Redis operation duration",
			Buckets: []float64{0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1},
		},
		[]string{"operation", "status"},
	)

	// 数据库查询延迟
	dbQueryDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "conversation_db_query_duration_seconds",
			Help:    "Database query duration",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1},
		},
		[]string{"query_type", "status"},
	)

	// AI 请求延迟
	aiRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "conversation_ai_request_duration_seconds",
			Help:    "AI request duration",
			Buckets: []float64{0.1, 0.5, 1, 2, 5, 10, 30},
		},
		[]string{"mode", "status"},
	)

	// Token 使用量
	tokenUsage = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "conversation_token_usage_total",
			Help: "Total token usage",
		},
		[]string{"tenant_id", "type"}, // type: prompt/completion
	)

	// 错误计数
	errorCount = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "conversation_errors_total",
			Help: "Total number of errors",
		},
		[]string{"type", "tenant_id"},
	)
)

// MetricsMiddleware Prometheus 指标采集中间件
func MetricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 跳过 metrics 端点本身
		if c.Request.URL.Path == "/metrics" {
			c.Next()
			return
		}

		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method

		// 处理请求
		c.Next()

		// 获取租户 ID
		tenantID := c.GetString("tenant_id")
		if tenantID == "" {
			tenantID = "unknown"
		}

		// 记录延迟
		duration := time.Since(start).Seconds()
		httpRequestDuration.WithLabelValues(method, path, tenantID).Observe(duration)

		// 记录请求计数
		status := strconv.Itoa(c.Writer.Status())
		httpRequestsTotal.WithLabelValues(method, path, status, tenantID).Inc()

		// 记录错误
		if c.Writer.Status() >= 400 {
			errorType := "client_error"
			if c.Writer.Status() >= 500 {
				errorType = "server_error"
			}
			errorCount.WithLabelValues(errorType, tenantID).Inc()
		}
	}
}

// RecordConversationOperation 记录对话操作
func RecordConversationOperation(operation, status, tenantID string) {
	conversationOperations.WithLabelValues(operation, status, tenantID).Inc()
}

// RecordConversationCreateDuration 记录对话创建延迟
func RecordConversationCreateDuration(tenantID string, duration time.Duration) {
	conversationCreateDuration.WithLabelValues(tenantID).Observe(duration.Seconds())
}

// RecordMessageSendDuration 记录消息发送延迟
func RecordMessageSendDuration(tenantID string, duration time.Duration) {
	messageSendDuration.WithLabelValues(tenantID).Observe(duration.Seconds())
}

// SetActiveConversations 设置活跃对话数
func SetActiveConversations(tenantID string, count float64) {
	activeConversations.WithLabelValues(tenantID).Set(count)
}

// IncWebSocketConnections 增加 WebSocket 连接数
func IncWebSocketConnections(tenantID string) {
	websocketConnections.WithLabelValues(tenantID).Inc()
}

// DecWebSocketConnections 减少 WebSocket 连接数
func DecWebSocketConnections(tenantID string) {
	websocketConnections.WithLabelValues(tenantID).Dec()
}

// RecordCacheHit 记录缓存命中
func RecordCacheHit(cacheType string, hit bool) {
	result := "miss"
	if hit {
		result = "hit"
	}
	cacheHits.WithLabelValues(cacheType, result).Inc()
}

// RecordRedisOperation 记录 Redis 操作
func RecordRedisOperation(operation, status string, duration time.Duration) {
	redisOperationDuration.WithLabelValues(operation, status).Observe(duration.Seconds())
}

// RecordDBQuery 记录数据库查询
func RecordDBQuery(queryType, status string, duration time.Duration) {
	dbQueryDuration.WithLabelValues(queryType, status).Observe(duration.Seconds())
}

// RecordAIRequest 记录 AI 请求
func RecordAIRequest(mode, status string, duration time.Duration) {
	aiRequestDuration.WithLabelValues(mode, status).Observe(duration.Seconds())
}

// RecordTokenUsage 记录 Token 使用量
func RecordTokenUsage(tenantID, tokenType string, count int) {
	tokenUsage.WithLabelValues(tenantID, tokenType).Add(float64(count))
}

// GetMetricsRegistry 获取 Prometheus 注册表
func GetMetricsRegistry() *prometheus.Registry {
	return prometheus.DefaultRegisterer.(*prometheus.Registry)
}
