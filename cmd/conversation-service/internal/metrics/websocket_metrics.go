package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// WebSocketConnectionsTotal WebSocket连接总数
	WebSocketConnectionsTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "websocket_connections_total",
		Help: "Total number of WebSocket connections",
	})

	// WebSocketConnectionsActive 当前活跃的WebSocket连接数
	WebSocketConnectionsActive = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "websocket_connections_active",
		Help: "Number of active WebSocket connections",
	})

	// WebSocketMessagesSent 发送的消息总数
	WebSocketMessagesSent = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "websocket_messages_sent_total",
		Help: "Total number of messages sent",
	}, []string{"type"})

	// WebSocketMessagesReceived 接收的消息总数
	WebSocketMessagesReceived = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "websocket_messages_received_total",
		Help: "Total number of messages received",
	}, []string{"type"})

	// WebSocketMessageDuration 消息处理延迟
	WebSocketMessageDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name: "websocket_message_duration_seconds",
		Help: "WebSocket message processing duration in seconds",
		Buckets: []float64{0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0},
	}, []string{"type"})

	// WebSocketErrors WebSocket错误计数
	WebSocketErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "websocket_errors_total",
		Help: "Total number of WebSocket errors",
	}, []string{"error_type"})

	// SessionCacheHits 会话缓存命中数
	SessionCacheHits = promauto.NewCounter(prometheus.CounterOpts{
		Name: "session_cache_hits_total",
		Help: "Total number of session cache hits",
	})

	// SessionCacheMisses 会话缓存未命中数
	SessionCacheMisses = promauto.NewCounter(prometheus.CounterOpts{
		Name: "session_cache_misses_total",
		Help: "Total number of session cache misses",
	})

	// SyncEventsTotal 同步事件总数
	SyncEventsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "sync_events_total",
		Help: "Total number of sync events",
	}, []string{"event_type"})

	// ActiveDevicesPerUser 每个用户的活跃设备数
	ActiveDevicesPerUser = promauto.NewHistogram(prometheus.HistogramOpts{
		Name: "active_devices_per_user",
		Help: "Number of active devices per user",
		Buckets: []float64{1, 2, 3, 4, 5, 10},
	})
)

