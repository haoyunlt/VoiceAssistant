package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/lib/pq"
	"voiceassistant/cmd/knowledge-service/internal/domain"
	"gorm.io/gorm"
)

// ChunkPO 分块持久化对象
type ChunkPO struct {
	ID              string          `gorm:"primaryKey;size:64"`
	DocumentID      string          `gorm:"size:64;not null;index:idx_document"`
	KnowledgeBaseID string          `gorm:"size:64;not null;index:idx_knowledge_base"`
	Content         string          `gorm:"type:text;not null"`
	ContentHash     string          `gorm:"size:64;index:idx_content_hash"`
	Position        int             `gorm:"not null"`
	TokenCount      int             `gorm:"not null"`
	CharCount       int             `gorm:"not null"`
	Metadata        string          `gorm:"type:jsonb"`
	Embedding       pq.Float32Array `gorm:"type:float4[]"` // PostgreSQL数组类型存储向量
	EmbeddingStatus string          `gorm:"size:20;not null;index:idx_embedding_status"`
	TenantID        string          `gorm:"size:64;not null;index:idx_tenant"`
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// TableName 表名
func (ChunkPO) TableName() string {
	return "knowledge.chunks"
}

// ChunkRepository 分块仓储实现
type ChunkRepository struct {
	data *Data
	log  *log.Helper
}

// NewChunkRepo 创建分块仓储
func NewChunkRepo(data *Data, logger log.Logger) domain.ChunkRepository {
	return &ChunkRepository{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create 创建分块
func (r *ChunkRepository) Create(ctx context.Context, chunk *domain.Chunk) error {
	po, err := r.toChunkPO(chunk)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		r.log.Errorf("failed to create chunk: %v", err)
		return err
	}

	return nil
}

// BatchCreate 批量创建分块
func (r *ChunkRepository) BatchCreate(ctx context.Context, chunks []*domain.Chunk) error {
	if len(chunks) == 0 {
		return nil
	}

	pos := make([]ChunkPO, len(chunks))
	for i, chunk := range chunks {
		po, err := r.toChunkPO(chunk)
		if err != nil {
			return err
		}
		pos[i] = *po
	}

	// 批量插入
	if err := r.data.db.WithContext(ctx).CreateInBatches(pos, 100).Error; err != nil {
		r.log.Errorf("failed to batch create chunks: %v", err)
		return err
	}

	return nil
}

// GetByID 根据ID获取分块
func (r *ChunkRepository) GetByID(ctx context.Context, id string) (*domain.Chunk, error) {
	var po ChunkPO
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrChunkNotFound
		}
		r.log.Errorf("failed to get chunk: %v", err)
		return nil, err
	}

	return r.toDomainChunk(&po)
}

// Update 更新分块
func (r *ChunkRepository) Update(ctx context.Context, chunk *domain.Chunk) error {
	po, err := r.toChunkPO(chunk)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).
		Model(&ChunkPO{}).
		Where("id = ?", chunk.ID).
		Updates(po).Error; err != nil {
		r.log.Errorf("failed to update chunk: %v", err)
		return err
	}

	return nil
}

// Delete 删除分块
func (r *ChunkRepository) Delete(ctx context.Context, id string) error {
	if err := r.data.db.WithContext(ctx).Delete(&ChunkPO{}, "id = ?", id).Error; err != nil {
		r.log.Errorf("failed to delete chunk: %v", err)
		return err
	}

	return nil
}

// ListByDocument 获取文档的分块列表
func (r *ChunkRepository) ListByDocument(
	ctx context.Context,
	documentID string,
	offset, limit int,
) ([]*domain.Chunk, error) {
	var pos []ChunkPO

	if err := r.data.db.WithContext(ctx).
		Where("document_id = ?", documentID).
		Order("position ASC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list chunks by document: %v", err)
		return nil, err
	}

	chunks := make([]*domain.Chunk, 0, len(pos))
	for _, po := range pos {
		chunk, err := r.toDomainChunk(&po)
		if err != nil {
			r.log.Warnf("failed to convert chunk: %v", err)
			continue
		}
		chunks = append(chunks, chunk)
	}

	return chunks, nil
}

// ListByKnowledgeBase 获取知识库的分块列表
func (r *ChunkRepository) ListByKnowledgeBase(
	ctx context.Context,
	kbID string,
	offset, limit int,
) ([]*domain.Chunk, error) {
	var pos []ChunkPO

	if err := r.data.db.WithContext(ctx).
		Where("knowledge_base_id = ?", kbID).
		Order("created_at DESC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list chunks by knowledge base: %v", err)
		return nil, err
	}

	chunks := make([]*domain.Chunk, 0, len(pos))
	for _, po := range pos {
		chunk, err := r.toDomainChunk(&po)
		if err != nil {
			r.log.Warnf("failed to convert chunk: %v", err)
			continue
		}
		chunks = append(chunks, chunk)
	}

	return chunks, nil
}

