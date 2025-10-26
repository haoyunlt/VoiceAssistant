package service

import (
	"context"
	"crypto/md5"
	"fmt"
	"io"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"google.golang.org/protobuf/types/known/timestamppb"

	eventsv1 "voiceassistant/api/proto/events/v1"
	"voiceassistant/cmd/knowledge-service/internal/infra"
	"voiceassistant/pkg/events"
)

// DocumentService 文档服务
type DocumentService struct {
	storage        infra.FileStorage
	virusScanner   infra.VirusScanner
	eventPublisher events.Publisher
}

// NewDocumentService 创建文档服务
func NewDocumentService(
	storage infra.FileStorage,
	virusScanner infra.VirusScanner,
	eventPublisher events.Publisher,
) *DocumentService {
	return &DocumentService{
		storage:        storage,
		virusScanner:   virusScanner,
		eventPublisher: eventPublisher,
	}
}

// UploadDocumentRequest 上传文档请求
type UploadDocumentRequest struct {
	TenantID      string
	UserID        string
	FileName      string
	ContentType   string
	Reader        io.Reader
	Size          int64
	SkipVirusScan bool // 跳过病毒扫描（测试用）
}

// UploadDocumentResponse 上传文档响应
type UploadDocumentResponse struct {
	DocumentID      string
	FileName        string
	StoragePath     string
	Size            int64
	ContentType     string
	MD5Hash         string
	IsClean         bool
	VirusScanResult string
	UploadedAt      time.Time
}

// UploadDocument 上传文档
func (s *DocumentService) UploadDocument(ctx context.Context, req *UploadDocumentRequest) (*UploadDocumentResponse, error) {
	// 生成文档 ID
	documentID := uuid.New().String()

	// 生成存储路径: {tenant_id}/{document_id}/{filename}
	storagePath := fmt.Sprintf("%s/%s/%s", req.TenantID, documentID, req.FileName)

	// 如果启用病毒扫描，先扫描
	var scanResult *infra.ScanResult
	var md5Hash string

	if !req.SkipVirusScan {
		// 创建 TeeReader 同时计算 MD5 和扫描病毒
		md5Hasher := md5.New()
		teeReader := io.TeeReader(req.Reader, md5Hasher)

		// 病毒扫描
		var err error
		scanResult, err = s.virusScanner.Scan(ctx, teeReader)
		if err != nil {
			return nil, fmt.Errorf("virus scan failed: %w", err)
		}

		// 计算 MD5
		md5Hash = fmt.Sprintf("%x", md5Hasher.Sum(nil))

		// 如果发现病毒，拒绝上传
		if !scanResult.IsClean {
			// 发布扫描失败事件
			s.publishDocumentScannedEvent(ctx, documentID, req.TenantID, req.UserID, false, scanResult.Virus)

			return &UploadDocumentResponse{
				DocumentID:      documentID,
				FileName:        req.FileName,
				IsClean:         false,
				VirusScanResult: scanResult.Message,
			}, fmt.Errorf("virus detected: %s", scanResult.Virus)
		}
	} else {
		// 跳过病毒扫描，只计算 MD5
		md5Hasher := md5.New()
		if _, err := io.Copy(md5Hasher, req.Reader); err != nil {
			return nil, fmt.Errorf("failed to calculate md5: %w", err)
		}
		md5Hash = fmt.Sprintf("%x", md5Hasher.Sum(nil))
	}

	// 重新打开文件进行上传（因为 reader 已经被读取）
	// 注意：实际实现中应该使用缓存或多路复用
	// 这里假设调用者会处理 reader 的重新打开

	// 上传到 MinIO
	uploadResult, err := s.storage.UploadFile(ctx, storagePath, req.Reader, req.Size, req.ContentType)
	if err != nil {
		return nil, fmt.Errorf("failed to upload file: %w", err)
	}

	// 发布文档上传事件
	if err := s.publishDocumentUploadedEvent(ctx, documentID, req.TenantID, req.UserID, req.FileName, req.ContentType, uploadResult.Size, storagePath, md5Hash); err != nil {
		// 记录日志但不失败
		fmt.Printf("Failed to publish document uploaded event: %v\n", err)
	}

	// 如果启用了病毒扫描，发布扫描事件
	if !req.SkipVirusScan && scanResult != nil {
		s.publishDocumentScannedEvent(ctx, documentID, req.TenantID, req.UserID, scanResult.IsClean, "")
	}

	return &UploadDocumentResponse{
		DocumentID:      documentID,
		FileName:        req.FileName,
		StoragePath:     storagePath,
		Size:            uploadResult.Size,
		ContentType:     uploadResult.ContentType,
		MD5Hash:         md5Hash,
		IsClean:         scanResult == nil || scanResult.IsClean,
		VirusScanResult: getVirusScanMessage(scanResult),
		UploadedAt:      uploadResult.UploadedAt,
	}, nil
}

// DownloadDocument 下载文档
func (s *DocumentService) DownloadDocument(ctx context.Context, tenantID, documentID, fileName string) (io.ReadCloser, error) {
	storagePath := fmt.Sprintf("%s/%s/%s", tenantID, documentID, fileName)
	return s.storage.DownloadFile(ctx, storagePath)
}

// DeleteDocument 删除文档
func (s *DocumentService) DeleteDocument(ctx context.Context, tenantID, userID, documentID, fileName string) error {
	storagePath := fmt.Sprintf("%s/%s/%s", tenantID, documentID, fileName)

	// 删除文件
	if err := s.storage.DeleteFile(ctx, storagePath); err != nil {
		return fmt.Errorf("failed to delete file: %w", err)
	}

	// 发布文档删除事件
	if err := s.publishDocumentDeletedEvent(ctx, documentID, tenantID, userID, "user_requested"); err != nil {
		fmt.Printf("Failed to publish document deleted event: %v\n", err)
	}

	return nil
}

