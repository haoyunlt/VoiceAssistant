package domain

import (
	"time"

	"github.com/google/uuid"
)

// Chunk 文档分块
type Chunk struct {
	ID              string
	DocumentID      string
	KnowledgeBaseID string
	Content         string    // 分块内容
	ContentHash     string    // 内容哈希
	Position        int       // 位置序号
	TokenCount      int       // Token数量
	CharCount       int       // 字符数量
	Metadata        map[string]interface{} // 元数据
	Embedding       []float32 // 向量（可选，大数据可能存在向量数据库）
	EmbeddingStatus string    // 向量化状态: pending/completed/failed
	TenantID        string
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// NewChunk 创建新分块
func NewChunk(
	documentID, knowledgeBaseID string,
	content string,
	position int,
	tenantID string,
) *Chunk {
	id := "chunk_" + uuid.New().String()
	now := time.Now()

	return &Chunk{
		ID:              id,
		DocumentID:      documentID,
		KnowledgeBaseID: knowledgeBaseID,
		Content:         content,
		Position:        position,
		TokenCount:      estimateTokenCount(content),
		CharCount:       len(content),
		Metadata:        make(map[string]interface{}),
		EmbeddingStatus: "pending",
		TenantID:        tenantID,
		CreatedAt:       now,
		UpdatedAt:       now,
	}
}

// SetContentHash 设置内容哈希
func (c *Chunk) SetContentHash(hash string) {
	c.ContentHash = hash
	c.UpdatedAt = time.Now()
}

// SetEmbedding 设置向量
func (c *Chunk) SetEmbedding(embedding []float32) {
	c.Embedding = embedding
	c.EmbeddingStatus = "completed"
	c.UpdatedAt = time.Now()
}

// FailEmbedding 向量化失败
func (c *Chunk) FailEmbedding() {
	c.EmbeddingStatus = "failed"
	c.UpdatedAt = time.Now()
}

// AddMetadata 添加元数据
func (c *Chunk) AddMetadata(key string, value interface{}) {
	if c.Metadata == nil {
		c.Metadata = make(map[string]interface{})
	}
	c.Metadata[key] = value
	c.UpdatedAt = time.Now()
}

// HasEmbedding 检查是否有向量
func (c *Chunk) HasEmbedding() bool {
	return c.EmbeddingStatus == "completed" && len(c.Embedding) > 0
}

// IsEmbeddingPending 检查向量是否待生成
func (c *Chunk) IsEmbeddingPending() bool {
	return c.EmbeddingStatus == "pending"
}

// IsEmbeddingFailed 检查向量是否失败
func (c *Chunk) IsEmbeddingFailed() bool {
	return c.EmbeddingStatus == "failed"
}

// Validate 验证分块
func (c *Chunk) Validate() error {
	if c.DocumentID == "" {
		return ErrInvalidDocumentID
	}
	if c.KnowledgeBaseID == "" {
		return ErrInvalidKnowledgeBaseID
	}
	if c.Content == "" {
		return ErrInvalidChunkContent
	}
	if c.TenantID == "" {
		return ErrInvalidTenantID
	}
	return nil
}

// estimateTokenCount 估算Token数量（简化实现）
func estimateTokenCount(text string) int {
	// 简单估算：1 token ≈ 4 字符（英文）或 1.5 字符（中文）
	// 实际应该使用tiktoken等库
	runeCount := len([]rune(text))
	return runeCount / 2 // 简化估算
}
