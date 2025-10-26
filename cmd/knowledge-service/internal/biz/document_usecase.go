package biz

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"voiceassistant/cmd/knowledge-service/internal/domain"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/event"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/security"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/storage"
)

// DocumentRepository 文档仓储接口
type DocumentRepository interface {
	Create(ctx context.Context, doc *domain.Document) error
	Update(ctx context.Context, doc *domain.Document) error
	Delete(ctx context.Context, id string) error
	FindByID(ctx context.Context, id string) (*domain.Document, error)
	FindByKnowledgeBaseID(ctx context.Context, kbID string, limit, offset int) ([]*domain.Document, error)
	CountByKnowledgeBaseID(ctx context.Context, kbID string) (int64, error)
}

// DocumentUsecase 文档用例
type DocumentUsecase struct {
	repo           DocumentRepository
	storageClient  *storage.MinIOClient
	virusScanner   security.VirusScanner
	eventPublisher *event.EventPublisher
}

// NewDocumentUsecase 创建文档用例
func NewDocumentUsecase(
	repo DocumentRepository,
	storageClient *storage.MinIOClient,
	virusScanner security.VirusScanner,
	eventPublisher *event.EventPublisher,
) *DocumentUsecase {
	return &DocumentUsecase{
		repo:           repo,
		storageClient:  storageClient,
		virusScanner:   virusScanner,
		eventPublisher: eventPublisher,
	}
}

// UploadDocumentInput 上传文档输入
type UploadDocumentInput struct {
	KnowledgeBaseID string
	TenantID        string
	UserID          string
	Filename        string
	ContentType     string
	FileReader      io.Reader
	FileSize        int64
	Metadata        map[string]string
}

// UploadDocument 上传文档
func (uc *DocumentUsecase) UploadDocument(ctx context.Context, input *UploadDocumentInput) (*domain.Document, error) {
	// 1. 验证文件类型
	if !isAllowedFileType(input.Filename) {
		return nil, fmt.Errorf("file type not allowed: %s", filepath.Ext(input.Filename))
	}

	// 2. 验证文件大小 (最大100MB)
	const maxFileSize = 100 * 1024 * 1024
	if input.FileSize > maxFileSize {
		return nil, fmt.Errorf("file size exceeds limit: %d bytes (max: %d)", input.FileSize, maxFileSize)
	}

	// 3. 读取文件内容到缓冲区 (用于病毒扫描和上传)
	buf := &bytes.Buffer{}
	teeReader := io.TeeReader(input.FileReader, buf)
	fileContent, err := io.ReadAll(teeReader)
	if err != nil {
		return nil, fmt.Errorf("failed to read file content: %w", err)
	}

	// 4. 病毒扫描
	scanResult, err := uc.virusScanner.Scan(ctx, bytes.NewReader(fileContent))
	if err != nil {
		return nil, fmt.Errorf("virus scan failed: %w", err)
	}

	if !scanResult.IsClean {
		return nil, fmt.Errorf("file contains threat: %s", scanResult.Threat)
	}

	// 5. 生成存储路径
	documentID := uuid.New().String()
	storagePath := generateStoragePath(input.TenantID, input.KnowledgeBaseID, documentID, input.Filename)

	// 6. 上传到MinIO
	err = uc.storageClient.UploadFile(
		ctx,
		storagePath,
		bytes.NewReader(fileContent),
		input.FileSize,
		input.ContentType,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to upload file to storage: %w", err)
	}

	// 7. 创建文档记录
	doc := &domain.Document{
		ID:              documentID,
		KnowledgeBaseID: input.KnowledgeBaseID,
		TenantID:        input.TenantID,
		UserID:          input.UserID,
		Filename:        input.Filename,
		FileSize:        input.FileSize,
		ContentType:     input.ContentType,
		StoragePath:     storagePath,
		Status:          domain.DocumentStatusPending,
		Version:         1,
		Metadata:        input.Metadata,
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
	}

	if err := uc.repo.Create(ctx, doc); err != nil {
		// 如果数据库保存失败，删除已上传的文件
		_ = uc.storageClient.DeleteFile(ctx, storagePath)
		return nil, fmt.Errorf("failed to create document record: %w", err)
	}

	// 8. 发布文档上传事件 (Indexing Service会监听此事件)
	err = uc.eventPublisher.PublishDocumentUploaded(ctx, &event.DocumentUploadedEvent{
		DocumentID:      doc.ID,
		TenantID:        doc.TenantID,
		UserID:          doc.UserID,
		KnowledgeBaseID: doc.KnowledgeBaseID,
		Filename:        doc.Filename,
		FileSize:        doc.FileSize,
		ContentType:     doc.ContentType,
		StoragePath:     doc.StoragePath,
		Metadata:        doc.Metadata,
	})
	if err != nil {
		// 事件发布失败不阻塞主流程，但记录错误
		// TODO: 实现事件补偿机制
		return doc, fmt.Errorf("document uploaded but event publish failed: %w", err)
	}

	return doc, nil
}