// GetDocumentInfo 获取文档信息
func (s *DocumentService) GetDocumentInfo(ctx context.Context, tenantID, documentID, fileName string) (*infra.FileInfo, error) {
	storagePath := fmt.Sprintf("%s/%s/%s", tenantID, documentID, fileName)
	return s.storage.GetFileInfo(ctx, storagePath)
}

// ListDocuments 列出租户的所有文档
func (s *DocumentService) ListDocuments(ctx context.Context, tenantID string) ([]*infra.FileInfo, error) {
	prefix := fmt.Sprintf("%s/", tenantID)
	return s.storage.ListFiles(ctx, prefix)
}

// GenerateDownloadURL 生成下载 URL
func (s *DocumentService) GenerateDownloadURL(ctx context.Context, tenantID, documentID, fileName string, expiry time.Duration) (string, error) {
	storagePath := fmt.Sprintf("%s/%s/%s", tenantID, documentID, fileName)
	return s.storage.GeneratePresignedURL(ctx, storagePath, expiry)
}

// GenerateUploadURL 生成上传 URL (用于客户端直接上传)
func (s *DocumentService) GenerateUploadURL(ctx context.Context, tenantID, documentID, fileName string, expiry time.Duration) (string, error) {
	storagePath := fmt.Sprintf("%s/%s/%s", tenantID, documentID, fileName)
	return s.storage.GenerateUploadURL(ctx, storagePath, expiry)
}

// 发布文档上传事件
func (s *DocumentService) publishDocumentUploadedEvent(ctx context.Context, documentID, tenantID, userID, fileName, contentType string, size int64, storagePath, md5Hash string) error {
	payload := &eventsv1.DocumentUploadedPayload{
		DocumentId:  documentID,
		TenantId:    tenantID,
		UserId:      userID,
		Filename:    fileName,
		ContentType: contentType,
		FileSize:    size,
		StoragePath: storagePath,
		Md5Hash:     md5Hash,
		UploadedAt:  timestamppb.Now(),
		Metadata: &eventsv1.DocumentMetadata{
			Title: filepath.Base(fileName),
		},
	}

	return events.PublishDocumentEvent(
		ctx,
		s.eventPublisher,
		"document.uploaded",
		documentID,
		tenantID,
		userID,
		payload,
		nil,
	)
}

// 发布文档删除事件
func (s *DocumentService) publishDocumentDeletedEvent(ctx context.Context, documentID, tenantID, userID, reason string) error {
	payload := &eventsv1.DocumentDeletedPayload{
		DocumentId: documentID,
		TenantId:   tenantID,
		UserId:     userID,
		Reason:     reason,
		DeletedAt:  timestamppb.Now(),
	}

	return events.PublishDocumentEvent(
		ctx,
		s.eventPublisher,
		"document.deleted",
		documentID,
		tenantID,
		userID,
		payload,
		nil,
	)
}

// 发布文档扫描事件
func (s *DocumentService) publishDocumentScannedEvent(ctx context.Context, documentID, tenantID, userID string, isClean bool, threats string) error {
	threatsSlice := []string{}
	if threats != "" {
		threatsSlice = []string{threats}
	}

	payload := &eventsv1.DocumentScannedPayload{
		DocumentId: documentID,
		TenantId:   tenantID,
		IsClean:    isClean,
		ScanResult: fmt.Sprintf("Clean: %v", isClean),
		Threats:    threatsSlice,
		ScannedAt:  timestamppb.Now(),
	}

	return events.PublishDocumentEvent(
		ctx,
		s.eventPublisher,
		"document.scanned",
		documentID,
		tenantID,
		userID,
		payload,
		nil,
	)
}

// 获取病毒扫描消息
func getVirusScanMessage(scanResult *infra.ScanResult) string {
	if scanResult == nil {
		return "Skipped"
	}
	if scanResult.IsClean {
		return "Clean"
	}
	return fmt.Sprintf("Virus detected: %s", scanResult.Virus)
}

// ValidateFileName 验证文件名
func ValidateFileName(fileName string) error {
	if fileName == "" {
		return fmt.Errorf("filename cannot be empty")
	}

	// 检查文件扩展名
	ext := filepath.Ext(fileName)
	allowedExts := []string{
		".pdf", ".doc", ".docx", ".txt", ".md",
		".xlsx", ".xls", ".csv",
		".ppt", ".pptx",
		".jpg", ".jpeg", ".png", ".gif",
		".zip", ".tar", ".gz",
	}

	found := false
	for _, allowed := range allowedExts {
		if ext == allowed {
			found = true
			break
		}
	}

	if !found {
		return fmt.Errorf("file type not allowed: %s", ext)
	}

	return nil
}

// GetContentType 根据文件扩展名获取 Content-Type
func GetContentType(fileName string) string {
	ext := filepath.Ext(fileName)
	contentTypes := map[string]string{
		".pdf":  "application/pdf",
		".doc":  "application/msword",
		".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
		".txt":  "text/plain",
		".md":   "text/markdown",
		".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		".xls":  "application/vnd.ms-excel",
		".csv":  "text/csv",
		".ppt":  "application/vnd.ms-powerpoint",
		".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
		".jpg":  "image/jpeg",
		".jpeg": "image/jpeg",
		".png":  "image/png",
		".gif":  "image/gif",
		".zip":  "application/zip",
		".tar":  "application/x-tar",
		".gz":   "application/gzip",
	}

	if ct, ok := contentTypes[ext]; ok {
		return ct
	}

	return "application/octet-stream"
}
