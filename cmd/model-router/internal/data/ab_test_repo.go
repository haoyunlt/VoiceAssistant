package data

import (
	"context"
	"encoding/json"
	"time"

	"voicehelper/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

// ABTestPO 持久化对象（PostgreSQL）
type ABTestPO struct {
	ID           string    `gorm:"primaryKey;size:64"`
	Name         string    `gorm:"size:100;not null;uniqueIndex"`
	Description  string    `gorm:"size:500"`
	StartTime    time.Time `gorm:"not null;index"`
	EndTime      time.Time `gorm:"not null;index"`
	Status       string    `gorm:"size:20;not null;index"`
	Strategy     string    `gorm:"size:50;not null"`
	VariantsJSON string    `gorm:"type:jsonb;not null;column:variants"`
	MetadataJSON string    `gorm:"type:jsonb;column:metadata"`
	CreatedAt    time.Time `gorm:"not null"`
	UpdatedAt    time.Time `gorm:"not null"`
	CreatedBy    string    `gorm:"size:64"`
}

// TableName 表名
func (ABTestPO) TableName() string {
	return "model_router.ab_tests"
}

// ABTestRepositoryImpl 仓储实现
type ABTestRepositoryImpl struct {
	db  *gorm.DB
	log *log.Helper
}

// NewABTestRepository 创建A/B测试仓储
func NewABTestRepository(data *Data, logger log.Logger) domain.ABTestRepository {
	return &ABTestRepositoryImpl{
		db:  data.db,
		log: log.NewHelper(logger),
	}
}

// CreateTest 创建测试
func (r *ABTestRepositoryImpl) CreateTest(ctx context.Context, test *domain.ABTestConfig) error {
	po, err := r.toTestPO(test)
	if err != nil {
		return err
	}

	if err := r.db.WithContext(ctx).Create(po).Error; err != nil {
		r.log.Errorf("failed to create ab test: %v", err)
		return err
	}

	return nil
}

// GetTest 获取测试
func (r *ABTestRepositoryImpl) GetTest(ctx context.Context, testID string) (*domain.ABTestConfig, error) {
	var po ABTestPO
	if err := r.db.WithContext(ctx).Where("id = ?", testID).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrTestNotFound
		}
		r.log.Errorf("failed to get ab test: %v", err)
		return nil, err
	}

	return r.toDomainTest(&po)
}

// UpdateTest 更新测试
func (r *ABTestRepositoryImpl) UpdateTest(ctx context.Context, test *domain.ABTestConfig) error {
	po, err := r.toTestPO(test)
	if err != nil {
		return err
	}

	if err := r.db.WithContext(ctx).
		Model(&ABTestPO{}).
		Where("id = ?", test.ID).
		Updates(map[string]interface{}{
			"name":        po.Name,
			"description": po.Description,
			"start_time":  po.StartTime,
			"end_time":    po.EndTime,
			"status":      po.Status,
			"strategy":    po.Strategy,
			"variants":    po.VariantsJSON,
			"metadata":    po.MetadataJSON,
			"updated_at":  time.Now(),
		}).Error; err != nil {
		r.log.Errorf("failed to update ab test: %v", err)
		return err
	}

	return nil
}

// ListTests 列出测试
func (r *ABTestRepositoryImpl) ListTests(ctx context.Context, filters *domain.TestFilters) ([]*domain.ABTestConfig, error) {
	var pos []ABTestPO

	query := r.db.WithContext(ctx).Model(&ABTestPO{})

	// 应用过滤条件
	if filters != nil {
		if filters.Status != "" {
			query = query.Where("status = ?", filters.Status)
		}
		if filters.CreatedBy != "" {
			query = query.Where("created_by = ?", filters.CreatedBy)
		}
		if !filters.StartDate.IsZero() {
			query = query.Where("created_at >= ?", filters.StartDate)
		}
		if !filters.EndDate.IsZero() {
			query = query.Where("created_at <= ?", filters.EndDate)
		}

		if filters.Limit > 0 {
			query = query.Limit(filters.Limit)
		}
		if filters.Offset > 0 {
			query = query.Offset(filters.Offset)
		}
	}

	if err := query.Order("created_at DESC").Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list ab tests: %v", err)
		return nil, err
	}

	return r.toDomainTests(pos)
}

