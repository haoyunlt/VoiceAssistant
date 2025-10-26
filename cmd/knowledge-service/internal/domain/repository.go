package domain

import (
	"context"
)

// KnowledgeBaseRepository 知识库仓储接口
type KnowledgeBaseRepository interface {
	// Create 创建知识库
	Create(ctx context.Context, kb *KnowledgeBase) error

	// GetByID 根据ID获取知识库
	GetByID(ctx context.Context, id string) (*KnowledgeBase, error)

	// Update 更新知识库
	Update(ctx context.Context, kb *KnowledgeBase) error

	// Delete 删除知识库
	Delete(ctx context.Context, id string) error

	// ListByTenant 获取租户的知识库列表
	ListByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*KnowledgeBase, int64, error)

	// ListByStatus 根据状态获取知识库列表
	ListByStatus(ctx context.Context, status KnowledgeBaseStatus, offset, limit int) ([]*KnowledgeBase, error)
}

// DocumentRepository 文档仓储接口
type DocumentRepository interface {
	// Create 创建文档
	Create(ctx context.Context, doc *Document) error

	// GetByID 根据ID获取文档
	GetByID(ctx context.Context, id string) (*Document, error)

	// Update 更新文档
	Update(ctx context.Context, doc *Document) error

	// Delete 删除文档
	Delete(ctx context.Context, id string) error

	// ListByKnowledgeBase 获取知识库的文档列表
	ListByKnowledgeBase(ctx context.Context, kbID string, offset, limit int) ([]*Document, int64, error)

	// ListByStatus 根据状态获取文档列表
	ListByStatus(ctx context.Context, status DocumentStatus, offset, limit int) ([]*Document, error)

	// CountByKnowledgeBase 统计知识库的文档数量
	CountByKnowledgeBase(ctx context.Context, kbID string) (int64, error)
}

// ChunkRepository 分块仓储接口
type ChunkRepository interface {
	// Create 创建分块
	Create(ctx context.Context, chunk *Chunk) error

	// BatchCreate 批量创建分块
	BatchCreate(ctx context.Context, chunks []*Chunk) error

	// GetByID 根据ID获取分块
	GetByID(ctx context.Context, id string) (*Chunk, error)

	// Update 更新分块
	Update(ctx context.Context, chunk *Chunk) error

	// Delete 删除分块
	Delete(ctx context.Context, id string) error

	// ListByDocument 获取文档的分块列表
	ListByDocument(ctx context.Context, documentID string, offset, limit int) ([]*Chunk, error)

	// ListByKnowledgeBase 获取知识库的分块列表
	ListByKnowledgeBase(ctx context.Context, kbID string, offset, limit int) ([]*Chunk, error)

	// DeleteByDocument 删除文档的所有分块
	DeleteByDocument(ctx context.Context, documentID string) error

	// CountByDocument 统计文档的分块数量
	CountByDocument(ctx context.Context, documentID string) (int64, error)

	// CountByKnowledgeBase 统计知识库的分块数量
	CountByKnowledgeBase(ctx context.Context, kbID string) (int64, error)

	// ListPendingEmbedding 获取待向量化的分块
	ListPendingEmbedding(ctx context.Context, limit int) ([]*Chunk, error)
}
