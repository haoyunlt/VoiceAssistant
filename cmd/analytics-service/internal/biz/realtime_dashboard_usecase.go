package biz

import (
	"context"
	"fmt"
	"time"
)

// DashboardMetrics 实时看板指标
type DashboardMetrics struct {
	// 实时指标
	CurrentActiveUsers    int64   `json:"current_active_users"`
	CurrentRequestsPerSec float64 `json:"current_requests_per_sec"`
	AverageResponseTime   float64 `json:"average_response_time_ms"`
	ErrorRate             float64 `json:"error_rate"`

	// 今日统计
	TodayTotalRequests int64   `json:"today_total_requests"`
	TodayTotalTokens   int64   `json:"today_total_tokens"`
	TodayTotalCost     float64 `json:"today_total_cost"`
	TodayUniqueUsers   int64   `json:"today_unique_users"`

	// 模型使用
	TopModels []ModelUsage `json:"top_models"`

	// 趋势数据（最近24小时）
	RequestsTrend []TimeSeriesPoint `json:"requests_trend"`
	TokensTrend   []TimeSeriesPoint `json:"tokens_trend"`
	CostTrend     []TimeSeriesPoint `json:"cost_trend"`

	// 性能指标
	P50ResponseTime float64 `json:"p50_response_time_ms"`
	P95ResponseTime float64 `json:"p95_response_time_ms"`
	P99ResponseTime float64 `json:"p99_response_time_ms"`

	// 系统健康
	HealthStatus string `json:"health_status"`
	AlertCount   int    `json:"alert_count"`

	UpdatedAt time.Time `json:"updated_at"`
}

// ModelUsage 模型使用情况
type ModelUsage struct {
	ModelName    string  `json:"model_name"`
	RequestCount int64   `json:"request_count"`
	TokenCount   int64   `json:"token_count"`
	Cost         float64 `json:"cost"`
	Percentage   float64 `json:"percentage"`
}

// TimeSeriesPoint 时间序列数据点
type TimeSeriesPoint struct {
	Timestamp time.Time `json:"timestamp"`
	Value     float64   `json:"value"`
}

// RealtimeDashboardUsecase 实时看板用例
type RealtimeDashboardUsecase struct {
	clickhouseClient ClickHouseClient
	cacheClient      CacheClient
}

// NewRealtimeDashboardUsecase 创建实时看板用例
func NewRealtimeDashboardUsecase(
	clickhouseClient ClickHouseClient,
	cacheClient CacheClient,
) *RealtimeDashboardUsecase {
	return &RealtimeDashboardUsecase{
		clickhouseClient: clickhouseClient,
		cacheClient:      cacheClient,
	}
}

