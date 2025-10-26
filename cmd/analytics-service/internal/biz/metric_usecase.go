package biz

import (
	"context"
	"time"

	"analytics-service/internal/domain"
)

// MetricUsecase 指标用例
type MetricUsecase struct {
	metricRepo domain.MetricRepository
}

// NewMetricUsecase 创建指标用例
func NewMetricUsecase(metricRepo domain.MetricRepository) *MetricUsecase {
	return &MetricUsecase{
		metricRepo: metricRepo,
	}
}

// RecordMetric 记录指标
func (uc *MetricUsecase) RecordMetric(ctx context.Context, metric *domain.Metric) error {
	return uc.metricRepo.RecordMetric(ctx, metric)
}

// GetUsageStats 获取使用统计
func (uc *MetricUsecase) GetUsageStats(ctx context.Context, tenantID string, period domain.TimePeriod, start, end time.Time) (*domain.UsageStats, error) {
	// 验证时间周期
	if err := uc.validateTimePeriod(period); err != nil {
		return nil, err
	}

	// 获取统计数据
	stats, err := uc.metricRepo.GetUsageStats(ctx, tenantID, period, start, end)
	if err != nil {
		return nil, err
	}

	return stats, nil
}

// GetModelStats 获取模型统计
func (uc *MetricUsecase) GetModelStats(ctx context.Context, tenantID string, period domain.TimePeriod, start, end time.Time) ([]*domain.ModelStats, error) {
	// 验证时间周期
	if err := uc.validateTimePeriod(period); err != nil {
		return nil, err
	}

	// 获取统计数据
	stats, err := uc.metricRepo.GetModelStats(ctx, tenantID, period, start, end)
	if err != nil {
		return nil, err
	}

	return stats, nil
}

// GetUserBehavior 获取用户行为统计
func (uc *MetricUsecase) GetUserBehavior(ctx context.Context, tenantID, userID string, period domain.TimePeriod, start, end time.Time) (*domain.UserBehavior, error) {
	// 验证时间周期
	if err := uc.validateTimePeriod(period); err != nil {
		return nil, err
	}

	// 获取统计数据
	behavior, err := uc.metricRepo.GetUserBehavior(ctx, tenantID, userID, period, start, end)
	if err != nil {
		return nil, err
	}

	return behavior, nil
}

// GetRealtimeStats 获取实时统计
func (uc *MetricUsecase) GetRealtimeStats(ctx context.Context, tenantID string) (*domain.RealtimeStats, error) {
	stats, err := uc.metricRepo.GetRealtimeStats(ctx, tenantID)
	if err != nil {
		return nil, err
	}

	return stats, nil
}

// GetCostBreakdown 获取成本分解
func (uc *MetricUsecase) GetCostBreakdown(ctx context.Context, tenantID string, period domain.TimePeriod, start, end time.Time) (*domain.CostBreakdown, error) {
	// 验证时间周期
	if err := uc.validateTimePeriod(period); err != nil {
		return nil, err
	}

	// 获取成本分解
	breakdown, err := uc.metricRepo.GetCostBreakdown(ctx, tenantID, period, start, end)
	if err != nil {
		return nil, err
	}

	return breakdown, nil
}

// validateTimePeriod 验证时间周期
func (uc *MetricUsecase) validateTimePeriod(period domain.TimePeriod) error {
	switch period {
	case domain.PeriodMinute, domain.PeriodHour, domain.PeriodDay, domain.PeriodWeek, domain.PeriodMonth:
		return nil
	default:
		return domain.ErrInvalidTimePeriod
	}
}
