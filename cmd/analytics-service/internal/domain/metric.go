package domain

import "time"

// Metric 指标聚合根
type Metric struct {
	ID         string
	TenantID   string
	Type       MetricType
	Name       string
	Value      float64
	Dimensions map[string]string
	Timestamp  time.Time
}

// MetricType 指标类型
type MetricType string

const (
	MetricTypeCounter   MetricType = "counter"   // 计数器
	MetricTypeGauge     MetricType = "gauge"     // 仪表盘
	MetricTypeHistogram MetricType = "histogram" // 直方图
)

// UsageStats 使用统计
type UsageStats struct {
	TenantID           string
	TotalConversations int64
	TotalMessages      int64
	TotalTokens        int64
	TotalCost          float64
	ActiveUsers        int64
	Period             TimePeriod
	StartTime          time.Time
	EndTime            time.Time
}

// ModelStats 模型统计
type ModelStats struct {
	TenantID     string
	ModelName    string
	Provider     string
	RequestCount int64
	TotalTokens  int64
	TotalCost    float64
	AvgLatency   float64
	ErrorRate    float64
	Period       TimePeriod
	StartTime    time.Time
	EndTime      time.Time
}

// UserBehavior 用户行为统计
type UserBehavior struct {
	TenantID           string
	UserID             string
	ConversationCount  int64
	MessageCount       int64
	AvgSessionDuration float64
	LastActiveTime     time.Time
	Period             TimePeriod
	StartTime          time.Time
	EndTime            time.Time
}

// TimePeriod 时间周期
type TimePeriod string

const (
	PeriodMinute TimePeriod = "minute"
	PeriodHour   TimePeriod = "hour"
	PeriodDay    TimePeriod = "day"
	PeriodWeek   TimePeriod = "week"
	PeriodMonth  TimePeriod = "month"
)

// RealtimeStats 实时统计
type RealtimeStats struct {
	TenantID           string
	CurrentQPS         float64
	CurrentActiveUsers int64
	CurrentLatency     float64
	Timestamp          time.Time
}

// CostBreakdown 成本分解
type CostBreakdown struct {
	TenantID      string
	ModelCost     float64
	EmbeddingCost float64
	RerankCost    float64
	TotalCost     float64
	Period        TimePeriod
	StartTime     time.Time
	EndTime       time.Time
}