// GetDashboardMetrics 获取实时看板指标
func (uc *RealtimeDashboardUsecase) GetDashboardMetrics(
	ctx context.Context,
	tenantID string,
) (*DashboardMetrics, error) {
	// 1. 尝试从缓存获取
	cacheKey := fmt.Sprintf("dashboard:metrics:%s", tenantID)
	cachedMetrics, err := uc.cacheClient.Get(ctx, cacheKey)
	if err == nil && cachedMetrics != nil {
		metrics := &DashboardMetrics{}
		// 假设缓存存储为JSON
		return metrics, nil
	}

	// 2. 计算实时指标
	now := time.Now()
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	// 并发获取各项指标
	type result struct {
		key   string
		value interface{}
		err   error
	}

	resultChan := make(chan result, 10)

	// 获取当前活跃用户
	go func() {
		count, err := uc.getCurrentActiveUsers(ctx, tenantID)
		resultChan <- result{key: "active_users", value: count, err: err}
	}()

	// 获取今日总请求数
	go func() {
		count, err := uc.getTodayTotalRequests(ctx, tenantID, today)
		resultChan <- result{key: "today_requests", value: count, err: err}
	}()

	// 获取今日总Token数
	go func() {
		count, err := uc.getTodayTotalTokens(ctx, tenantID, today)
		resultChan <- result{key: "today_tokens", value: count, err: err}
	}()

	// 获取今日总成本
	go func() {
		cost, err := uc.getTodayTotalCost(ctx, tenantID, today)
		resultChan <- result{key: "today_cost", value: cost, err: err}
	}()

	// 获取今日独立用户数
	go func() {
		count, err := uc.getTodayUniqueUsers(ctx, tenantID, today)
		resultChan <- result{key: "today_users", value: count, err: err}
	}()

	// 获取Top模型
	go func() {
		models, err := uc.getTopModels(ctx, tenantID, today, 5)
		resultChan <- result{key: "top_models", value: models, err: err}
	}()

	// 获取请求趋势
	go func() {
		trend, err := uc.getRequestsTrend(ctx, tenantID, 24)
		resultChan <- result{key: "requests_trend", value: trend, err: err}
	}()

	// 获取平均响应时间
	go func() {
		avgTime, err := uc.getAverageResponseTime(ctx, tenantID, 5*time.Minute)
		resultChan <- result{key: "avg_response_time", value: avgTime, err: err}
	}()

	// 获取错误率
	go func() {
		rate, err := uc.getErrorRate(ctx, tenantID, 5*time.Minute)
		resultChan <- result{key: "error_rate", value: rate, err: err}
	}()

	// 收集结果
	metrics := &DashboardMetrics{
		UpdatedAt: now,
	}

	for i := 0; i < 9; i++ {
		res := <-resultChan
		if res.err != nil {
			continue
		}

		switch res.key {
		case "active_users":
			metrics.CurrentActiveUsers = res.value.(int64)
		case "today_requests":
			metrics.TodayTotalRequests = res.value.(int64)
		case "today_tokens":
			metrics.TodayTotalTokens = res.value.(int64)
		case "today_cost":
			metrics.TodayTotalCost = res.value.(float64)
		case "today_users":
			metrics.TodayUniqueUsers = res.value.(int64)
		case "top_models":
			metrics.TopModels = res.value.([]ModelUsage)
		case "requests_trend":
			metrics.RequestsTrend = res.value.([]TimeSeriesPoint)
		case "avg_response_time":
			metrics.AverageResponseTime = res.value.(float64)
		case "error_rate":
			metrics.ErrorRate = res.value.(float64)
		}
	}

	// 3. 缓存结果（30秒）
	uc.cacheClient.Set(ctx, cacheKey, metrics, 30*time.Second)

	return metrics, nil
}

// getCurrentActiveUsers 获取当前活跃用户数
func (uc *RealtimeDashboardUsecase) getCurrentActiveUsers(
	ctx context.Context,
	tenantID string,
) (int64, error) {
	query := `
		SELECT uniqExact(user_id) as count
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= now() - INTERVAL 5 MINUTE
	`

	var count int64
	err := uc.clickhouseClient.QueryRow(ctx, query, tenantID).Scan(&count)
	return count, err
}

// getTodayTotalRequests 获取今日总请求数
func (uc *RealtimeDashboardUsecase) getTodayTotalRequests(
	ctx context.Context,
	tenantID string,
	today time.Time,
) (int64, error) {
	query := `
		SELECT count() as count
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= ?
	`

	var count int64
	err := uc.clickhouseClient.QueryRow(ctx, query, tenantID, today).Scan(&count)
	return count, err
}

// getTodayTotalTokens 获取今日总Token数
func (uc *RealtimeDashboardUsecase) getTodayTotalTokens(
	ctx context.Context,
	tenantID string,
	today time.Time,
) (int64, error) {
	query := `
		SELECT sum(total_tokens) as total
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= ?
	`

	var total int64
	err := uc.clickhouseClient.QueryRow(ctx, query, tenantID, today).Scan(&total)
	return total, err
}