// DeleteTest 删除测试
func (r *ABTestRepositoryImpl) DeleteTest(ctx context.Context, testID string) error {
	if err := r.db.WithContext(ctx).Delete(&ABTestPO{}, "id = ?", testID).Error; err != nil {
		r.log.Errorf("failed to delete ab test: %v", err)
		return err
	}

	return nil
}

// RecordMetric 记录指标（暂时使用PostgreSQL，后续迁移到ClickHouse）
func (r *ABTestRepositoryImpl) RecordMetric(ctx context.Context, metric *domain.ABTestMetric) error {
	// TODO: 实现ClickHouse存储
	// 这里先用简单的日志记录
	r.log.Infof("Record metric: test=%s, variant=%s, success=%v, latency=%.2fms",
		metric.TestID, metric.VariantID, metric.Success, metric.LatencyMs)
	return nil
}

// GetMetrics 获取指标（暂时返回空）
func (r *ABTestRepositoryImpl) GetMetrics(
	ctx context.Context,
	testID, variantID string,
	timeRange domain.TimeRange,
) ([]*domain.ABTestMetric, error) {
	// TODO: 实现ClickHouse查询
	return []*domain.ABTestMetric{}, nil
}

// AggregateResults 聚合结果（暂时返回空）
func (r *ABTestRepositoryImpl) AggregateResults(
	ctx context.Context,
	testID string,
) (map[string]*domain.ABTestResult, error) {
	// TODO: 实现ClickHouse聚合查询
	return make(map[string]*domain.ABTestResult), nil
}

// toTestPO 转换为持久化对象
func (r *ABTestRepositoryImpl) toTestPO(test *domain.ABTestConfig) (*ABTestPO, error) {
	variantsJSON, err := json.Marshal(test.Variants)
	if err != nil {
		return nil, err
	}

	metadataJSON, _ := json.Marshal(test.Metadata)

	return &ABTestPO{
		ID:           test.ID,
		Name:         test.Name,
		Description:  test.Description,
		StartTime:    test.StartTime,
		EndTime:      test.EndTime,
		Status:       string(test.Status),
		Strategy:     test.Strategy,
		VariantsJSON: string(variantsJSON),
		MetadataJSON: string(metadataJSON),
		CreatedAt:    test.CreatedAt,
		UpdatedAt:    test.UpdatedAt,
		CreatedBy:    test.CreatedBy,
	}, nil
}

// toDomainTest 转换为领域对象
func (r *ABTestRepositoryImpl) toDomainTest(po *ABTestPO) (*domain.ABTestConfig, error) {
	var variants []*domain.ABVariant
	if err := json.Unmarshal([]byte(po.VariantsJSON), &variants); err != nil {
		return nil, err
	}

	var metadata map[string]interface{}
	if po.MetadataJSON != "" {
		json.Unmarshal([]byte(po.MetadataJSON), &metadata)
	}

	return &domain.ABTestConfig{
		ID:          po.ID,
		Name:        po.Name,
		Description: po.Description,
		StartTime:   po.StartTime,
		EndTime:     po.EndTime,
		Status:      domain.TestStatus(po.Status),
		Strategy:    po.Strategy,
		Variants:    variants,
		Metadata:    metadata,
		CreatedAt:   po.CreatedAt,
		UpdatedAt:   po.UpdatedAt,
		CreatedBy:   po.CreatedBy,
	}, nil
}

// toDomainTests 批量转换
func (r *ABTestRepositoryImpl) toDomainTests(pos []ABTestPO) ([]*domain.ABTestConfig, error) {
	tests := make([]*domain.ABTestConfig, 0, len(pos))
	for _, po := range pos {
		test, err := r.toDomainTest(&po)
		if err != nil {
			r.log.Warnf("failed to convert ab test: %v", err)
			continue
		}
		tests = append(tests, test)
	}
	return tests, nil
}


