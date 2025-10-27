package data

import (
	"context"
	"time"

	"voiceassistant/cmd/analytics-service/internal/domain"
)

// MetricRepository 指标仓储实现
type MetricRepository struct {
	ch *ClickHouseClient
}

// NewMetricRepository 创建指标仓储
func NewMetricRepository(ch *ClickHouseClient) domain.MetricRepository {
	return &MetricRepository{
		ch: ch,
	}
}

// RecordMetric 记录指标
func (r *MetricRepository) RecordMetric(ctx context.Context, metric *domain.Metric) error {
	// 简化实现：将指标写入 ClickHouse
	query := `
		INSERT INTO metrics (id, tenant_id, type, name, value, timestamp)
		VALUES (?, ?, ?, ?, ?, ?)
	`

	return r.ch.Exec(ctx, query,
		metric.ID,
		metric.TenantID,
		string(metric.Type),
		metric.Name,
		metric.Value,
		metric.Timestamp,
	)
}

// GetUsageStats 获取使用统计
func (r *MetricRepository) GetUsageStats(ctx context.Context, tenantID string, period domain.TimePeriod, start, end time.Time) (*domain.UsageStats, error) {
	// 简化实现：从 ClickHouse 查询聚合数据
	query := `
		SELECT
			COUNT(DISTINCT conversation_id) as total_conversations,
			COUNT(*) as total_messages,
			SUM(tokens_used) as total_tokens,
			SUM(cost_usd) as total_cost,
			COUNT(DISTINCT user_id) as active_users
		FROM message_events
		WHERE tenant_id = ?
			AND created_at >= ?
			AND created_at < ?
	`

	row := r.ch.QueryRow(ctx, query, tenantID, start, end)

	stats := &domain.UsageStats{
		TenantID:  tenantID,
		Period:    period,
		StartTime: start,
		EndTime:   end,
	}

	err := row.Scan(
		&stats.TotalConversations,
		&stats.TotalMessages,
		&stats.TotalTokens,
		&stats.TotalCost,
		&stats.ActiveUsers,
	)

	return stats, err
}

// GetModelStats 获取模型统计
func (r *MetricRepository) GetModelStats(ctx context.Context, tenantID string, period domain.TimePeriod, start, end time.Time) ([]*domain.ModelStats, error) {
	// 简化实现：从 ClickHouse 查询模型统计
	query := `
		SELECT
			model_name,
			provider,
			COUNT(*) as request_count,
			SUM(tokens_used) as total_tokens,
			SUM(cost_usd) as total_cost,
			AVG(latency_ms) as avg_latency,
			CAST(SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as error_rate
		FROM message_events
		WHERE tenant_id = ?
			AND created_at >= ?
			AND created_at < ?
		GROUP BY model_name, provider
		ORDER BY request_count DESC
	`

	rows, err := r.ch.Query(ctx, query, tenantID, start, end)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var stats []*domain.ModelStats
	for rows.Next() {
		stat := &domain.ModelStats{
			TenantID:  tenantID,
			Period:    period,
			StartTime: start,
			EndTime:   end,
		}

		if err := rows.Scan(
			&stat.ModelName,
			&stat.Provider,
			&stat.RequestCount,
			&stat.TotalTokens,
			&stat.TotalCost,
			&stat.AvgLatency,
			&stat.ErrorRate,
		); err != nil {
			return nil, err
		}

		stats = append(stats, stat)
	}

	return stats, nil
}

// GetUserBehavior 获取用户行为统计
func (r *MetricRepository) GetUserBehavior(ctx context.Context, tenantID, userID string, period domain.TimePeriod, start, end time.Time) (*domain.UserBehavior, error) {
	// 简化实现
	query := `
		SELECT
			COUNT(DISTINCT conversation_id) as conversation_count,
			COUNT(*) as message_count,
			AVG(session_duration_ms) / 1000.0 as avg_session_duration,
			MAX(created_at) as last_active_time
		FROM message_events
		WHERE tenant_id = ?
			AND user_id = ?
			AND created_at >= ?
			AND created_at < ?
	`

	row := r.ch.QueryRow(ctx, query, tenantID, userID, start, end)

	behavior := &domain.UserBehavior{
		TenantID:  tenantID,
		UserID:    userID,
		Period:    period,
		StartTime: start,
		EndTime:   end,
	}

	err := row.Scan(
		&behavior.ConversationCount,
		&behavior.MessageCount,
		&behavior.AvgSessionDuration,
		&behavior.LastActiveTime,
	)

	return behavior, err
}

// GetRealtimeStats 获取实时统计
func (r *MetricRepository) GetRealtimeStats(ctx context.Context, tenantID string) (*domain.RealtimeStats, error) {
	// 简化实现：查询最近1分钟的数据
	query := `
		SELECT
			COUNT(*) / 60.0 as current_qps,
			COUNT(DISTINCT user_id) as current_active_users,
			AVG(latency_ms) as current_latency
		FROM message_events
		WHERE tenant_id = ?
			AND created_at >= now() - INTERVAL 1 MINUTE
	`

	row := r.ch.QueryRow(ctx, query, tenantID)

	stats := &domain.RealtimeStats{
		TenantID:  tenantID,
		Timestamp: time.Now(),
	}

	err := row.Scan(
		&stats.CurrentQPS,
		&stats.CurrentActiveUsers,
		&stats.CurrentLatency,
	)

	return stats, err
}

// GetCostBreakdown 获取成本分解
func (r *MetricRepository) GetCostBreakdown(ctx context.Context, tenantID string, period domain.TimePeriod, start, end time.Time) (*domain.CostBreakdown, error) {
	// 简化实现：查询成本分解
	query := `
		SELECT
			SUM(CASE WHEN cost_type = 'model' THEN cost_usd ELSE 0 END) as model_cost,
			SUM(CASE WHEN cost_type = 'embedding' THEN cost_usd ELSE 0 END) as embedding_cost,
			SUM(CASE WHEN cost_type = 'rerank' THEN cost_usd ELSE 0 END) as rerank_cost,
			SUM(cost_usd) as total_cost
		FROM cost_events
		WHERE tenant_id = ?
			AND created_at >= ?
			AND created_at < ?
	`

	row := r.ch.QueryRow(ctx, query, tenantID, start, end)

	breakdown := &domain.CostBreakdown{
		TenantID:  tenantID,
		Period:    period,
		StartTime: start,
		EndTime:   end,
	}

	err := row.Scan(
		&breakdown.ModelCost,
		&breakdown.EmbeddingCost,
		&breakdown.RerankCost,
		&breakdown.TotalCost,
	)

	return breakdown, err
}
