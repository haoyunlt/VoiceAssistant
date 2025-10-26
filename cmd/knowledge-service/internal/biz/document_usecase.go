package biz

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/voicehelper/voiceassistant/cmd/knowledge-service/internal/domain"
)

// DocumentUsecase 文档用例
type DocumentUsecase struct {
	docRepo   domain.DocumentRepository
	chunkRepo domain.ChunkRepository
	kbRepo    domain.KnowledgeBaseRepository
	log       *log.Helper
}

// NewDocumentUsecase 创建文档用例
func NewDocumentUsecase(
	docRepo domain.DocumentRepository,
	chunkRepo domain.ChunkRepository,
	kbRepo domain.KnowledgeBaseRepository,
	logger log.Logger,
) *DocumentUsecase {
	return &DocumentUsecase{
		docRepo:   docRepo,
		chunkRepo: chunkRepo,
		kbRepo:    kbRepo,
		log:       log.NewHelper(logger),
	}
}

// UploadDocument 上传文档
func (uc *DocumentUsecase) UploadDocument(
	ctx context.Context,
	knowledgeBaseID string,
	name, fileName string,
	fileType domain.DocumentType,
	fileSize int64,
	filePath string,
	tenantID, uploadedBy string,
) (*domain.Document, error) {
	// 检查知识库是否存在且激活
	kb, err := uc.kbRepo.GetByID(ctx, knowledgeBaseID)
	if err != nil {
		return nil, err
	}
	if !kb.IsActive() {
		return nil, fmt.Errorf("knowledge base is not active")
	}

	// 创建文档
	doc := domain.NewDocument(
		knowledgeBaseID,
		name,
		fileName,
		fileType,
		fileSize,
		filePath,
		tenantID,
		uploadedBy,
	)

	// 验证
	if err := doc.Validate(); err != nil {
		uc.log.WithContext(ctx).Errorf("invalid document: %v", err)
		return nil, err
	}

	// 持久化
	if err := uc.docRepo.Create(ctx, doc); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create document: %v", err)
		return nil, err
	}

	// 更新知识库统计
	kb.IncrementDocumentCount(1)
	kb.AddSize(fileSize)
	uc.kbRepo.Update(ctx, kb)

	uc.log.WithContext(ctx).Infof("uploaded document: %s, name: %s", doc.ID, doc.Name)
	return doc, nil
}

// GetDocument 获取文档
func (uc *DocumentUsecase) GetDocument(ctx context.Context, id string) (*domain.Document, error) {
	doc, err := uc.docRepo.GetByID(ctx, id)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get document %s: %v", id, err)
		return nil, err
	}
	return doc, nil
}

// UpdateDocument 更新文档
func (uc *DocumentUsecase) UpdateDocument(
	ctx context.Context,
	id, name string,
	metadata map[string]interface{},
) (*domain.Document, error) {
	doc, err := uc.docRepo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	doc.Update(name, metadata)

	if err := uc.docRepo.Update(ctx, doc); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update document: %v", err)
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("updated document: %s", doc.ID)
	return doc, nil
}

// DeleteDocument 删除文档
func (uc *DocumentUsecase) DeleteDocument(ctx context.Context, id string) error {
	doc, err := uc.docRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	// 删除所有分块
	if err := uc.chunkRepo.DeleteByDocument(ctx, id); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to delete chunks: %v", err)
		return err
	}

	// 标记文档为已删除
	doc.MarkDeleted()
	if err := uc.docRepo.Update(ctx, doc); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to mark document as deleted: %v", err)
		return err
	}

	// 更新知识库统计
	kb, err := uc.kbRepo.GetByID(ctx, doc.KnowledgeBaseID)
	if err == nil {
		kb.IncrementDocumentCount(-1)
		kb.IncrementChunkCount(-doc.ChunkCount)
		kb.AddSize(-doc.FileSize)
		uc.kbRepo.Update(ctx, kb)
	}

	uc.log.WithContext(ctx).Infof("deleted document: %s", doc.ID)
	return nil
}

