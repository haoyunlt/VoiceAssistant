package domain

import (
	"time"

	"github.com/google/uuid"
)

// DocumentType 文档类型
type DocumentType string

const (
	DocumentTypeText     DocumentType = "text"     // 纯文本
	DocumentTypePDF      DocumentType = "pdf"      // PDF
	DocumentTypeWord     DocumentType = "word"     // Word文档
	DocumentTypeMarkdown DocumentType = "markdown" // Markdown
	DocumentTypeHTML     DocumentType = "html"     // HTML
	DocumentTypeJSON     DocumentType = "json"     // JSON
)

// DocumentStatus 文档状态
type DocumentStatus string

const (
	DocumentStatusPending   DocumentStatus = "pending"   // 待处理
	DocumentStatusProcessing DocumentStatus = "processing" // 处理中
	DocumentStatusCompleted  DocumentStatus = "completed"  // 已完成
	DocumentStatusFailed     DocumentStatus = "failed"     // 失败
	DocumentStatusDeleted    DocumentStatus = "deleted"    // 已删除
)

// Document 文档聚合根
type Document struct {
	ID              string
	KnowledgeBaseID string
	Name            string
	FileName        string
	FileType        DocumentType
	FileSize        int64  // 字节
	FilePath        string // 存储路径
	FileURL         string // 访问URL
	Content         string // 文档内容
	Summary         string // 文档摘要
	Status          DocumentStatus
	ChunkCount      int                    // 分块数量
	TenantID        string
	UploadedBy      string
	Metadata        map[string]interface{} // 元数据
	ErrorMessage    string                 // 错误信息
	ProcessedAt     *time.Time             // 处理时间
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// NewDocument 创建新文档
func NewDocument(
	knowledgeBaseID string,
	name, fileName string,
	fileType DocumentType,
	fileSize int64,
	filePath string,
	tenantID, uploadedBy string,
) *Document {
	id := "doc_" + uuid.New().String()
	now := time.Now()

	return &Document{
		ID:              id,
		KnowledgeBaseID: knowledgeBaseID,
		Name:            name,
		FileName:        fileName,
		FileType:        fileType,
		FileSize:        fileSize,
		FilePath:        filePath,
		Status:          DocumentStatusPending,
		ChunkCount:      0,
		TenantID:        tenantID,
		UploadedBy:      uploadedBy,
		Metadata:        make(map[string]interface{}),
		CreatedAt:       now,
		UpdatedAt:       now,
	}
}

// SetContent 设置文档内容
func (d *Document) SetContent(content string) {
	d.Content = content
	d.UpdatedAt = time.Now()
}

// SetSummary 设置文档摘要
func (d *Document) SetSummary(summary string) {
	d.Summary = summary
	d.UpdatedAt = time.Now()
}

// SetFileURL 设置文件URL
func (d *Document) SetFileURL(url string) {
	d.FileURL = url
	d.UpdatedAt = time.Now()
}

// StartProcessing 开始处理
func (d *Document) StartProcessing() {
	d.Status = DocumentStatusProcessing
	d.UpdatedAt = time.Now()
}

// CompleteProcessing 完成处理
func (d *Document) CompleteProcessing(chunkCount int) {
	d.Status = DocumentStatusCompleted
	d.ChunkCount = chunkCount
	now := time.Now()
	d.ProcessedAt = &now
	d.UpdatedAt = now
}

// FailProcessing 处理失败
func (d *Document) FailProcessing(errorMsg string) {
	d.Status = DocumentStatusFailed
	d.ErrorMessage = errorMsg
	d.UpdatedAt = time.Now()
}

// MarkDeleted 标记删除
func (d *Document) MarkDeleted() {
	d.Status = DocumentStatusDeleted
	d.UpdatedAt = time.Now()
}

// Update 更新文档信息
func (d *Document) Update(name string, metadata map[string]interface{}) {
	if name != "" {
		d.Name = name
	}
	if metadata != nil {
		if d.Metadata == nil {
			d.Metadata = make(map[string]interface{})
		}
		for k, v := range metadata {
			d.Metadata[k] = v
		}
	}
	d.UpdatedAt = time.Now()
}

// IsProcessed 检查是否已处理
func (d *Document) IsProcessed() bool {
	return d.Status == DocumentStatusCompleted
}

// IsFailed 检查是否失败
func (d *Document) IsFailed() bool {
	return d.Status == DocumentStatusFailed
}

// IsDeleted 检查是否已删除
func (d *Document) IsDeleted() bool {
	return d.Status == DocumentStatusDeleted
}

// CanProcess 检查是否可以处理
func (d *Document) CanProcess() bool {
	return d.Status == DocumentStatusPending || d.Status == DocumentStatusFailed
}

// Validate 验证文档
func (d *Document) Validate() error {
	if d.KnowledgeBaseID == "" {
		return ErrInvalidKnowledgeBaseID
	}
	if d.Name == "" {
		return ErrInvalidDocumentName
	}
	if d.FileName == "" {
		return ErrInvalidFileName
	}
	if d.TenantID == "" {
		return ErrInvalidTenantID
	}
	return nil
}
