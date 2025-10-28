package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
)

// ReportType 报表类型
type ReportType string

const (
	ReportTypeUsage  ReportType = "usage"  // 使用报表
	ReportTypeCost   ReportType = "cost"   // 成本报表
	ReportTypeModel  ReportType = "model"  // 模型报表
	ReportTypeUser   ReportType = "user"   // 用户报表
	ReportTypeCustom ReportType = "custom" // 自定义报表
)

// ReportStatus 报表状态
type ReportStatus string

const (
	ReportStatusPending    ReportStatus = "pending"    // 等待生成
	ReportStatusGenerating ReportStatus = "generating" // 生成中
	ReportStatusCompleted  ReportStatus = "completed"  // 已完成
	ReportStatusFailed     ReportStatus = "failed"     // 生成失败
)

// Report 报表
type Report struct {
	ID                  string                 `json:"id"`
	Type                ReportType             `json:"type"`
	Status              ReportStatus           `json:"status"`
	TenantID            string                 `json:"tenant_id,omitempty"`
	StartDate           string                 `json:"start_date"`
	EndDate             string                 `json:"end_date"`
	Parameters          map[string]interface{} `json:"parameters,omitempty"`
	Data                interface{}            `json:"data,omitempty"`
	DownloadURL         string                 `json:"download_url,omitempty"`
	CreatedAt           time.Time              `json:"created_at"`
	CompletedAt         *time.Time             `json:"completed_at,omitempty"`
	EstimatedCompletion *time.Time             `json:"estimated_completion,omitempty"`
	Error               string                 `json:"error,omitempty"`
}

// UsageReport 使用报表数据
type UsageReport struct {
	TotalRequests   int64            `json:"total_requests"`
	TotalTokens     int64            `json:"total_tokens"`
	TotalCost       float64          `json:"total_cost"`
	ByService       map[string]int64 `json:"by_service"`           // RAG, Agent, Voice等
	ByModel         map[string]int64 `json:"by_model"`             // 不同模型的使用次数
	DailyBreakdown  []DailyUsage     `json:"daily_breakdown"`      // 每日分解
	TopUsers        []UserUsage      `json:"top_users"`            // Top用户
	PeakHours       []HourlyUsage    `json:"peak_hours"`           // 高峰时段
	AvgResponseTime float64          `json:"avg_response_time_ms"` // 平均响应时间
	SuccessRate     float64          `json:"success_rate"`         // 成功率
}

// CostReport 成本报表数据
type CostReport struct {
	TotalCost      float64            `json:"total_cost_usd"`
	TotalTokens    int64              `json:"total_tokens"`
	ByModel        []ModelCost        `json:"by_model"`                // 按模型统计
	ByService      []ServiceCost      `json:"by_service"`              // 按服务统计
	ByTenant       []TenantCost       `json:"by_tenant"`               // 按租户统计
	DailyBreakdown []DailyCost        `json:"daily_breakdown"`         // 每日分解
	CostTrend      []CostTrendPoint   `json:"cost_trend"`              // 成本趋势
	TopExpensive   []TopExpensiveItem `json:"top_expensive"`           // Top消费项
	BudgetStatus   *BudgetStatus      `json:"budget_status,omitempty"` // 预算状态
	Forecast       *CostForecast      `json:"forecast,omitempty"`      // 成本预测
}

// ModelReport 模型报表数据
type ModelReport struct {
	TotalModels     int              `json:"total_models"`
	ActiveModels    int              `json:"active_models"`
	ByModel         []ModelStats     `json:"by_model"`                  // 按模型统计
	Performance     []ModelPerf      `json:"performance"`               // 性能统计
	Reliability     []ModelReliable  `json:"reliability"`               // 可靠性统计
	CostEfficiency  []CostEfficiency `json:"cost_efficiency"`           // 成本效率
	Recommendations []string         `json:"recommendations,omitempty"` // 优化建议
}

// UserReport 用户报表数据
type UserReport struct {
	TotalUsers     int              `json:"total_users"`
	ActiveUsers    int              `json:"active_users"`
	NewUsers       int              `json:"new_users"`
	ChurnedUsers   int              `json:"churned_users"`
	TopUsers       []UserActivity   `json:"top_users"`       // Top活跃用户
	ByTenant       []TenantActivity `json:"by_tenant"`       // 按租户统计
	Engagement     *EngagementStats `json:"engagement"`      // 用户参与度
	Retention      *RetentionStats  `json:"retention"`       // 用户留存
	DailyBreakdown []DailyUserStats `json:"daily_breakdown"` // 每日分解
}

