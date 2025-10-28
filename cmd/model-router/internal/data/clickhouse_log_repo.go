package data

import (
	"context"
	"time"
	"voicehelper/cmd/model-router/internal/domain"
	"voicehelper/cmd/model-router/internal/infrastructure"

	"github.com/go-kratos/kratos/v2/log"
)

// ClickHouseLogRepository ClickHouse日志仓储
type ClickHouseLogRepository struct {
	ch  *infrastructure.ClickHouseClient
	log *log.Helper
}

// NewClickHouseLogRepo 创建ClickHouse日志仓储
func NewClickHouseLogRepo(ch *infrastructure.ClickHouseClient, logger log.Logger) *ClickHouseLogRepository {
	return &ClickHouseLogRepository{
		ch:  ch,
		log: log.NewHelper(logger),
	}
}

// SaveRequestLog 保存请求日志
func (r *ClickHouseLogRepository) SaveRequestLog(ctx context.Context, req *domain.ModelRequest, resp *domain.ModelResponse) error {
	log := &infrastructure.RequestLog{
		RequestID:        req.RequestID,
		TenantID:         req.TenantID,
		UserID:           req.UserID,
		ModelID:          req.ModelID,
		ModelName:        req.ModelName,
		ModelProvider:    req.Provider,
		RequestTime:      req.RequestTime,
		ResponseTime:     time.Now(),
		LatencyMs:        uint32(time.Since(req.RequestTime).Milliseconds()),
		Success:          resp.Success,
		ErrorMessage:     resp.ErrorMessage,
		ErrorCode:        resp.ErrorCode,
		PromptTokens:     uint32(resp.PromptTokens),
		CompletionTokens: uint32(resp.CompletionTokens),
		TotalTokens:      uint32(resp.TotalTokens),
		CostUSD:          resp.CostUSD,
		RequestType:      req.RequestType,
		Stream:           req.Stream,
		RoutingStrategy:  req.RoutingStrategy,
		FallbackUsed:     req.FallbackUsed,
		ABTestVariant:    req.ABTestVariant,
		Metadata:         req.MetadataJSON(),
	}

	if err := r.ch.InsertRequestLog(ctx, log); err != nil {
		r.log.Errorf("failed to save request log to clickhouse: %v", err)
		// 不抛出错误，避免影响主流程
		return nil
	}

	return nil
}

// BatchSaveRequestLogs 批量保存请求日志
func (r *ClickHouseLogRepository) BatchSaveRequestLogs(ctx context.Context, logs []*infrastructure.RequestLog) error {
	if len(logs) == 0 {
		return nil
	}

	if err := r.ch.BatchInsertRequestLogs(ctx, logs); err != nil {
		r.log.Errorf("failed to batch save request logs: %v", err)
		return err
	}

	r.log.Infof("batch saved %d request logs to clickhouse", len(logs))
	return nil
}

// GetDailyStats 获取日统计
func (r *ClickHouseLogRepository) GetDailyStats(
	ctx context.Context,
	tenantID string,
	startDate, endDate time.Time,
) ([]*infrastructure.DailyStats, error) {
	return r.ch.GetDailyStats(ctx, tenantID, startDate, endDate)
}

// GetModelCostAnalysis 获取模型成本分析
func (r *ClickHouseLogRepository) GetModelCostAnalysis(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
	topN int,
) ([]*infrastructure.ModelCostAnalysis, error) {
	return r.ch.GetModelCostAnalysis(ctx, tenantID, startTime, endTime, topN)
}

// GetHourlyTrend 获取小时趋势
func (r *ClickHouseLogRepository) GetHourlyTrend(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
) ([]*infrastructure.HourlyTrend, error) {
	return r.ch.GetHourlyTrend(ctx, tenantID, startTime, endTime)
}

// QueryRequestLogs 查询请求日志
func (r *ClickHouseLogRepository) QueryRequestLogs(
	ctx context.Context,
	tenantID string,
	modelID string,
	startTime, endTime time.Time,
	limit int,
) ([]*infrastructure.RequestLog, error) {
	return r.ch.QueryRequestLogs(ctx, tenantID, modelID, startTime, endTime, limit)
}

// HealthCheck 健康检查
func (r *ClickHouseLogRepository) HealthCheck(ctx context.Context) error {
	return r.ch.HealthCheck(ctx)
}
