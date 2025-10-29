package domain

import (
	"encoding/json"
	"time"
)

// KnowledgeBaseVersion 知识库版本
type KnowledgeBaseVersion struct {
	ID              string
	KnowledgeBaseID string
	Version         int
	Snapshot        VersionSnapshot
	Description     string
	CreatedAt       time.Time
	CreatedBy       string
	TenantID        string
}

// VersionSnapshot 版本快照
type VersionSnapshot struct {
	DocumentCount   int               `json:"document_count"`
	ChunkCount      int               `json:"chunk_count"`
	EntityCount     int               `json:"entity_count"`
	RelationCount   int               `json:"relation_count"`
	VectorIndexHash string            `json:"vector_index_hash"`
	GraphSnapshotID string            `json:"graph_snapshot_id"`
	Metadata        map[string]string `json:"metadata"`
	CreatedAt       time.Time         `json:"created_at"`
}

// NewKnowledgeBaseVersion 创建新版本
func NewKnowledgeBaseVersion(
	kbID string,
	version int,
	createdBy string,
	tenantID string,
	description string,
) *KnowledgeBaseVersion {
	return &KnowledgeBaseVersion{
		ID:              generateID(),
		KnowledgeBaseID: kbID,
		Version:         version,
		Description:     description,
		CreatedAt:       time.Now(),
		CreatedBy:       createdBy,
		TenantID:        tenantID,
	}
}

// ToJSON 转换为JSON
func (v *KnowledgeBaseVersion) ToJSON() (string, error) {
	data, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// VersionRepository 版本仓库接口
type VersionRepository interface {
	// Create 创建版本
	Create(ctx interface{}, version *KnowledgeBaseVersion) error

	// GetByID 根据ID获取版本
	GetByID(ctx interface{}, id string) (*KnowledgeBaseVersion, error)

	// GetByKnowledgeBase 获取知识库的所有版本
	GetByKnowledgeBase(ctx interface{}, kbID string, offset, limit int) ([]*KnowledgeBaseVersion, int64, error)

	// GetLatestVersion 获取最新版本
	GetLatestVersion(ctx interface{}, kbID string) (*KnowledgeBaseVersion, error)

	// Delete 删除版本
	Delete(ctx interface{}, id string) error

	// CountByKnowledgeBase 统计知识库版本数
	CountByKnowledgeBase(ctx interface{}, kbID string) (int64, error)
}