// getTodayTotalCost 获取今日总成本
func (uc *RealtimeDashboardUsecase) getTodayTotalCost(
	ctx context.Context,
	tenantID string,
	today time.Time,
) (float64, error) {
	query := `
		SELECT sum(cost) as total
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= ?
	`

	var total float64
	err := uc.clickhouseClient.QueryRow(ctx, query, tenantID, today).Scan(&total)
	return total, err
}

// getTodayUniqueUsers 获取今日独立用户数
func (uc *RealtimeDashboardUsecase) getTodayUniqueUsers(
	ctx context.Context,
	tenantID string,
	today time.Time,
) (int64, error) {
	query := `
		SELECT uniqExact(user_id) as count
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= ?
	`

	var count int64
	err := uc.clickhouseClient.QueryRow(ctx, query, tenantID, today).Scan(&count)
	return count, err
}

// getTopModels 获取Top模型使用情况
func (uc *RealtimeDashboardUsecase) getTopModels(
	ctx context.Context,
	tenantID string,
	since time.Time,
	limit int,
) ([]ModelUsage, error) {
	query := `
		SELECT
			model_name,
			count() as request_count,
			sum(total_tokens) as token_count,
			sum(cost) as total_cost
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= ?
		GROUP BY model_name
		ORDER BY request_count DESC
		LIMIT ?
	`

	rows, err := uc.clickhouseClient.Query(ctx, query, tenantID, since, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var models []ModelUsage
	var totalRequests int64

	for rows.Next() {
		var model ModelUsage
		if err := rows.Scan(
			&model.ModelName,
			&model.RequestCount,
			&model.TokenCount,
			&model.Cost,
		); err != nil {
			return nil, err
		}
		models = append(models, model)
		totalRequests += model.RequestCount
	}

	// 计算百分比
	for i := range models {
		if totalRequests > 0 {
			models[i].Percentage = float64(models[i].RequestCount) / float64(totalRequests) * 100
		}
	}

	return models, nil
}

// getRequestsTrend 获取请求趋势
func (uc *RealtimeDashboardUsecase) getRequestsTrend(
	ctx context.Context,
	tenantID string,
	hours int,
) ([]TimeSeriesPoint, error) {
	query := `
		SELECT
			toStartOfHour(timestamp) as hour,
			count() as count
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= now() - INTERVAL ? HOUR
		GROUP BY hour
		ORDER BY hour
	`

	rows, err := uc.clickhouseClient.Query(ctx, query, tenantID, hours)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var points []TimeSeriesPoint
	for rows.Next() {
		var point TimeSeriesPoint
		var count int64
		if err := rows.Scan(&point.Timestamp, &count); err != nil {
			return nil, err
		}
		point.Value = float64(count)
		points = append(points, point)
	}

	return points, nil
}

// getAverageResponseTime 获取平均响应时间
func (uc *RealtimeDashboardUsecase) getAverageResponseTime(
	ctx context.Context,
	tenantID string,
	duration time.Duration,
) (float64, error) {
	query := `
		SELECT avg(response_time_ms) as avg_time
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= now() - INTERVAL ? SECOND
	`

	var avgTime float64
	err := uc.clickhouseClient.QueryRow(
		ctx, query, tenantID, int(duration.Seconds()),
	).Scan(&avgTime)
	return avgTime, err
}

// getErrorRate 获取错误率
func (uc *RealtimeDashboardUsecase) getErrorRate(
	ctx context.Context,
	tenantID string,
	duration time.Duration,
) (float64, error) {
	query := `
		SELECT
			countIf(status = 'error') * 100.0 / count() as error_rate
		FROM usage_metrics
		WHERE tenant_id = ?
		  AND timestamp >= now() - INTERVAL ? SECOND
	`

	var errorRate float64
	err := uc.clickhouseClient.QueryRow(
		ctx, query, tenantID, int(duration.Seconds()),
	).Scan(&errorRate)
	return errorRate, err
}
