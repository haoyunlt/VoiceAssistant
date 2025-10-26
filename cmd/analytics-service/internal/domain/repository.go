package domain

import (
	"context"
	"time"
)

// MetricRepository 指标仓储接口
type MetricRepository interface {
	// RecordMetric 记录指标
	RecordMetric(ctx context.Context, metric *Metric) error

	// GetUsageStats 获取使用统计
	GetUsageStats(ctx context.Context, tenantID string, period TimePeriod, start, end time.Time) (*UsageStats, error)

	// GetModelStats 获取模型统计
	GetModelStats(ctx context.Context, tenantID string, period TimePeriod, start, end time.Time) ([]*ModelStats, error)

	// GetUserBehavior 获取用户行为统计
	GetUserBehavior(ctx context.Context, tenantID, userID string, period TimePeriod, start, end time.Time) (*UserBehavior, error)

	// GetRealtimeStats 获取实时统计
	GetRealtimeStats(ctx context.Context, tenantID string) (*RealtimeStats, error)

	// GetCostBreakdown 获取成本分解
	GetCostBreakdown(ctx context.Context, tenantID string, period TimePeriod, start, end time.Time) (*CostBreakdown, error)
}

// ReportRepository 报表仓储接口
type ReportRepository interface {
	// CreateReport 创建报表
	CreateReport(ctx context.Context, report *Report) error

	// GetReport 获取报表
	GetReport(ctx context.Context, id string) (*Report, error)

	// UpdateReport 更新报表
	UpdateReport(ctx context.Context, report *Report) error

	// ListReports 列出报表
	ListReports(ctx context.Context, tenantID string, limit, offset int) ([]*Report, int, error)

	// DeleteReport 删除报表
	DeleteReport(ctx context.Context, id string) error
}