// DeleteByDocument 删除文档的所有分块
func (r *ChunkRepository) DeleteByDocument(ctx context.Context, documentID string) error {
	if err := r.data.db.WithContext(ctx).
		Where("document_id = ?", documentID).
		Delete(&ChunkPO{}).Error; err != nil {
		r.log.Errorf("failed to delete chunks by document: %v", err)
		return err
	}

	return nil
}

// CountByDocument 统计文档的分块数量
func (r *ChunkRepository) CountByDocument(ctx context.Context, documentID string) (int64, error) {
	var count int64
	if err := r.data.db.WithContext(ctx).
		Model(&ChunkPO{}).
		Where("document_id = ?", documentID).
		Count(&count).Error; err != nil {
		r.log.Errorf("failed to count chunks: %v", err)
		return 0, err
	}

	return count, nil
}

// CountByKnowledgeBase 统计知识库的分块数量
func (r *ChunkRepository) CountByKnowledgeBase(ctx context.Context, kbID string) (int64, error) {
	var count int64
	if err := r.data.db.WithContext(ctx).
		Model(&ChunkPO{}).
		Where("knowledge_base_id = ?", kbID).
		Count(&count).Error; err != nil {
		r.log.Errorf("failed to count chunks: %v", err)
		return 0, err
	}

	return count, nil
}

// ListPendingEmbedding 获取待向量化的分块
func (r *ChunkRepository) ListPendingEmbedding(ctx context.Context, limit int) ([]*domain.Chunk, error) {
	var pos []ChunkPO

	if err := r.data.db.WithContext(ctx).
		Where("embedding_status = ?", "pending").
		Order("created_at ASC").
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list pending embedding chunks: %v", err)
		return nil, err
	}

	chunks := make([]*domain.Chunk, 0, len(pos))
	for _, po := range pos {
		chunk, err := r.toDomainChunk(&po)
		if err != nil {
			r.log.Warnf("failed to convert chunk: %v", err)
			continue
		}
		chunks = append(chunks, chunk)
	}

	return chunks, nil
}

// toChunkPO 转换为持久化对象
func (r *ChunkRepository) toChunkPO(chunk *domain.Chunk) (*ChunkPO, error) {
	metadataJSON, _ := json.Marshal(chunk.Metadata)

	// 转换embedding为PostgreSQL数组
	var embedding pq.Float32Array
	if len(chunk.Embedding) > 0 {
		embedding = pq.Float32Array(chunk.Embedding)
	}

	return &ChunkPO{
		ID:              chunk.ID,
		DocumentID:      chunk.DocumentID,
		KnowledgeBaseID: chunk.KnowledgeBaseID,
		Content:         chunk.Content,
		ContentHash:     chunk.ContentHash,
		Position:        chunk.Position,
		TokenCount:      chunk.TokenCount,
		CharCount:       chunk.CharCount,
		Metadata:        string(metadataJSON),
		Embedding:       embedding,
		EmbeddingStatus: chunk.EmbeddingStatus,
		TenantID:        chunk.TenantID,
		CreatedAt:       chunk.CreatedAt,
		UpdatedAt:       chunk.UpdatedAt,
	}, nil
}

// toDomainChunk 转换为领域对象
func (r *ChunkRepository) toDomainChunk(po *ChunkPO) (*domain.Chunk, error) {
	var metadata map[string]interface{}
	if po.Metadata != "" {
		json.Unmarshal([]byte(po.Metadata), &metadata)
	}

	// 转换embedding
	var embedding []float32
	if len(po.Embedding) > 0 {
		embedding = []float32(po.Embedding)
	}

	return &domain.Chunk{
		ID:              po.ID,
		DocumentID:      po.DocumentID,
		KnowledgeBaseID: po.KnowledgeBaseID,
		Content:         po.Content,
		ContentHash:     po.ContentHash,
		Position:        po.Position,
		TokenCount:      po.TokenCount,
		CharCount:       po.CharCount,
		Metadata:        metadata,
		Embedding:       embedding,
		EmbeddingStatus: po.EmbeddingStatus,
		TenantID:        po.TenantID,
		CreatedAt:       po.CreatedAt,
		UpdatedAt:       po.UpdatedAt,
	}, nil
}
