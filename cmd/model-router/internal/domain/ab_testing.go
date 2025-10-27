package domain

import (
	"context"
	"time"
)

// ABTestRepository A/B测试仓储接口
type ABTestRepository interface {
	// 测试配置
	CreateTest(ctx context.Context, test *ABTestConfig) error
	GetTest(ctx context.Context, testID string) (*ABTestConfig, error)
	UpdateTest(ctx context.Context, test *ABTestConfig) error
	ListTests(ctx context.Context, filters *TestFilters) ([]*ABTestConfig, error)
	DeleteTest(ctx context.Context, testID string) error

	// 测试结果（时序存储）
	RecordMetric(ctx context.Context, metric *ABTestMetric) error
	GetMetrics(ctx context.Context, testID, variantID string, timeRange TimeRange) ([]*ABTestMetric, error)
	AggregateResults(ctx context.Context, testID string) (map[string]*ABTestResult, error)
}

// TestStatus 测试状态
type TestStatus string

const (
	TestStatusDraft     TestStatus = "draft"
	TestStatusRunning   TestStatus = "running"
	TestStatusPaused    TestStatus = "paused"
	TestStatusCompleted TestStatus = "completed"
)

// ABTestConfig A/B测试配置（持久化）
type ABTestConfig struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	StartTime   time.Time              `json:"start_time"`
	EndTime     time.Time              `json:"end_time"`
	Status      TestStatus             `json:"status"`
	Strategy    string                 `json:"strategy"` // consistent_hash, weighted_random
	Variants    []*ABVariant           `json:"variants"`
	Metadata    map[string]interface{} `json:"metadata"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
	CreatedBy   string                 `json:"created_by"`
}

// ABVariant A/B测试变体
type ABVariant struct {
	ID          string  `json:"id"`
	Name        string  `json:"name"`
	ModelID     string  `json:"model_id"`
	Weight      float64 `json:"weight"` // 流量权重 (0-1)
	Description string  `json:"description"`
}

// ABTestMetric A/B测试指标（单次记录）
type ABTestMetric struct {
	ID          string                 `json:"id"`
	TestID      string                 `json:"test_id"`
	VariantID   string                 `json:"variant_id"`
	UserID      string                 `json:"user_id"`
	Timestamp   time.Time              `json:"timestamp"`
	Success     bool                   `json:"success"`
	LatencyMs   float64                `json:"latency_ms"`
	TokensUsed  int64                  `json:"tokens_used"`
	CostUSD     float64                `json:"cost_usd"`
	ModelID     string                 `json:"model_id"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// ABTestResult A/B测试结果（聚合）
type ABTestResult struct {
	VariantID    string    `json:"variant_id"`
	RequestCount int64     `json:"request_count"`
	SuccessCount int64     `json:"success_count"`
	FailureCount int64     `json:"failure_count"`
	AvgLatencyMs float64   `json:"avg_latency_ms"`
	TotalTokens  int64     `json:"total_tokens"`
	TotalCost    float64   `json:"total_cost"`
	LastUpdated  time.Time `json:"last_updated"`
}

// TestFilters 测试过滤条件
type TestFilters struct {
	Status    TestStatus
	CreatedBy string
	StartDate time.Time
	EndDate   time.Time
	Limit     int
	Offset    int
}

// TimeRange 时间范围
type TimeRange struct {
	Start time.Time
	End   time.Time
}

// IsActive 检查测试是否在有效期内
func (c *ABTestConfig) IsActive() bool {
	now := time.Now()
	return c.Status == TestStatusRunning &&
		now.After(c.StartTime) &&
		now.Before(c.EndTime)
}

// ValidateVariants 验证变体配置
func (c *ABTestConfig) ValidateVariants() error {
	if len(c.Variants) == 0 {
		return ErrInvalidVariants
	}

	totalWeight := 0.0
	for _, v := range c.Variants {
		if v.Weight < 0 || v.Weight > 1 {
			return ErrInvalidWeight
		}
		totalWeight += v.Weight
	}

	if totalWeight < 0.99 || totalWeight > 1.01 {
		return ErrInvalidTotalWeight
	}

	return nil
}

// FindVariant 查找变体
func (c *ABTestConfig) FindVariant(variantID string) *ABVariant {
	for _, v := range c.Variants {
		if v.ID == variantID {
			return v
		}
	}
	return nil
}