// 支持数据结构
type DailyUsage struct {
	Date     string  `json:"date"`
	Requests int64   `json:"requests"`
	Tokens   int64   `json:"tokens"`
	Cost     float64 `json:"cost_usd"`
}

type UserUsage struct {
	UserID   string  `json:"user_id"`
	Requests int64   `json:"requests"`
	Tokens   int64   `json:"tokens"`
	Cost     float64 `json:"cost_usd"`
}

type HourlyUsage struct {
	Hour     int     `json:"hour"`
	Requests int64   `json:"requests"`
	AvgLoad  float64 `json:"avg_load"`
}

type ModelCost struct {
	Model      string  `json:"model"`
	Tokens     int64   `json:"tokens"`
	Cost       float64 `json:"cost_usd"`
	Requests   int64   `json:"requests"`
	Percentage float64 `json:"percentage"`
}

type ServiceCost struct {
	Service    string  `json:"service"`
	Cost       float64 `json:"cost_usd"`
	Requests   int64   `json:"requests"`
	Percentage float64 `json:"percentage"`
}

type TenantCost struct {
	TenantID   string  `json:"tenant_id"`
	TenantName string  `json:"tenant_name,omitempty"`
	Cost       float64 `json:"cost_usd"`
	Requests   int64   `json:"requests"`
	Percentage float64 `json:"percentage"`
}

type DailyCost struct {
	Date   string  `json:"date"`
	Cost   float64 `json:"cost_usd"`
	Tokens int64   `json:"tokens"`
}

type CostTrendPoint struct {
	Date   string  `json:"date"`
	Cost   float64 `json:"cost_usd"`
	Change float64 `json:"change_percentage"`
}

type TopExpensiveItem struct {
	Item       string  `json:"item"`
	Type       string  `json:"type"` // model, service, tenant
	Cost       float64 `json:"cost_usd"`
	Percentage float64 `json:"percentage"`
}

type BudgetStatus struct {
	TotalBudget   float64 `json:"total_budget_usd"`
	Used          float64 `json:"used_usd"`
	Remaining     float64 `json:"remaining_usd"`
	UsagePercent  float64 `json:"usage_percentage"`
	DaysRemaining int     `json:"days_remaining"`
	DailyRate     float64 `json:"daily_rate_usd"`
}

type CostForecast struct {
	NextWeek  float64 `json:"next_week_usd"`
	NextMonth float64 `json:"next_month_usd"`
	Trend     string  `json:"trend"` // increasing, decreasing, stable
}

type ModelStats struct {
	Model       string  `json:"model"`
	Requests    int64   `json:"requests"`
	Tokens      int64   `json:"tokens"`
	Cost        float64 `json:"cost_usd"`
	AvgLatency  float64 `json:"avg_latency_ms"`
	SuccessRate float64 `json:"success_rate"`
}

type ModelPerf struct {
	Model      string  `json:"model"`
	AvgLatency float64 `json:"avg_latency_ms"`
	P95Latency float64 `json:"p95_latency_ms"`
	P99Latency float64 `json:"p99_latency_ms"`
	Throughput float64 `json:"throughput_rps"`
}

type ModelReliable struct {
	Model        string  `json:"model"`
	SuccessRate  float64 `json:"success_rate"`
	ErrorRate    float64 `json:"error_rate"`
	Availability float64 `json:"availability"`
	MTBF         float64 `json:"mtbf_hours"` // Mean Time Between Failures
}

type CostEfficiency struct {
	Model            string  `json:"model"`
	CostPerRequest   float64 `json:"cost_per_request_usd"`
	CostPerToken     float64 `json:"cost_per_1k_tokens_usd"`
	QualityScore     float64 `json:"quality_score"`     // 0-1
	EfficiencyRating string  `json:"efficiency_rating"` // excellent, good, fair, poor
}

