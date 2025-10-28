package application

import (
	"context"
	"fmt"
	"time"
	"voicehelper/cmd/model-router/internal/data"
	"voicehelper/cmd/model-router/internal/infrastructure"

	"github.com/go-kratos/kratos/v2/log"
)

// CostAnalysisService 成本分析服务
type CostAnalysisService struct {
	logRepo *data.ClickHouseLogRepository
	log     *log.Helper
}

// NewCostAnalysisService 创建成本分析服务
func NewCostAnalysisService(logRepo *data.ClickHouseLogRepository, logger log.Logger) *CostAnalysisService {
	return &CostAnalysisService{
		logRepo: logRepo,
		log:     log.NewHelper(logger),
	}
}

// CostReport 成本报表
type CostReport struct {
	TenantID          string                              `json:"tenant_id"`
	TimeRange         TimeRange                           `json:"time_range"`
	TotalCost         float64                             `json:"total_cost"`
	TotalRequests     uint64                              `json:"total_requests"`
	AvgCostPerRequest float64                             `json:"avg_cost_per_request"`
	ModelBreakdown    []*infrastructure.ModelCostAnalysis `json:"model_breakdown"`
	DailyTrend        []*infrastructure.DailyStats        `json:"daily_trend"`
	HourlyTrend       []*infrastructure.HourlyTrend       `json:"hourly_trend"`
	TopModels         []*infrastructure.ModelCostAnalysis `json:"top_models"`
}

// TimeRange 时间范围
type TimeRange struct {
	StartTime time.Time `json:"start_time"`
	EndTime   time.Time `json:"end_time"`
	Duration  string    `json:"duration"`
}

// GenerateCostReport 生成成本报表
func (s *CostAnalysisService) GenerateCostReport(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
) (*CostReport, error) {
	s.log.Infof("generating cost report for tenant %s from %s to %s", tenantID, startTime, endTime)

	// 1. 获取模型成本分析
	modelCosts, err := s.logRepo.GetModelCostAnalysis(ctx, tenantID, startTime, endTime, 100)
	if err != nil {
		s.log.Errorf("failed to get model cost analysis: %v", err)
		return nil, err
	}

	// 2. 获取日统计
	dailyStats, err := s.logRepo.GetDailyStats(ctx, tenantID, startTime, endTime)
	if err != nil {
		s.log.Errorf("failed to get daily stats: %v", err)
		return nil, err
	}

	// 3. 获取小时趋势
	hourlyTrend, err := s.logRepo.GetHourlyTrend(ctx, tenantID, startTime, endTime)
	if err != nil {
		s.log.Errorf("failed to get hourly trend: %v", err)
		return nil, err
	}

	// 4. 计算总成本和总请求数
	var totalCost float64
	var totalRequests uint64

	for _, mc := range modelCosts {
		totalCost += mc.TotalCostUSD
		totalRequests += mc.TotalRequests
	}

	// 5. Top 10模型
	topModels := modelCosts
	if len(topModels) > 10 {
		topModels = topModels[:10]
	}

	report := &CostReport{
		TenantID: tenantID,
		TimeRange: TimeRange{
			StartTime: startTime,
			EndTime:   endTime,
			Duration:  endTime.Sub(startTime).String(),
		},
		TotalCost:     totalCost,
		TotalRequests: totalRequests,
		AvgCostPerRequest: func() float64 {
			if totalRequests > 0 {
				return totalCost / float64(totalRequests)
			}
			return 0
		}(),
		ModelBreakdown: modelCosts,
		DailyTrend:     dailyStats,
		HourlyTrend:    hourlyTrend,
		TopModels:      topModels,
	}

	s.log.Infof("cost report generated: total_cost=$%.4f, total_requests=%d", totalCost, totalRequests)

	return report, nil
}

// CostAlert 成本告警
type CostAlert struct {
	AlertID      string    `json:"alert_id"`
	TenantID     string    `json:"tenant_id"`
	AlertType    string    `json:"alert_type"` // daily_limit, hourly_spike, model_cost
	Threshold    float64   `json:"threshold"`
	CurrentValue float64   `json:"current_value"`
	Triggered    bool      `json:"triggered"`
	Message      string    `json:"message"`
	Timestamp    time.Time `json:"timestamp"`
}

