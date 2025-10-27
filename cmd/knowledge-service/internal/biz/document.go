package biz

import (
	"context"
	"fmt"
	"time"

	"voice-assistant/cmd/knowledge-service/internal/service"
)

// DocumentUseCase 文档用例
type DocumentUseCase struct {
	repo           DocumentRepo
	indexingClient *service.IndexingClient
}

// NewDocumentUseCase 创建文档用例
func NewDocumentUseCase(repo DocumentRepo, indexingClient *service.IndexingClient) *DocumentUseCase {
	return &DocumentUseCase{
		repo:           repo,
		indexingClient: indexingClient,
	}
}

// CreateAndIndexDocument 创建文档并触发索引
func (uc *DocumentUseCase) CreateAndIndexDocument(ctx context.Context, doc *Document) error {
	// 1. 创建文档记录（只存储元数据）
	doc.Status = "pending"
	doc.CreatedAt = time.Now()
	doc.UpdatedAt = time.Now()

	if err := uc.repo.Create(ctx, doc); err != nil {
		return fmt.Errorf("create document: %w", err)
	}

	// 2. 触发索引服务处理
	indexReq := &service.IndexDocumentRequest{
		DocumentID:      doc.ID,
		TenantID:        doc.TenantID,
		KnowledgeBaseID: doc.KnowledgeBaseID,
		Options: map[string]interface{}{
			"chunk_size":  512,
			"overlap":     50,
			"build_graph": false, // 知识图谱可选
		},
	}

	indexResp, err := uc.indexingClient.TriggerIndexing(ctx, indexReq)
	if err != nil {
		// 索引失败，更新文档状态
		doc.Status = "index_failed"
		doc.UpdatedAt = time.Now()
		_ = uc.repo.Update(ctx, doc)
		return fmt.Errorf("trigger indexing: %w", err)
	}

	// 3. 更新文档状态为处理中
	doc.Status = "indexing"
	doc.JobID = indexResp.JobID
	doc.UpdatedAt = time.Now()

	if err := uc.repo.Update(ctx, doc); err != nil {
		return fmt.Errorf("update document status: %w", err)
	}

	return nil
}

// GetDocumentWithIndexingStatus 获取文档及索引状态
func (uc *DocumentUseCase) GetDocumentWithIndexingStatus(ctx context.Context, id string) (*DocumentWithStatus, error) {
	// 1. 获取文档
	doc, err := uc.repo.GetByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("get document: %w", err)
	}

	result := &DocumentWithStatus{
		Document: doc,
	}

	// 2. 如果有索引任务，查询状态
	if doc.JobID != "" {
		status, err := uc.indexingClient.GetIndexingStatus(ctx, doc.JobID)
		if err != nil {
			// 查询失败不影响文档返回
			result.IndexingStatus = map[string]interface{}{
				"error": err.Error(),
			}
		} else {
			result.IndexingStatus = status
		}
	}

	return result, nil
}

// Document 文档领域模型
type Document struct {
	ID              string
	KnowledgeBaseID string
	TenantID        string
	Name            string
	FileName        string
	FileType        string
	FileSize        int64
	FilePath        string
	Status          string // pending, indexing, completed, failed
	JobID           string // 索引任务ID
	ChunkCount      int
	CreatedBy       string
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// DocumentWithStatus 文档及索引状态
type DocumentWithStatus struct {
	Document       *Document
	IndexingStatus map[string]interface{}
}

// DocumentRepo 文档仓储接口
type DocumentRepo interface {
	Create(ctx context.Context, doc *Document) error
	Update(ctx context.Context, doc *Document) error
	GetByID(ctx context.Context, id string) (*Document, error)
	List(ctx context.Context, kbID string, limit, offset int) ([]*Document, error)
	Delete(ctx context.Context, id string) error
}