type UserActivity struct {
	UserID      string  `json:"user_id"`
	Username    string  `json:"username,omitempty"`
	Sessions    int     `json:"sessions"`
	Requests    int64   `json:"requests"`
	AvgDuration float64 `json:"avg_duration_minutes"`
	LastActive  string  `json:"last_active"`
}

type TenantActivity struct {
	TenantID    string `json:"tenant_id"`
	TenantName  string `json:"tenant_name,omitempty"`
	ActiveUsers int    `json:"active_users"`
	Requests    int64  `json:"requests"`
	Sessions    int    `json:"sessions"`
}

type EngagementStats struct {
	DailyActiveUsers   int                `json:"daily_active_users"`
	WeeklyActiveUsers  int                `json:"weekly_active_users"`
	AvgSessionTime     float64            `json:"avg_session_time_minutes"`
	AvgRequestsPerUser float64            `json:"avg_requests_per_user"`
	FeatureAdoption    map[string]float64 `json:"feature_adoption"` // feature -> adoption rate
}

type RetentionStats struct {
	Day1Retention  float64           `json:"day1_retention"`
	Day7Retention  float64           `json:"day7_retention"`
	Day30Retention float64           `json:"day30_retention"`
	CohortAnalysis []CohortRetention `json:"cohort_analysis,omitempty"`
}

type CohortRetention struct {
	Cohort   string  `json:"cohort"`
	Users    int     `json:"users"`
	Day1Ret  float64 `json:"day1_retention"`
	Day7Ret  float64 `json:"day7_retention"`
	Day30Ret float64 `json:"day30_retention"`
}

type DailyUserStats struct {
	Date        string  `json:"date"`
	ActiveUsers int     `json:"active_users"`
	NewUsers    int     `json:"new_users"`
	Sessions    int     `json:"sessions"`
	AvgDuration float64 `json:"avg_duration_minutes"`
}

// ReportGenerator 报表生成器
type ReportGenerator struct {
	clickhouse ClickHouseClient
	cache      CacheManager
}

// NewReportGenerator 创建报表生成器
func NewReportGenerator(ch ClickHouseClient, cache CacheManager) *ReportGenerator {
	return &ReportGenerator{
		clickhouse: ch,
		cache:      cache,
	}
}

// GenerateUsageReport 生成使用报表
func (g *ReportGenerator) GenerateUsageReport(ctx context.Context, tenantID, startDate, endDate string) (*UsageReport, error) {
	// 1. 查询总体统计
	var totalRequests, totalTokens int64
	var totalCost float64

	query := `
		SELECT
			COUNT(*) as requests,
			SUM(total_tokens) as tokens,
			SUM(total_cost) as cost
		FROM ai_requests
		WHERE timestamp >= ? AND timestamp < ?
	`

	args := []interface{}{startDate, endDate}
	if tenantID != "" {
		query += " AND tenant_id = ?"
		args = append(args, tenantID)
	}

	// 这里应该实际调用ClickHouse查询
	// 暂时使用mock数据
	totalRequests = 12000
	totalTokens = 4500000
	totalCost = 125.50

	// 2. 按服务统计
	byService := map[string]int64{
		"rag":        7000,
		"agent":      3000,
		"voice":      1500,
		"multimodal": 500,
	}

	// 3. 按模型统计
	byModel := map[string]int64{
		"gpt-4-turbo-preview": 5000,
		"gpt-3.5-turbo":       7000,
	}

	// 4. 每日分解
	dailyBreakdown := []DailyUsage{
		{Date: "2025-10-26", Requests: 3500, Tokens: 1300000, Cost: 36.50},
		{Date: "2025-10-25", Requests: 3200, Tokens: 1200000, Cost: 34.00},
		{Date: "2025-10-24", Requests: 3000, Tokens: 1100000, Cost: 31.00},
	}

	// 5. Top用户
	topUsers := []UserUsage{
		{UserID: "user_123", Requests: 450, Tokens: 170000, Cost: 4.50},
		{UserID: "user_124", Requests: 380, Tokens: 140000, Cost: 3.80},
	}

	// 6. 高峰时段
	peakHours := []HourlyUsage{
		{Hour: 10, Requests: 800, AvgLoad: 0.85},
		{Hour: 14, Requests: 750, AvgLoad: 0.80},
		{Hour: 15, Requests: 720, AvgLoad: 0.75},
	}

	return &UsageReport{
		TotalRequests:   totalRequests,
		TotalTokens:     totalTokens,
		TotalCost:       totalCost,
		ByService:       byService,
		ByModel:         byModel,
		DailyBreakdown:  dailyBreakdown,
		TopUsers:        topUsers,
		PeakHours:       peakHours,
		AvgResponseTime: 1250.0,
		SuccessRate:     0.95,
	}, nil
}

