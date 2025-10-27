package data

import (
	"context"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

// ModelMetricsPO 模型指标持久化对象
type ModelMetricsPO struct {
	ModelID         string  `gorm:"primaryKey;size:64"`
	TotalRequests   int64   `gorm:"not null;default:0"`
	SuccessRequests int64   `gorm:"not null;default:0"`
	FailedRequests  int64   `gorm:"not null;default:0"`
	AvgLatencyMs    float64 `gorm:"not null;default:0"`
	P95LatencyMs    float64 `gorm:"not null;default:0"`
	P99LatencyMs    float64 `gorm:"not null;default:0"`
	TotalTokens     int64   `gorm:"not null;default:0"`
	TotalCost       float64 `gorm:"type:decimal(12,4);not null;default:0"`
	ErrorRate       float64 `gorm:"not null;default:0"`
	LastRequestAt   *time.Time
	UpdatedAt       time.Time
}

// TableName 表名
func (ModelMetricsPO) TableName() string {
	return "model_router.model_metrics"
}

// ModelMetricsRepository 模型指标仓储实现
type ModelMetricsRepository struct {
	data *Data
	log  *log.Helper
}

// NewModelMetricsRepo 创建模型指标仓储
func NewModelMetricsRepo(data *Data, logger log.Logger) domain.ModelMetricsRepository {
	return &ModelMetricsRepository{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Save 保存指标
func (r *ModelMetricsRepository) Save(ctx context.Context, metrics *domain.ModelMetrics) error {
	po := r.toMetricsPO(metrics)

	// Use Save instead of upsert for simplicity
	if err := r.data.db.WithContext(ctx).
		Save(po).Error; err != nil {
		r.log.Errorf("failed to save metrics: %v", err)
		return err
	}

	return nil
}

// GetByModelID 根据模型ID获取指标
func (r *ModelMetricsRepository) GetByModelID(ctx context.Context, modelID string) (*domain.ModelMetrics, error) {
	var po ModelMetricsPO
	if err := r.data.db.WithContext(ctx).
		Where("model_id = ?", modelID).
		First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			// 返回空指标
			return domain.NewModelMetrics(modelID), nil
		}
		r.log.Errorf("failed to get metrics: %v", err)
		return nil, err
	}

	return r.toDomainMetrics(&po), nil
}

// ListAll 获取所有指标
func (r *ModelMetricsRepository) ListAll(ctx context.Context) ([]*domain.ModelMetrics, error) {
	var pos []ModelMetricsPO

	if err := r.data.db.WithContext(ctx).Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list metrics: %v", err)
		return nil, err
	}

	metrics := make([]*domain.ModelMetrics, len(pos))
	for i, po := range pos {
		metrics[i] = r.toDomainMetrics(&po)
	}

	return metrics, nil
}

// UpdateMetrics 更新指标
func (r *ModelMetricsRepository) UpdateMetrics(
	ctx context.Context,
	modelID string,
	success bool,
	latencyMs int,
	tokens int,
	cost float64,
) error {
	// 获取现有指标
	metrics, err := r.GetByModelID(ctx, modelID)
	if err != nil {
		return err
	}

	// 记录请求
	metrics.RecordRequest(success, latencyMs, tokens, cost)

	// 保存
	return r.Save(ctx, metrics)
}

// toMetricsPO 转换为持久化对象
func (r *ModelMetricsRepository) toMetricsPO(metrics *domain.ModelMetrics) *ModelMetricsPO {
	return &ModelMetricsPO{
		ModelID:         metrics.ModelID,
		TotalRequests:   metrics.TotalRequests,
		SuccessRequests: metrics.SuccessRequests,
		FailedRequests:  metrics.FailedRequests,
		AvgLatencyMs:    metrics.AvgLatencyMs,
		P95LatencyMs:    metrics.P95LatencyMs,
		P99LatencyMs:    metrics.P99LatencyMs,
		TotalTokens:     metrics.TotalTokens,
		TotalCost:       metrics.TotalCost,
		ErrorRate:       metrics.ErrorRate,
		LastRequestAt:   metrics.LastRequestAt,
		UpdatedAt:       metrics.UpdatedAt,
	}
}

// toDomainMetrics 转换为领域对象
func (r *ModelMetricsRepository) toDomainMetrics(po *ModelMetricsPO) *domain.ModelMetrics {
	return &domain.ModelMetrics{
		ModelID:         po.ModelID,
		TotalRequests:   po.TotalRequests,
		SuccessRequests: po.SuccessRequests,
		FailedRequests:  po.FailedRequests,
		AvgLatencyMs:    po.AvgLatencyMs,
		P95LatencyMs:    po.P95LatencyMs,
		P99LatencyMs:    po.P99LatencyMs,
		TotalTokens:     po.TotalTokens,
		TotalCost:       po.TotalCost,
		ErrorRate:       po.ErrorRate,
		LastRequestAt:   po.LastRequestAt,
		UpdatedAt:       po.UpdatedAt,
	}
}

// upsert 返回PostgreSQL upsert子句
func upsert() interface{} {
	// 使用GORM的OnConflict
	return nil // 简化实现，实际需要GORM v2的Clauses
}