// CheckCostAlerts 检查成本告警
func (s *CostAnalysisService) CheckCostAlerts(
	ctx context.Context,
	tenantID string,
	dailyLimit float64,
	hourlyLimit float64,
) ([]*CostAlert, error) {
	alerts := make([]*CostAlert, 0)

	now := time.Now()

	// 1. 检查今日成本
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	todayEnd := now

	dailyStats, err := s.logRepo.GetDailyStats(ctx, tenantID, todayStart, todayEnd)
	if err != nil {
		s.log.Errorf("failed to get today stats: %v", err)
	} else {
		var todayCost float64
		for _, stat := range dailyStats {
			todayCost += stat.TotalCostUSD
		}

		alert := &CostAlert{
			AlertID:      fmt.Sprintf("daily_%s_%s", tenantID, todayStart.Format("20060102")),
			TenantID:     tenantID,
			AlertType:    "daily_limit",
			Threshold:    dailyLimit,
			CurrentValue: todayCost,
			Triggered:    todayCost >= dailyLimit,
			Timestamp:    now,
		}

		if alert.Triggered {
			alert.Message = fmt.Sprintf(
				"Daily cost limit exceeded: $%.2f / $%.2f (%.1f%%)",
				todayCost, dailyLimit, (todayCost/dailyLimit)*100,
			)
			s.log.Warnf("cost alert triggered: %s", alert.Message)
		}

		alerts = append(alerts, alert)
	}

	// 2. 检查过去1小时成本
	hourStart := now.Add(-1 * time.Hour)

	hourlyTrend, err := s.logRepo.GetHourlyTrend(ctx, tenantID, hourStart, now)
	if err != nil {
		s.log.Errorf("failed to get hourly trend: %v", err)
	} else {
		var hourCost float64
		for _, trend := range hourlyTrend {
			hourCost += trend.TotalCost
		}

		alert := &CostAlert{
			AlertID:      fmt.Sprintf("hourly_%s_%s", tenantID, hourStart.Format("2006010215")),
			TenantID:     tenantID,
			AlertType:    "hourly_spike",
			Threshold:    hourlyLimit,
			CurrentValue: hourCost,
			Triggered:    hourCost >= hourlyLimit,
			Timestamp:    now,
		}

		if alert.Triggered {
			alert.Message = fmt.Sprintf(
				"Hourly cost spike detected: $%.2f / $%.2f (%.1f%%)",
				hourCost, hourlyLimit, (hourCost/hourlyLimit)*100,
			)
			s.log.Warnf("cost alert triggered: %s", alert.Message)
		}

		alerts = append(alerts, alert)
	}

	// 3. 检查单个模型成本
	modelCosts, err := s.logRepo.GetModelCostAnalysis(ctx, tenantID, todayStart, now, 10)
	if err != nil {
		s.log.Errorf("failed to get model costs: %v", err)
	} else {
		for _, mc := range modelCosts {
			// 如果单个模型成本超过每日限额的20%
			threshold := dailyLimit * 0.2
			if mc.TotalCostUSD >= threshold {
				alert := &CostAlert{
					AlertID:      fmt.Sprintf("model_%s_%s_%s", tenantID, mc.ModelID, todayStart.Format("20060102")),
					TenantID:     tenantID,
					AlertType:    "model_cost",
					Threshold:    threshold,
					CurrentValue: mc.TotalCostUSD,
					Triggered:    true,
					Message: fmt.Sprintf(
						"High cost model detected: %s cost $%.2f (20%% of daily limit)",
						mc.ModelName, mc.TotalCostUSD,
					),
					Timestamp: now,
				}
				alerts = append(alerts, alert)
			}
		}
	}

	return alerts, nil
}