// GetDocument 获取文档
func (uc *DocumentUsecase) GetDocument(ctx context.Context, id string) (*domain.Document, error) {
	doc, err := uc.repo.FindByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("failed to find document: %w", err)
	}

	return doc, nil
}

// DownloadDocument 下载文档
func (uc *DocumentUsecase) DownloadDocument(ctx context.Context, id string) (io.ReadCloser, *domain.Document, error) {
	// 1. 获取文档信息
	doc, err := uc.repo.FindByID(ctx, id)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to find document: %w", err)
	}

	// 2. 从MinIO下载文件
	reader, err := uc.storageClient.DownloadFile(ctx, doc.StoragePath)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to download file: %w", err)
	}

	return reader, doc, nil
}

// GetDownloadURL 获取下载URL
func (uc *DocumentUsecase) GetDownloadURL(ctx context.Context, id string, expires time.Duration) (string, error) {
	// 1. 获取文档信息
	doc, err := uc.repo.FindByID(ctx, id)
	if err != nil {
		return "", fmt.Errorf("failed to find document: %w", err)
	}

	// 2. 生成预签名URL
	url, err := uc.storageClient.GetPresignedURL(ctx, doc.StoragePath, expires)
	if err != nil {
		return "", fmt.Errorf("failed to generate presigned url: %w", err)
	}

	return url, nil
}

// DeleteDocument 删除文档
func (uc *DocumentUsecase) DeleteDocument(ctx context.Context, id string) error {
	// 1. 获取文档信息
	doc, err := uc.repo.FindByID(ctx, id)
	if err != nil {
		return fmt.Errorf("failed to find document: %w", err)
	}

	// 2. 从MinIO删除文件
	if err := uc.storageClient.DeleteFile(ctx, doc.StoragePath); err != nil {
		// 存储删除失败不阻塞，继续删除数据库记录
		// TODO: 实现清理任务
	}

	// 3. 删除数据库记录
	if err := uc.repo.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete document record: %w", err)
	}

	// 4. 发布文档删除事件
	err = uc.eventPublisher.PublishDocumentDeleted(ctx, &event.DocumentDeletedEvent{
		DocumentID:      doc.ID,
		TenantID:        doc.TenantID,
		UserID:          doc.UserID,
		KnowledgeBaseID: doc.KnowledgeBaseID,
		Filename:        doc.Filename,
		StoragePath:     doc.StoragePath,
		Metadata:        doc.Metadata,
	})
	if err != nil {
		// 事件发布失败不阻塞
		// TODO: 实现事件补偿机制
	}

	return nil
}

// ListDocuments 列出文档
func (uc *DocumentUsecase) ListDocuments(ctx context.Context, knowledgeBaseID string, page, pageSize int) ([]*domain.Document, int64, error) {
	offset := (page - 1) * pageSize

	docs, err := uc.repo.FindByKnowledgeBaseID(ctx, knowledgeBaseID, pageSize, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list documents: %w", err)
	}

	total, err := uc.repo.CountByKnowledgeBaseID(ctx, knowledgeBaseID)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count documents: %w", err)
	}

	return docs, total, nil
}

// UpdateDocumentStatus 更新文档状态
func (uc *DocumentUsecase) UpdateDocumentStatus(ctx context.Context, id string, status domain.DocumentStatus) error {
	doc, err := uc.repo.FindByID(ctx, id)
	if err != nil {
		return fmt.Errorf("failed to find document: %w", err)
	}

	doc.Status = status
	doc.UpdatedAt = time.Now()

	if err := uc.repo.Update(ctx, doc); err != nil {
		return fmt.Errorf("failed to update document status: %w", err)
	}

	return nil
}

// generateStoragePath 生成存储路径
func generateStoragePath(tenantID, knowledgeBaseID, documentID, filename string) string {
	ext := filepath.Ext(filename)
	return fmt.Sprintf("%s/%s/%s%s", tenantID, knowledgeBaseID, documentID, ext)
}

// isAllowedFileType 检查文件类型是否允许
func isAllowedFileType(filename string) bool {
	allowedExtensions := map[string]bool{
		".pdf":  true,
		".doc":  true,
		".docx": true,
		".txt":  true,
		".md":   true,
		".html": true,
		".htm":  true,
		".xlsx": true,
		".xls":  true,
		".pptx": true,
		".ppt":  true,
		".csv":  true,
		".json": true,
		".xml":  true,
	}

	ext := filepath.Ext(filename)
	return allowedExtensions[ext]
}
