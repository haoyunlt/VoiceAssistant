package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voiceassistant/cmd/knowledge-service/internal/domain"
	"gorm.io/gorm"
)

// KnowledgeBasePO 知识库持久化对象
type KnowledgeBasePO struct {
	ID             string `gorm:"primaryKey;size:64"`
	Name           string `gorm:"size:255;not null;index:idx_name"`
	Description    string `gorm:"type:text"`
	Type           string `gorm:"size:20;not null;index:idx_type"`
	Status         string `gorm:"size:20;not null;index:idx_status"`
	TenantID       string `gorm:"size:64;not null;index:idx_tenant"`
	CreatedBy      string `gorm:"size:64;not null"`
	EmbeddingModel string `gorm:"size:50;not null"`
	EmbeddingDim   int    `gorm:"not null"`
	ChunkSize      int    `gorm:"not null"`
	ChunkOverlap   int    `gorm:"not null"`
	Settings       string `gorm:"type:jsonb"`
	DocumentCount  int    `gorm:"not null;default:0"`
	ChunkCount     int    `gorm:"not null;default:0"`
	TotalSize      int64  `gorm:"not null;default:0"`
	LastIndexedAt  *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// TableName 表名
func (KnowledgeBasePO) TableName() string {
	return "knowledge.knowledge_bases"
}

// KnowledgeBaseRepository 知识库仓储实现
type KnowledgeBaseRepository struct {
	data *Data
	log  *log.Helper
}

// NewKnowledgeBaseRepo 创建知识库仓储
func NewKnowledgeBaseRepo(data *Data, logger log.Logger) domain.KnowledgeBaseRepository {
	return &KnowledgeBaseRepository{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create 创建知识库
func (r *KnowledgeBaseRepository) Create(ctx context.Context, kb *domain.KnowledgeBase) error {
	po, err := r.toKnowledgeBasePO(kb)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		r.log.Errorf("failed to create knowledge base: %v", err)
		return err
	}

	return nil
}

// GetByID 根据ID获取知识库
func (r *KnowledgeBaseRepository) GetByID(ctx context.Context, id string) (*domain.KnowledgeBase, error) {
	var po KnowledgeBasePO
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrKnowledgeBaseNotFound
		}
		r.log.Errorf("failed to get knowledge base: %v", err)
		return nil, err
	}

	return r.toDomainKnowledgeBase(&po)
}

// Update 更新知识库
func (r *KnowledgeBaseRepository) Update(ctx context.Context, kb *domain.KnowledgeBase) error {
	po, err := r.toKnowledgeBasePO(kb)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).
		Model(&KnowledgeBasePO{}).
		Where("id = ?", kb.ID).
		Updates(po).Error; err != nil {
		r.log.Errorf("failed to update knowledge base: %v", err)
		return err
	}

	return nil
}

// Delete 删除知识库
func (r *KnowledgeBaseRepository) Delete(ctx context.Context, id string) error {
	if err := r.data.db.WithContext(ctx).Delete(&KnowledgeBasePO{}, "id = ?", id).Error; err != nil {
		r.log.Errorf("failed to delete knowledge base: %v", err)
		return err
	}

	return nil
}

// ListByTenant 获取租户的知识库列表
func (r *KnowledgeBaseRepository) ListByTenant(
	ctx context.Context,
	tenantID string,
	offset, limit int,
) ([]*domain.KnowledgeBase, int64, error) {
	var pos []KnowledgeBasePO
	var total int64

	// 查询总数
	if err := r.data.db.WithContext(ctx).
		Model(&KnowledgeBasePO{}).
		Where("tenant_id = ?", tenantID).
		Count(&total).Error; err != nil {
		r.log.Errorf("failed to count knowledge bases: %v", err)
		return nil, 0, err
	}

	// 查询列表
	if err := r.data.db.WithContext(ctx).
		Where("tenant_id = ?", tenantID).
		Order("created_at DESC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list knowledge bases: %v", err)
		return nil, 0, err
	}

	kbs := make([]*domain.KnowledgeBase, 0, len(pos))
	for _, po := range pos {
		kb, err := r.toDomainKnowledgeBase(&po)
		if err != nil {
			r.log.Warnf("failed to convert knowledge base: %v", err)
			continue
		}
		kbs = append(kbs, kb)
	}

	return kbs, total, nil
}

// ListByStatus 根据状态获取知识库列表
func (r *KnowledgeBaseRepository) ListByStatus(
	ctx context.Context,
	status domain.KnowledgeBaseStatus,
	offset, limit int,
) ([]*domain.KnowledgeBase, error) {
	var pos []KnowledgeBasePO

	if err := r.data.db.WithContext(ctx).
		Where("status = ?", status).
		Order("created_at DESC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list knowledge bases by status: %v", err)
		return nil, err
	}

	kbs := make([]*domain.KnowledgeBase, 0, len(pos))
	for _, po := range pos {
		kb, err := r.toDomainKnowledgeBase(&po)
		if err != nil {
			r.log.Warnf("failed to convert knowledge base: %v", err)
			continue
		}
		kbs = append(kbs, kb)
	}

	return kbs, nil
}

// toKnowledgeBasePO 转换为持久化对象
func (r *KnowledgeBaseRepository) toKnowledgeBasePO(kb *domain.KnowledgeBase) (*KnowledgeBasePO, error) {
	settingsJSON, _ := json.Marshal(kb.Settings)

	return &KnowledgeBasePO{
		ID:             kb.ID,
		Name:           kb.Name,
		Description:    kb.Description,
		Type:           string(kb.Type),
		Status:         string(kb.Status),
		TenantID:       kb.TenantID,
		CreatedBy:      kb.CreatedBy,
		EmbeddingModel: string(kb.EmbeddingModel),
		EmbeddingDim:   kb.EmbeddingDim,
		ChunkSize:      kb.ChunkSize,
		ChunkOverlap:   kb.ChunkOverlap,
		Settings:       string(settingsJSON),
		DocumentCount:  kb.DocumentCount,
		ChunkCount:     kb.ChunkCount,
		TotalSize:      kb.TotalSize,
		LastIndexedAt:  kb.LastIndexedAt,
		CreatedAt:      kb.CreatedAt,
		UpdatedAt:      kb.UpdatedAt,
	}, nil
}

// toDomainKnowledgeBase 转换为领域对象
func (r *KnowledgeBaseRepository) toDomainKnowledgeBase(po *KnowledgeBasePO) (*domain.KnowledgeBase, error) {
	var settings map[string]interface{}
	if po.Settings != "" {
		json.Unmarshal([]byte(po.Settings), &settings)
	}

	return &domain.KnowledgeBase{
		ID:             po.ID,
		Name:           po.Name,
		Description:    po.Description,
		Type:           domain.KnowledgeBaseType(po.Type),
		Status:         domain.KnowledgeBaseStatus(po.Status),
		TenantID:       po.TenantID,
		CreatedBy:      po.CreatedBy,
		EmbeddingModel: domain.EmbeddingModel(po.EmbeddingModel),
		EmbeddingDim:   po.EmbeddingDim,
		ChunkSize:      po.ChunkSize,
		ChunkOverlap:   po.ChunkOverlap,
		Settings:       settings,
		DocumentCount:  po.DocumentCount,
		ChunkCount:     po.ChunkCount,
		TotalSize:      po.TotalSize,
		LastIndexedAt:  po.LastIndexedAt,
		CreatedAt:      po.CreatedAt,
		UpdatedAt:      po.UpdatedAt,
	}, nil
}
