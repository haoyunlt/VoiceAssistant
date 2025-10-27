package data

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"voiceassistant/cmd/identity-service/internal/biz"

	"gorm.io/gorm"
)

// AuditLogDO 审计日志数据对象
type AuditLogDO struct {
	ID        string `gorm:"primaryKey;size:100"`
	TenantID  string `gorm:"index;size:50"`
	UserID    string `gorm:"index;size:50"`
	Action    string `gorm:"index;size:50"`
	Resource  string `gorm:"size:255"`
	Level     string `gorm:"index;size:20"`
	Status    string `gorm:"index;size:20"`
	IPAddress string `gorm:"size:50"`
	UserAgent string `gorm:"size:500"`
	Details   string `gorm:"type:text"`
	Error     string `gorm:"type:text"`
	CreatedAt int64  `gorm:"index"`
}

// TableName 指定表名
func (AuditLogDO) TableName() string {
	return "audit_logs"
}

// auditLogRepo 审计日志仓储实现
type auditLogRepo struct {
	db *gorm.DB
}

// NewAuditLogRepository 创建审计日志仓储
func NewAuditLogRepository(db *gorm.DB) biz.AuditLogRepository {
	return &auditLogRepo{
		db: db,
	}
}

// Create 创建审计日志
func (r *auditLogRepo) Create(ctx context.Context, auditLog *biz.AuditLog) error {
	// 转换为DO
	do := r.toDataObject(auditLog)

	// 保存到数据库
	if err := r.db.WithContext(ctx).Create(do).Error; err != nil {
		return fmt.Errorf("failed to create audit log: %w", err)
	}

	return nil
}

// Query 查询审计日志
func (r *auditLogRepo) Query(ctx context.Context, filters *biz.AuditLogFilters) ([]*biz.AuditLog, int, error) {
	query := r.db.WithContext(ctx).Model(&AuditLogDO{})

	// 应用过滤条件
	if filters.TenantID != "" {
		query = query.Where("tenant_id = ?", filters.TenantID)
	}
	if filters.UserID != "" {
		query = query.Where("user_id = ?", filters.UserID)
	}
	if filters.Action != "" {
		query = query.Where("action = ?", filters.Action)
	}
	if filters.Resource != "" {
		query = query.Where("resource LIKE ?", "%"+filters.Resource+"%")
	}
	if filters.Level != "" {
		query = query.Where("level = ?", filters.Level)
	}
	if filters.Status != "" {
		query = query.Where("status = ?", filters.Status)
	}
	if filters.StartTime != nil {
		query = query.Where("created_at >= ?", filters.StartTime.Unix())
	}
	if filters.EndTime != nil {
		query = query.Where("created_at <= ?", filters.EndTime.Unix())
	}

	// 获取总数
	var total int64
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to count audit logs: %w", err)
	}

	// 分页查询
	limit := filters.Limit
	if limit <= 0 {
		limit = 10
	}
	offset := filters.Offset
	if offset < 0 {
		offset = 0
	}

	var dos []*AuditLogDO
	if err := query.Order("created_at DESC").
		Limit(limit).
		Offset(offset).
		Find(&dos).Error; err != nil {
		return nil, 0, fmt.Errorf("failed to query audit logs: %w", err)
	}

	// 转换为领域对象
	logs := make([]*biz.AuditLog, len(dos))
	for i, do := range dos {
		logs[i] = r.toDomainObject(do)
	}

	return logs, int(total), nil
}

// GetByID 根据ID获取审计日志
func (r *auditLogRepo) GetByID(ctx context.Context, id string) (*biz.AuditLog, error) {
	var do AuditLogDO
	if err := r.db.WithContext(ctx).Where("id = ?", id).First(&do).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("audit log not found: %s", id)
		}
		return nil, fmt.Errorf("failed to get audit log: %w", err)
	}

	return r.toDomainObject(&do), nil
}

// toDataObject 转换为数据对象
func (r *auditLogRepo) toDataObject(log *biz.AuditLog) *AuditLogDO {
	detailsJSON, _ := json.Marshal(log.Details)

	return &AuditLogDO{
		ID:        log.ID,
		TenantID:  log.TenantID,
		UserID:    log.UserID,
		Action:    string(log.Action),
		Resource:  log.Resource,
		Level:     string(log.Level),
		Status:    log.Status,
		IPAddress: log.IPAddress,
		UserAgent: log.UserAgent,
		Details:   string(detailsJSON),
		Error:     log.Error,
		CreatedAt: log.CreatedAt.Unix(),
	}
}

// toDomainObject 转换为领域对象
func (r *auditLogRepo) toDomainObject(do *AuditLogDO) *biz.AuditLog {
	var details map[string]interface{}
	if do.Details != "" {
		json.Unmarshal([]byte(do.Details), &details)
	}

	return &biz.AuditLog{
		ID:        do.ID,
		TenantID:  do.TenantID,
		UserID:    do.UserID,
		Action:    biz.AuditAction(do.Action),
		Resource:  do.Resource,
		Level:     biz.AuditLevel(do.Level),
		Status:    do.Status,
		IPAddress: do.IPAddress,
		UserAgent: do.UserAgent,
		Details:   details,
		Error:     do.Error,
		CreatedAt: time.Unix(do.CreatedAt, 0),
	}
}
