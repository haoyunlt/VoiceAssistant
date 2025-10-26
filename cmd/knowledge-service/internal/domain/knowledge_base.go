package domain

import (
	"time"

	"github.com/google/uuid"
)

// KnowledgeBaseType 知识库类型
type KnowledgeBaseType string

const (
	KnowledgeBaseTypeGeneral   KnowledgeBaseType = "general"   // 通用知识库
	KnowledgeBaseTypeProduct   KnowledgeBaseType = "product"   // 产品知识库
	KnowledgeBaseTypeFAQ       KnowledgeBaseType = "faq"       // FAQ知识库
	KnowledgeBaseTypePolicy    KnowledgeBaseType = "policy"    // 政策知识库
	KnowledgeBaseTypeCustom    KnowledgeBaseType = "custom"    // 自定义知识库
)

// KnowledgeBaseStatus 知识库状态
type KnowledgeBaseStatus string

const (
	KnowledgeBaseStatusActive   KnowledgeBaseStatus = "active"   // 激活
	KnowledgeBaseStatusInactive KnowledgeBaseStatus = "inactive" // 未激活
	KnowledgeBaseStatusArchived KnowledgeBaseStatus = "archived" // 已归档
)

// EmbeddingModel 向量化模型
type EmbeddingModel string

const (
	EmbeddingModelOpenAI      EmbeddingModel = "openai"        // OpenAI embedding
	EmbeddingModelCohere      EmbeddingModel = "cohere"        // Cohere embedding
	EmbeddingModelHuggingFace EmbeddingModel = "huggingface"   // HuggingFace embedding
	EmbeddingModelLocal       EmbeddingModel = "local"         // 本地模型
)

// KnowledgeBase 知识库聚合根
type KnowledgeBase struct {
	ID              string
	Name            string
	Description     string
	Type            KnowledgeBaseType
	Status          KnowledgeBaseStatus
	TenantID        string
	CreatedBy       string
	EmbeddingModel  EmbeddingModel
	EmbeddingDim    int                    // 向量维度
	ChunkSize       int                    // 分块大小
	ChunkOverlap    int                    // 分块重叠
	Settings        map[string]interface{} // 其他设置
	DocumentCount   int                    // 文档数量
	ChunkCount      int                    // 分块数量
	TotalSize       int64                  // 总大小(字节)
	LastIndexedAt   *time.Time             // 最后索引时间
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// NewKnowledgeBase 创建新知识库
func NewKnowledgeBase(
	name, description string,
	kbType KnowledgeBaseType,
	tenantID, createdBy string,
	embeddingModel EmbeddingModel,
) *KnowledgeBase {
	id := "kb_" + uuid.New().String()
	now := time.Now()

	// 默认配置
	chunkSize := 500
	chunkOverlap := 50
	embeddingDim := 1536 // OpenAI ada-002 默认维度

	switch embeddingModel {
	case EmbeddingModelOpenAI:
		embeddingDim = 1536
	case EmbeddingModelCohere:
		embeddingDim = 768
	case EmbeddingModelHuggingFace:
		embeddingDim = 768
	case EmbeddingModelLocal:
		embeddingDim = 768
	}

	return &KnowledgeBase{
		ID:             id,
		Name:           name,
		Description:    description,
		Type:           kbType,
		Status:         KnowledgeBaseStatusActive,
		TenantID:       tenantID,
		CreatedBy:      createdBy,
		EmbeddingModel: embeddingModel,
		EmbeddingDim:   embeddingDim,
		ChunkSize:      chunkSize,
		ChunkOverlap:   chunkOverlap,
		Settings:       make(map[string]interface{}),
		DocumentCount:  0,
		ChunkCount:     0,
		TotalSize:      0,
		CreatedAt:      now,
		UpdatedAt:      now,
	}
}

// Update 更新知识库信息
func (kb *KnowledgeBase) Update(name, description string) {
	if name != "" {
		kb.Name = name
	}
	if description != "" {
		kb.Description = description
	}
	kb.UpdatedAt = time.Now()
}

// UpdateSettings 更新设置
func (kb *KnowledgeBase) UpdateSettings(settings map[string]interface{}) {
	if kb.Settings == nil {
		kb.Settings = make(map[string]interface{})
	}
	for k, v := range settings {
		kb.Settings[k] = v
	}
	kb.UpdatedAt = time.Now()
}

// SetChunkConfig 设置分块配置
func (kb *KnowledgeBase) SetChunkConfig(chunkSize, chunkOverlap int) error {
	if chunkSize < 100 || chunkSize > 2000 {
		return ErrInvalidChunkSize
	}
	if chunkOverlap < 0 || chunkOverlap >= chunkSize {
		return ErrInvalidChunkOverlap
	}
	kb.ChunkSize = chunkSize
	kb.ChunkOverlap = chunkOverlap
	kb.UpdatedAt = time.Now()
	return nil
}

// Activate 激活知识库
func (kb *KnowledgeBase) Activate() {
	kb.Status = KnowledgeBaseStatusActive
	kb.UpdatedAt = time.Now()
}

// Deactivate 停用知识库
func (kb *KnowledgeBase) Deactivate() {
	kb.Status = KnowledgeBaseStatusInactive
	kb.UpdatedAt = time.Now()
}

// Archive 归档知识库
func (kb *KnowledgeBase) Archive() {
	kb.Status = KnowledgeBaseStatusArchived
	kb.UpdatedAt = time.Now()
}

// IncrementDocumentCount 增加文档计数
func (kb *KnowledgeBase) IncrementDocumentCount(delta int) {
	kb.DocumentCount += delta
	kb.UpdatedAt = time.Now()
}

// IncrementChunkCount 增加分块计数
func (kb *KnowledgeBase) IncrementChunkCount(delta int) {
	kb.ChunkCount += delta
	kb.UpdatedAt = time.Now()
}

// AddSize 增加大小
func (kb *KnowledgeBase) AddSize(size int64) {
	kb.TotalSize += size
	kb.UpdatedAt = time.Now()
}

// UpdateLastIndexedAt 更新最后索引时间
func (kb *KnowledgeBase) UpdateLastIndexedAt() {
	now := time.Now()
	kb.LastIndexedAt = &now
	kb.UpdatedAt = now
}

// IsActive 检查是否激活
func (kb *KnowledgeBase) IsActive() bool {
	return kb.Status == KnowledgeBaseStatusActive
}

// IsArchived 检查是否已归档
func (kb *KnowledgeBase) IsArchived() bool {
	return kb.Status == KnowledgeBaseStatusArchived
}

// CanModify 检查是否可以修改
func (kb *KnowledgeBase) CanModify() bool {
	return kb.Status != KnowledgeBaseStatusArchived
}

// Validate 验证知识库
func (kb *KnowledgeBase) Validate() error {
	if kb.Name == "" {
		return ErrInvalidKnowledgeBaseName
	}
	if kb.TenantID == "" {
		return ErrInvalidTenantID
	}
	if kb.CreatedBy == "" {
		return ErrInvalidCreatedBy
	}
	return nil
}