// GenerateCostReport 生成成本报表
func (g *ReportGenerator) GenerateCostReport(ctx context.Context, tenantID, startDate, endDate string) (*CostReport, error) {
	// 实际应该从ClickHouse查询
	// 这里使用mock数据

	byModel := []ModelCost{
		{Model: "gpt-4-turbo-preview", Tokens: 2000000, Cost: 80.00, Requests: 5000, Percentage: 63.7},
		{Model: "gpt-3.5-turbo", Tokens: 2500000, Cost: 45.50, Requests: 7000, Percentage: 36.3},
	}

	byService := []ServiceCost{
		{Service: "rag", Cost: 70.00, Requests: 7000, Percentage: 55.8},
		{Service: "agent", Cost: 40.00, Requests: 3000, Percentage: 31.9},
		{Service: "voice", Cost: 12.50, Requests: 1500, Percentage: 10.0},
		{Service: "multimodal", Cost: 3.00, Requests: 500, Percentage: 2.4},
	}

	byTenant := []TenantCost{
		{TenantID: "tenant_123", TenantName: "Acme Corp", Cost: 45.00, Requests: 4500, Percentage: 35.9},
		{TenantID: "tenant_124", TenantName: "Tech Inc", Cost: 32.50, Requests: 3200, Percentage: 25.9},
	}

	dailyBreakdown := []DailyCost{
		{Date: "2025-10-26", Cost: 36.50, Tokens: 1300000},
		{Date: "2025-10-25", Cost: 34.00, Tokens: 1200000},
		{Date: "2025-10-24", Cost: 31.00, Tokens: 1100000},
	}

	costTrend := []CostTrendPoint{
		{Date: "2025-10-26", Cost: 36.50, Change: 7.35},
		{Date: "2025-10-25", Cost: 34.00, Change: 9.68},
		{Date: "2025-10-24", Cost: 31.00, Change: -3.13},
	}

	topExpensive := []TopExpensiveItem{
		{Item: "gpt-4-turbo-preview", Type: "model", Cost: 80.00, Percentage: 63.7},
		{Item: "rag", Type: "service", Cost: 70.00, Percentage: 55.8},
		{Item: "tenant_123", Type: "tenant", Cost: 45.00, Percentage: 35.9},
	}

	budgetStatus := &BudgetStatus{
		TotalBudget:   1000.00,
		Used:          125.50,
		Remaining:     874.50,
		UsagePercent:  12.55,
		DaysRemaining: 23,
		DailyRate:     34.17,
	}

	forecast := &CostForecast{
		NextWeek:  239.19,
		NextMonth: 1024.91,
		Trend:     "increasing",
	}

	return &CostReport{
		TotalCost:      125.50,
		TotalTokens:    4500000,
		ByModel:        byModel,
		ByService:      byService,
		ByTenant:       byTenant,
		DailyBreakdown: dailyBreakdown,
		CostTrend:      costTrend,
		TopExpensive:   topExpensive,
		BudgetStatus:   budgetStatus,
		Forecast:       forecast,
	}, nil
}

