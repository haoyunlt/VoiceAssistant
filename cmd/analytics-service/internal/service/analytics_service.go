package service

import (
	"context"
	"time"

	"voiceassistant/cmd/analytics-service/internal/biz"
	"voiceassistant/cmd/analytics-service/internal/domain"
)

// AnalyticsService 分析服务实现
type AnalyticsService struct {
	metricUc    *biz.MetricUsecase
	reportUc    *biz.ReportUsecase
	dashboardUc *biz.RealtimeDashboardUsecase
}

// NewAnalyticsService 创建分析服务
func NewAnalyticsService(
	metricUc *biz.MetricUsecase,
	reportUc *biz.ReportUsecase,
	dashboardUc *biz.RealtimeDashboardUsecase,
) *AnalyticsService {
	return &AnalyticsService{
		metricUc:    metricUc,
		reportUc:    reportUc,
		dashboardUc: dashboardUc,
	}
}

// GetUsageStats 获取使用统计
func (s *AnalyticsService) GetUsageStats(ctx context.Context, tenantID string, period string, start, end time.Time) (*domain.UsageStats, error) {
	return s.metricUc.GetUsageStats(ctx, tenantID, domain.TimePeriod(period), start, end)
}

// GetModelStats 获取模型统计
func (s *AnalyticsService) GetModelStats(ctx context.Context, tenantID string, period string, start, end time.Time) ([]*domain.ModelStats, error) {
	return s.metricUc.GetModelStats(ctx, tenantID, domain.TimePeriod(period), start, end)
}

// GetUserBehavior 获取用户行为统计
func (s *AnalyticsService) GetUserBehavior(ctx context.Context, tenantID, userID string, period string, start, end time.Time) (*domain.UserBehavior, error) {
	return s.metricUc.GetUserBehavior(ctx, tenantID, userID, domain.TimePeriod(period), start, end)
}

// GetRealtimeStats 获取实时统计
func (s *AnalyticsService) GetRealtimeStats(ctx context.Context, tenantID string) (*domain.RealtimeStats, error) {
	return s.metricUc.GetRealtimeStats(ctx, tenantID)
}

// GetCostBreakdown 获取成本分解
func (s *AnalyticsService) GetCostBreakdown(ctx context.Context, tenantID string, period string, start, end time.Time) (*domain.CostBreakdown, error) {
	return s.metricUc.GetCostBreakdown(ctx, tenantID, domain.TimePeriod(period), start, end)
}

// CreateReport 创建报表
func (s *AnalyticsService) CreateReport(ctx context.Context, tenantID, reportType, name, createdBy string) (*domain.Report, error) {
	return s.reportUc.CreateReport(ctx, tenantID, reportType, name, createdBy)
}

// GetReport 获取报表
func (s *AnalyticsService) GetReport(ctx context.Context, id string) (*domain.Report, error) {
	return s.reportUc.GetReport(ctx, id)
}

// ListReports 列出报表
func (s *AnalyticsService) ListReports(ctx context.Context, tenantID string, limit, offset int) ([]*domain.Report, int, error) {
	return s.reportUc.ListReports(ctx, tenantID, limit, offset)
}

// DeleteReport 删除报表
func (s *AnalyticsService) DeleteReport(ctx context.Context, id string) error {
	return s.reportUc.DeleteReport(ctx, id)
}

// GetDashboardMetrics 获取实时看板指标
func (s *AnalyticsService) GetDashboardMetrics(ctx context.Context, tenantID string) (*biz.DashboardMetrics, error) {
	return s.dashboardUc.GetDashboardMetrics(ctx, tenantID)
}
