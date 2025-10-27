package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voiceassistant/cmd/knowledge-service/internal/domain"
	"gorm.io/gorm"
)

// DocumentPO 文档持久化对象
type DocumentPO struct {
	ID              string `gorm:"primaryKey;size:64"`
	KnowledgeBaseID string `gorm:"size:64;not null;index:idx_knowledge_base"`
	Name            string `gorm:"size:255;not null"`
	FileName        string `gorm:"size:255;not null"`
	FileType        string `gorm:"size:20;not null"`
	FileSize        int64  `gorm:"not null"`
	FilePath        string `gorm:"size:500;not null"`
	FileURL         string `gorm:"size:500"`
	Content         string `gorm:"type:text"`
	Summary         string `gorm:"type:text"`
	Status          string `gorm:"size:20;not null;index:idx_status"`
	ChunkCount      int    `gorm:"not null;default:0"`
	TenantID        string `gorm:"size:64;not null;index:idx_tenant"`
	UploadedBy      string `gorm:"size:64;not null"`
	Metadata        string `gorm:"type:jsonb"`
	ErrorMessage    string `gorm:"type:text"`
	ProcessedAt     *time.Time
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// TableName 表名
func (DocumentPO) TableName() string {
	return "knowledge.documents"
}

// DocumentRepository 文档仓储实现
type DocumentRepository struct {
	data *Data
	log  *log.Helper
}

// NewDocumentRepo 创建文档仓储
func NewDocumentRepo(data *Data, logger log.Logger) domain.DocumentRepository {
	return &DocumentRepository{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create 创建文档
func (r *DocumentRepository) Create(ctx context.Context, doc *domain.Document) error {
	po, err := r.toDocumentPO(doc)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		r.log.Errorf("failed to create document: %v", err)
		return err
	}

	return nil
}

// GetByID 根据ID获取文档
func (r *DocumentRepository) GetByID(ctx context.Context, id string) (*domain.Document, error) {
	var po DocumentPO
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrDocumentNotFound
		}
		r.log.Errorf("failed to get document: %v", err)
		return nil, err
	}

	return r.toDomainDocument(&po)
}

// Update 更新文档
func (r *DocumentRepository) Update(ctx context.Context, doc *domain.Document) error {
	po, err := r.toDocumentPO(doc)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).
		Model(&DocumentPO{}).
		Where("id = ?", doc.ID).
		Updates(po).Error; err != nil {
		r.log.Errorf("failed to update document: %v", err)
		return err
	}

	return nil
}

// Delete 删除文档
func (r *DocumentRepository) Delete(ctx context.Context, id string) error {
	if err := r.data.db.WithContext(ctx).Delete(&DocumentPO{}, "id = ?", id).Error; err != nil {
		r.log.Errorf("failed to delete document: %v", err)
		return err
	}

	return nil
}

// ListByKnowledgeBase 获取知识库的文档列表
func (r *DocumentRepository) ListByKnowledgeBase(
	ctx context.Context,
	kbID string,
	offset, limit int,
) ([]*domain.Document, int64, error) {
	var pos []DocumentPO
	var total int64

	// 查询总数
	if err := r.data.db.WithContext(ctx).
		Model(&DocumentPO{}).
		Where("knowledge_base_id = ? AND status != ?", kbID, domain.DocumentStatusDeleted).
		Count(&total).Error; err != nil {
		r.log.Errorf("failed to count documents: %v", err)
		return nil, 0, err
	}

	// 查询列表
	if err := r.data.db.WithContext(ctx).
		Where("knowledge_base_id = ? AND status != ?", kbID, domain.DocumentStatusDeleted).
		Order("created_at DESC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list documents: %v", err)
		return nil, 0, err
	}

	docs := make([]*domain.Document, 0, len(pos))
	for _, po := range pos {
		doc, err := r.toDomainDocument(&po)
		if err != nil {
			r.log.Warnf("failed to convert document: %v", err)
			continue
		}
		docs = append(docs, doc)
	}

	return docs, total, nil
}

// ListByStatus 根据状态获取文档列表
func (r *DocumentRepository) ListByStatus(
	ctx context.Context,
	status domain.DocumentStatus,
	offset, limit int,
) ([]*domain.Document, error) {
	var pos []DocumentPO

	if err := r.data.db.WithContext(ctx).
		Where("status = ?", status).
		Order("created_at DESC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list documents by status: %v", err)
		return nil, err
	}

	docs := make([]*domain.Document, 0, len(pos))
	for _, po := range pos {
		doc, err := r.toDomainDocument(&po)
		if err != nil {
			r.log.Warnf("failed to convert document: %v", err)
			continue
		}
		docs = append(docs, doc)
	}

	return docs, nil
}

// CountByKnowledgeBase 统计知识库的文档数量
func (r *DocumentRepository) CountByKnowledgeBase(ctx context.Context, kbID string) (int64, error) {
	var count int64
	if err := r.data.db.WithContext(ctx).
		Model(&DocumentPO{}).
		Where("knowledge_base_id = ? AND status != ?", kbID, domain.DocumentStatusDeleted).
		Count(&count).Error; err != nil {
		r.log.Errorf("failed to count documents: %v", err)
		return 0, err
	}

	return count, nil
}

// toDocumentPO 转换为持久化对象
func (r *DocumentRepository) toDocumentPO(doc *domain.Document) (*DocumentPO, error) {
	metadataJSON, _ := json.Marshal(doc.Metadata)

	return &DocumentPO{
		ID:              doc.ID,
		KnowledgeBaseID: doc.KnowledgeBaseID,
		Name:            doc.Name,
		FileName:        doc.FileName,
		FileType:        string(doc.FileType),
		FileSize:        doc.FileSize,
		FilePath:        doc.FilePath,
		FileURL:         doc.FileURL,
		Content:         doc.Content,
		Summary:         doc.Summary,
		Status:          string(doc.Status),
		ChunkCount:      doc.ChunkCount,
		TenantID:        doc.TenantID,
		UploadedBy:      doc.UploadedBy,
		Metadata:        string(metadataJSON),
		ErrorMessage:    doc.ErrorMessage,
		ProcessedAt:     doc.ProcessedAt,
		CreatedAt:       doc.CreatedAt,
		UpdatedAt:       doc.UpdatedAt,
	}, nil
}

// toDomainDocument 转换为领域对象
func (r *DocumentRepository) toDomainDocument(po *DocumentPO) (*domain.Document, error) {
	var metadata map[string]interface{}
	if po.Metadata != "" {
		json.Unmarshal([]byte(po.Metadata), &metadata)
	}

	return &domain.Document{
		ID:              po.ID,
		KnowledgeBaseID: po.KnowledgeBaseID,
		Name:            po.Name,
		FileName:        po.FileName,
		FileType:        domain.DocumentType(po.FileType),
		FileSize:        po.FileSize,
		FilePath:        po.FilePath,
		FileURL:         po.FileURL,
		Content:         po.Content,
		Summary:         po.Summary,
		Status:          domain.DocumentStatus(po.Status),
		ChunkCount:      po.ChunkCount,
		TenantID:        po.TenantID,
		UploadedBy:      po.UploadedBy,
		Metadata:        metadata,
		ErrorMessage:    po.ErrorMessage,
		ProcessedAt:     po.ProcessedAt,
		CreatedAt:       po.CreatedAt,
		UpdatedAt:       po.UpdatedAt,
	}, nil
}