// UsageReport 使用报表
type UsageReport struct {
	TenantID        string             `json:"tenant_id"`
	TimeRange       TimeRange          `json:"time_range"`
	TotalRequests   uint64             `json:"total_requests"`
	SuccessRate     float64            `json:"success_rate"`
	AvgLatencyMs    float64            `json:"avg_latency_ms"`
	P95LatencyMs    float64            `json:"p95_latency_ms"`
	TotalTokens     uint64             `json:"total_tokens"`
	ModelUsage      []*ModelUsageStats `json:"model_usage"`
	RequestTypeDist map[string]uint64  `json:"request_type_distribution"`
}

// ModelUsageStats 模型使用统计
type ModelUsageStats struct {
	ModelID      string  `json:"model_id"`
	ModelName    string  `json:"model_name"`
	RequestCount uint64  `json:"request_count"`
	SuccessRate  float64 `json:"success_rate"`
	AvgLatencyMs float64 `json:"avg_latency_ms"`
	TotalTokens  uint64  `json:"total_tokens"`
	TotalCost    float64 `json:"total_cost"`
}

// GenerateUsageReport 生成使用报表
func (s *CostAnalysisService) GenerateUsageReport(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
) (*UsageReport, error) {
	s.log.Infof("generating usage report for tenant %s", tenantID)

	// 获取模型成本分析（包含使用统计）
	modelCosts, err := s.logRepo.GetModelCostAnalysis(ctx, tenantID, startTime, endTime, 100)
	if err != nil {
		return nil, err
	}

	// 计算总体统计
	var totalRequests uint64
	var totalSuccess uint64
	var totalTokens uint64
	var totalLatency float64
	var maxP95Latency float64

	modelUsage := make([]*ModelUsageStats, 0, len(modelCosts))

	for _, mc := range modelCosts {
		totalRequests += mc.TotalRequests
		successCount := uint64(float64(mc.TotalRequests) * (1 - mc.ErrorRate))
		totalSuccess += successCount
		totalTokens += mc.TotalTokens
		totalLatency += mc.AvgCostPerRequest * float64(mc.TotalRequests)

		if maxP95Latency < 0 { // 简化：使用avg作为P95估计
			maxP95Latency = mc.AvgCostPerRequest
		}

		modelUsage = append(modelUsage, &ModelUsageStats{
			ModelID:      mc.ModelID,
			ModelName:    mc.ModelName,
			RequestCount: mc.TotalRequests,
			SuccessRate:  1 - mc.ErrorRate,
			AvgLatencyMs: mc.AvgCostPerRequest,
			TotalTokens:  mc.TotalTokens,
			TotalCost:    mc.TotalCostUSD,
		})
	}

	report := &UsageReport{
		TenantID: tenantID,
		TimeRange: TimeRange{
			StartTime: startTime,
			EndTime:   endTime,
			Duration:  endTime.Sub(startTime).String(),
		},
		TotalRequests: totalRequests,
		SuccessRate: func() float64 {
			if totalRequests > 0 {
				return float64(totalSuccess) / float64(totalRequests)
			}
			return 0
		}(),
		AvgLatencyMs: func() float64 {
			if totalRequests > 0 {
				return totalLatency / float64(totalRequests)
			}
			return 0
		}(),
		P95LatencyMs:    maxP95Latency,
		TotalTokens:     totalTokens,
		ModelUsage:      modelUsage,
		RequestTypeDist: make(map[string]uint64), // 简化：后续可从日志聚合
	}

	return report, nil
}

// ExportCostReport 导出成本报表（CSV格式）
func (s *CostAnalysisService) ExportCostReport(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
) (string, error) {
	report, err := s.GenerateCostReport(ctx, tenantID, startTime, endTime)
	if err != nil {
		return "", err
	}

	// 生成CSV内容
	csv := "Model ID,Model Name,Total Requests,Total Cost (USD),Avg Cost/Request,Total Tokens,Error Rate\n"
	for _, mc := range report.ModelBreakdown {
		csv += fmt.Sprintf("%s,%s,%d,%.4f,%.6f,%d,%.4f\n",
			mc.ModelID, mc.ModelName, mc.TotalRequests, mc.TotalCostUSD,
			mc.AvgCostPerRequest, mc.TotalTokens, mc.ErrorRate,
		)
	}

	s.log.Infof("exported cost report for tenant %s", tenantID)

	return csv, nil
}