// ListDocuments 列出知识库的文档
func (uc *DocumentUsecase) ListDocuments(
	ctx context.Context,
	knowledgeBaseID string,
	offset, limit int,
) ([]*domain.Document, int64, error) {
	docs, total, err := uc.docRepo.ListByKnowledgeBase(ctx, knowledgeBaseID, offset, limit)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to list documents: %v", err)
		return nil, 0, err
	}
	return docs, total, nil
}

// ProcessDocument 处理文档（提取内容和分块）
func (uc *DocumentUsecase) ProcessDocument(ctx context.Context, id string, content string) error {
	doc, err := uc.docRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	if !doc.CanProcess() {
		return fmt.Errorf("document cannot be processed")
	}

	// 开始处理
	doc.StartProcessing()
	if err := uc.docRepo.Update(ctx, doc); err != nil {
		return err
	}

	// 设置内容
	doc.SetContent(content)

	// 获取知识库配置
	kb, err := uc.kbRepo.GetByID(ctx, doc.KnowledgeBaseID)
	if err != nil {
		doc.FailProcessing(err.Error())
		uc.docRepo.Update(ctx, doc)
		return err
	}

	// 分块处理
	chunks, err := uc.chunkDocument(doc, kb, content)
	if err != nil {
		doc.FailProcessing(err.Error())
		uc.docRepo.Update(ctx, doc)
		uc.log.WithContext(ctx).Errorf("failed to chunk document: %v", err)
		return err
	}

	// 保存分块
	if err := uc.chunkRepo.BatchCreate(ctx, chunks); err != nil {
		doc.FailProcessing(err.Error())
		uc.docRepo.Update(ctx, doc)
		uc.log.WithContext(ctx).Errorf("failed to save chunks: %v", err)
		return err
	}

	// 完成处理
	doc.CompleteProcessing(len(chunks))
	if err := uc.docRepo.Update(ctx, doc); err != nil {
		return err
	}

	// 更新知识库统计
	kb.IncrementChunkCount(len(chunks))
	kb.UpdateLastIndexedAt()
	uc.kbRepo.Update(ctx, kb)

	uc.log.WithContext(ctx).Infof("processed document: %s, chunks: %d", doc.ID, len(chunks))
	return nil
}

// chunkDocument 分块文档
func (uc *DocumentUsecase) chunkDocument(
	doc *domain.Document,
	kb *domain.KnowledgeBase,
	content string,
) ([]*domain.Chunk, error) {
	chunkSize := kb.ChunkSize
	chunkOverlap := kb.ChunkOverlap

	// 简单的固定大小分块（实际应该使用更智能的分块策略）
	chunks := make([]*domain.Chunk, 0)
	runes := []rune(content)
	position := 0

	for i := 0; i < len(runes); i += (chunkSize - chunkOverlap) {
		end := i + chunkSize
		if end > len(runes) {
			end = len(runes)
		}

		chunkContent := string(runes[i:end])
		if len(strings.TrimSpace(chunkContent)) == 0 {
			continue
		}

		chunk := domain.NewChunk(
			doc.ID,
			doc.KnowledgeBaseID,
			chunkContent,
			position,
			doc.TenantID,
		)

		// 设置内容哈希
		hash := sha256.Sum256([]byte(chunkContent))
		chunk.SetContentHash(hex.EncodeToString(hash[:]))

		// 添加元数据
		chunk.AddMetadata("document_name", doc.Name)
		chunk.AddMetadata("file_type", doc.FileType)

		chunks = append(chunks, chunk)
		position++

		if end >= len(runes) {
			break
		}
	}

	return chunks, nil
}

// GetDocumentChunks 获取文档的分块
func (uc *DocumentUsecase) GetDocumentChunks(
	ctx context.Context,
	documentID string,
	offset, limit int,
) ([]*domain.Chunk, error) {
	chunks, err := uc.chunkRepo.ListByDocument(ctx, documentID, offset, limit)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get document chunks: %v", err)
		return nil, err
	}
	return chunks, nil
}

// ReprocessDocument 重新处理文档
func (uc *DocumentUsecase) ReprocessDocument(ctx context.Context, id string) error {
	doc, err := uc.docRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	// 删除旧的分块
	if err := uc.chunkRepo.DeleteByDocument(ctx, id); err != nil {
		return err
	}

	// 重新处理
	return uc.ProcessDocument(ctx, id, doc.Content)
}
