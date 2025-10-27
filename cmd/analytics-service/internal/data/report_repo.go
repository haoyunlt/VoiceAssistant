package data

import (
	"context"
	"encoding/json"
	"time"
	"voiceassistant/cmd/analytics-service/internal/domain"

	"gorm.io/gorm"
)

// ReportDO 报表数据对象
type ReportDO struct {
	ID          string `gorm:"primaryKey"`
	TenantID    string `gorm:"index"`
	Type        string
	Name        string
	Description string
	Status      string
	Format      string
	Data        string // JSON string
	FileURL     string
	CreatedBy   string
	CreatedAt   time.Time
	CompletedAt *time.Time
}

// TableName 指定表名
func (ReportDO) TableName() string {
	return "analytics.reports"
}

// ReportRepository 报表仓储实现
type ReportRepository struct {
	db *DB
}

// NewReportRepository 创建报表仓储
func NewReportRepository(db *DB) domain.ReportRepository {
	return &ReportRepository{
		db: db,
	}
}

// CreateReport 创建报表
func (r *ReportRepository) CreateReport(ctx context.Context, report *domain.Report) error {
	do := r.toDataObject(report)
	return r.db.WithContext(ctx).Create(do).Error
}

// GetReport 获取报表
func (r *ReportRepository) GetReport(ctx context.Context, id string) (*domain.Report, error) {
	var do ReportDO
	if err := r.db.WithContext(ctx).Where("id = ?", id).First(&do).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrReportNotFound
		}
		return nil, err
	}

	return r.toDomain(&do), nil
}

// UpdateReport 更新报表
func (r *ReportRepository) UpdateReport(ctx context.Context, report *domain.Report) error {
	do := r.toDataObject(report)
	return r.db.WithContext(ctx).Save(do).Error
}

// ListReports 列出报表
func (r *ReportRepository) ListReports(ctx context.Context, tenantID string, limit, offset int) ([]*domain.Report, int, error) {
	var dos []ReportDO
	var total int64

	db := r.db.WithContext(ctx).Where("tenant_id = ?", tenantID)

	// 获取总数
	if err := db.Model(&ReportDO{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// 分页查询
	if err := db.Order("created_at DESC").Limit(limit).Offset(offset).Find(&dos).Error; err != nil {
		return nil, 0, err
	}

	reports := make([]*domain.Report, len(dos))
	for i, do := range dos {
		reports[i] = r.toDomain(&do)
	}

	return reports, int(total), nil
}

// DeleteReport 删除报表
func (r *ReportRepository) DeleteReport(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&ReportDO{}).Error
}

// toDataObject 转换为数据对象
func (r *ReportRepository) toDataObject(report *domain.Report) *ReportDO {
	dataJSON, _ := json.Marshal(report.Data)

	return &ReportDO{
		ID:          report.ID,
		TenantID:    report.TenantID,
		Type:        string(report.Type),
		Name:        report.Name,
		Description: report.Description,
		Status:      string(report.Status),
		Format:      string(report.Format),
		Data:        string(dataJSON),
		FileURL:     report.FileURL,
		CreatedBy:   report.CreatedBy,
		CreatedAt:   report.CreatedAt,
		CompletedAt: report.CompletedAt,
	}
}

// toDomain 转换为领域对象
func (r *ReportRepository) toDomain(do *ReportDO) *domain.Report {
	var data map[string]interface{}
	_ = json.Unmarshal([]byte(do.Data), &data)

	return &domain.Report{
		ID:          do.ID,
		TenantID:    do.TenantID,
		Type:        domain.ReportType(do.Type),
		Name:        do.Name,
		Description: do.Description,
		Status:      domain.ReportStatus(do.Status),
		Format:      domain.ReportFormat(do.Format),
		Data:        data,
		FileURL:     do.FileURL,
		CreatedBy:   do.CreatedBy,
		CreatedAt:   do.CreatedAt,
		CompletedAt: do.CompletedAt,
	}
}