// GenerateModelReport 生成模型报表
func (g *ReportGenerator) GenerateModelReport(ctx context.Context, tenantID, startDate, endDate string) (*ModelReport, error) {
	byModel := []ModelStats{
		{Model: "gpt-4-turbo-preview", Requests: 5000, Tokens: 2000000, Cost: 80.00, AvgLatency: 2200.0, SuccessRate: 0.96},
		{Model: "gpt-3.5-turbo", Requests: 7000, Tokens: 2500000, Cost: 45.50, AvgLatency: 950.0, SuccessRate: 0.98},
	}

	performance := []ModelPerf{
		{Model: "gpt-4-turbo-preview", AvgLatency: 2200.0, P95Latency: 4500.0, P99Latency: 6800.0, Throughput: 1.2},
		{Model: "gpt-3.5-turbo", AvgLatency: 950.0, P95Latency: 1800.0, P99Latency: 2500.0, Throughput: 2.8},
	}

	reliability := []ModelReliable{
		{Model: "gpt-4-turbo-preview", SuccessRate: 0.96, ErrorRate: 0.04, Availability: 0.998, MTBF: 720.0},
		{Model: "gpt-3.5-turbo", SuccessRate: 0.98, ErrorRate: 0.02, Availability: 0.999, MTBF: 1440.0},
	}

	costEfficiency := []CostEfficiency{
		{Model: "gpt-4-turbo-preview", CostPerRequest: 0.016, CostPerToken: 0.040, QualityScore: 0.92, EfficiencyRating: "good"},
		{Model: "gpt-3.5-turbo", CostPerRequest: 0.0065, CostPerToken: 0.018, QualityScore: 0.85, EfficiencyRating: "excellent"},
	}

	recommendations := []string{
		"Consider using gpt-3.5-turbo for simpler queries to reduce costs",
		"GPT-4 shows better quality but higher latency - optimize for batch processing",
		"Implement caching for frequently asked questions",
	}

	return &ModelReport{
		TotalModels:     2,
		ActiveModels:    2,
		ByModel:         byModel,
		Performance:     performance,
		Reliability:     reliability,
		CostEfficiency:  costEfficiency,
		Recommendations: recommendations,
	}, nil
}

// GenerateUserReport 生成用户报表
func (g *ReportGenerator) GenerateUserReport(ctx context.Context, tenantID, startDate, endDate string) (*UserReport, error) {
	topUsers := []UserActivity{
		{UserID: "user_123", Username: "john@example.com", Sessions: 45, Requests: 450, AvgDuration: 15.2, LastActive: "2025-10-27T10:30:00Z"},
		{UserID: "user_124", Username: "jane@example.com", Sessions: 38, Requests: 380, AvgDuration: 12.5, LastActive: "2025-10-27T09:45:00Z"},
	}

	byTenant := []TenantActivity{
		{TenantID: "tenant_123", TenantName: "Acme Corp", ActiveUsers: 180, Requests: 4500, Sessions: 950},
		{TenantID: "tenant_124", TenantName: "Tech Inc", ActiveUsers: 120, Requests: 3200, Sessions: 680},
	}

	engagement := &EngagementStats{
		DailyActiveUsers:   125,
		WeeklyActiveUsers:  340,
		AvgSessionTime:     15.2,
		AvgRequestsPerUser: 9.6,
		FeatureAdoption: map[string]float64{
			"chat":            0.95,
			"document_upload": 0.60,
			"voice":           0.30,
			"agent":           0.25,
		},
	}

	retention := &RetentionStats{
		Day1Retention:  0.85,
		Day7Retention:  0.65,
		Day30Retention: 0.45,
		CohortAnalysis: []CohortRetention{
			{Cohort: "2025-10", Users: 150, Day1Ret: 0.85, Day7Ret: 0.65, Day30Ret: 0.45},
			{Cohort: "2025-09", Users: 200, Day1Ret: 0.82, Day7Ret: 0.62, Day30Ret: 0.42},
		},
	}

	dailyBreakdown := []DailyUserStats{
		{Date: "2025-10-26", ActiveUsers: 125, NewUsers: 5, Sessions: 340, AvgDuration: 15.2},
		{Date: "2025-10-25", ActiveUsers: 118, NewUsers: 3, Sessions: 320, AvgDuration: 14.8},
	}

	return &UserReport{
		TotalUsers:     1250,
		ActiveUsers:    125,
		NewUsers:       5,
		ChurnedUsers:   8,
		TopUsers:       topUsers,
		ByTenant:       byTenant,
		Engagement:     engagement,
		Retention:      retention,
		DailyBreakdown: dailyBreakdown,
	}, nil
}

// ExportToJSON 导出报表为JSON
func (r *Report) ExportToJSON() (string, error) {
	data, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return "", fmt.Errorf("failed to export report: %w", err)
	}
	return string(data), nil
}

// CacheManager 缓存管理器接口（需要实际实现）
type CacheManager interface {
	Get(key string) (interface{}, error)
	Set(key string, value interface{}, ttl time.Duration) error
}
