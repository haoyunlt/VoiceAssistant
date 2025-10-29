package algo

import (
	"context"
	"fmt"
	"time"
)

// KnowledgeServiceClient Knowledge Service 客户端（统一的 Python 服务）
type KnowledgeServiceClient struct {
	*BaseClient
}

// NewKnowledgeServiceClient 创建 Knowledge Service 客户端
func NewKnowledgeServiceClient(baseURL string) *KnowledgeServiceClient {
	return &KnowledgeServiceClient{
		BaseClient: NewBaseClient(BaseClientConfig{
			ServiceName: "knowledge-service",
			BaseURL:     baseURL,
			Timeout:     60,
			MaxRetries:  2,
		}),
	}
}

// ========== Document Management ==========

// UploadDocumentRequest 上传文档请求
type UploadDocumentRequest struct {
	KnowledgeBaseID string            `json:"knowledge_base_id"`
	Name            string            `json:"name,omitempty"`
	Metadata        map[string]string `json:"metadata,omitempty"`
}

// UploadDocumentResponse 上传文档响应
type UploadDocumentResponse struct {
	DocumentID string `json:"document_id"`
	FileName   string `json:"file_name"`
	FileSize   int    `json:"file_size"`
	FileType   string `json:"file_type"`
	Status     string `json:"status"`
	FileURL    string `json:"file_url,omitempty"`
}

// ProcessDocumentRequest 处理文档请求
type ProcessDocumentRequest struct {
	DocumentID   string `json:"document_id"`
	ChunkSize    int    `json:"chunk_size,omitempty"`
	ChunkOverlap int    `json:"chunk_overlap,omitempty"`
}

// ProcessDocumentResponse 处理文档响应
type ProcessDocumentResponse struct {
	DocumentID  string `json:"document_id"`
	ChunksCount int    `json:"chunks_count"`
	Status      string `json:"status"`
}

// DocumentInfo 文档信息
type DocumentInfo struct {
	DocumentID      string    `json:"document_id"`
	Name            string    `json:"name"`
	FileName        string    `json:"file_name"`
	FileType        string    `json:"file_type"`
	FileSize        int       `json:"file_size"`
	Status          string    `json:"status"`
	ChunkCount      int       `json:"chunk_count"`
	UploadedBy      string    `json:"uploaded_by"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// ProcessDocument 处理文档（分块）
func (c *KnowledgeServiceClient) ProcessDocument(ctx context.Context, req *ProcessDocumentRequest) (*ProcessDocumentResponse, error) {
	var result ProcessDocumentResponse
	err := c.Post(ctx, "/api/v1/documents/process", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// GetDocument 获取文档详情
func (c *KnowledgeServiceClient) GetDocument(ctx context.Context, documentID string) (*DocumentInfo, error) {
	var result DocumentInfo
	path := fmt.Sprintf("/api/v1/documents/%s", documentID)
	err := c.Get(ctx, path, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// DeleteDocument 删除文档
func (c *KnowledgeServiceClient) DeleteDocument(ctx context.Context, documentID string) error {
	path := fmt.Sprintf("/api/v1/documents/%s", documentID)
	return c.Delete(ctx, path)
}

// GetDownloadURL 获取文档下载 URL
func (c *KnowledgeServiceClient) GetDownloadURL(ctx context.Context, documentID string) (string, error) {
	var result struct {
		DownloadURL string `json:"download_url"`
		ExpiresIn   int    `json:"expires_in"`
	}
	path := fmt.Sprintf("/api/v1/documents/%s/download", documentID)
	err := c.Get(ctx, path, &result)
	if err != nil {
		return "", err
	}
	return result.DownloadURL, nil
}

// ========== Version Management ==========

// CreateVersionRequest 创建版本请求
type CreateVersionRequest struct {
	KnowledgeBaseID string `json:"knowledge_base_id"`
	Description     string `json:"description,omitempty"`
}

// VersionSnapshot 版本快照
type VersionSnapshot struct {
	DocumentCount   int               `json:"document_count"`
	ChunkCount      int               `json:"chunk_count"`
	EntityCount     int               `json:"entity_count"`
	RelationCount   int               `json:"relation_count"`
	VectorIndexHash string            `json:"vector_index_hash"`
	GraphSnapshotID string            `json:"graph_snapshot_id"`
	CreatedAt       time.Time         `json:"created_at"`
}

// VersionInfo 版本信息
type VersionInfo struct {
	ID              string          `json:"id"`
	KnowledgeBaseID string          `json:"knowledge_base_id"`
	Version         int             `json:"version"`
	Snapshot        VersionSnapshot `json:"snapshot"`
	Description     string          `json:"description"`
	CreatedBy       string          `json:"created_by"`
	TenantID        string          `json:"tenant_id"`
	CreatedAt       time.Time       `json:"created_at"`
}

// RollbackRequest 回滚请求
type RollbackRequest struct {
	VersionID string `json:"version_id"`
}

// CreateVersion 创建版本快照
func (c *KnowledgeServiceClient) CreateVersion(ctx context.Context, req *CreateVersionRequest) (*VersionInfo, error) {
	var result VersionInfo
	err := c.Post(ctx, "/api/v1/versions/", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// ListVersions 列出版本历史
func (c *KnowledgeServiceClient) ListVersions(ctx context.Context, knowledgeBaseID string, offset, limit int) ([]VersionInfo, error) {
	var result struct {
		Versions []VersionInfo `json:"versions"`
		Total    int           `json:"total"`
	}
	path := fmt.Sprintf("/api/v1/versions/?knowledge_base_id=%s&offset=%d&limit=%d", knowledgeBaseID, offset, limit)
	err := c.Get(ctx, path, &result)
	if err != nil {
		return nil, err
	}
	return result.Versions, nil
}

// GetVersion 获取版本详情
func (c *KnowledgeServiceClient) GetVersion(ctx context.Context, versionID string) (*VersionInfo, error) {
	var result VersionInfo
	path := fmt.Sprintf("/api/v1/versions/%s", versionID)
	err := c.Get(ctx, path, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// RollbackVersion 回滚到指定版本
func (c *KnowledgeServiceClient) RollbackVersion(ctx context.Context, versionID string) error {
	req := &RollbackRequest{VersionID: versionID}
	var result map[string]interface{}
	return c.Post(ctx, "/api/v1/versions/rollback", req, &result)
}

// DeleteVersion 删除版本
func (c *KnowledgeServiceClient) DeleteVersion(ctx context.Context, versionID string) error {
	path := fmt.Sprintf("/api/v1/versions/%s", versionID)
	return c.Delete(ctx, path)
}

// ========== Knowledge Graph ==========

// ExtractRequest 实体提取请求
type ExtractRequest struct {
	Text   string `json:"text"`
	Source string `json:"source,omitempty"`
}

// ExtractResponse 实体提取响应
type ExtractResponse struct {
	Success          bool `json:"success"`
	EntitiesExtracted int  `json:"entities_extracted"`
	EntitiesStored    int  `json:"entities_stored"`
	RelationsExtracted int  `json:"relations_extracted"`
	RelationsStored    int  `json:"relations_stored"`
}

// QueryEntityRequest 查询实体请求
type QueryEntityRequest struct {
	Entity string `json:"entity"`
}

// EntityInfo 实体信息
type EntityInfo struct {
	Name       string                 `json:"name"`
	Label      string                 `json:"label"`
	Properties map[string]interface{} `json:"properties"`
}

// RelationInfo 关系信息
type RelationInfo struct {
	SourceEntity   string                 `json:"source_entity"`
	TargetEntity   string                 `json:"target_entity"`
	RelationType   string                 `json:"relation_type"`
	Properties     map[string]interface{} `json:"properties"`
}

// EntityQueryResponse 实体查询响应
type EntityQueryResponse struct {
	Entity     EntityInfo     `json:"entity"`
	Relations  []RelationInfo `json:"relations"`
}

// ExtractEntities 提取实体和关系
func (c *KnowledgeServiceClient) ExtractEntities(ctx context.Context, text, source string) (*ExtractResponse, error) {
	req := &ExtractRequest{
		Text:   text,
		Source: source,
	}
	var result ExtractResponse
	err := c.Post(ctx, "/api/v1/kg/extract", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// QueryEntity 查询实体
func (c *KnowledgeServiceClient) QueryEntity(ctx context.Context, entity string) (*EntityQueryResponse, error) {
	req := &QueryEntityRequest{Entity: entity}
	var result EntityQueryResponse
	err := c.Post(ctx, "/api/v1/kg/query/entity", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// ========== GraphRAG ==========

// BuildGraphRAGIndexRequest 构建 GraphRAG 索引请求
type BuildGraphRAGIndexRequest struct {
	DocumentID string                   `json:"document_id"`
	Chunks     []map[string]interface{} `json:"chunks"`
	Domain     string                   `json:"domain,omitempty"`
}

// BuildGraphRAGIndexResponse 构建 GraphRAG 索引响应
type BuildGraphRAGIndexResponse struct {
	DocumentID    string `json:"document_id"`
	Level0Count   int    `json:"level_0_count"`
	Level1Count   int    `json:"level_1_count"`
	Level2Count   int    `json:"level_2_count"`
	Level3Count   int    `json:"level_3_count"`
	Status        string `json:"status"`
}

// HybridRetrieveRequest 混合检索请求
type HybridRetrieveRequest struct {
	Query string `json:"query"`
	Mode  string `json:"mode"` // hybrid, vector, graph, bm25
	TopK  int    `json:"top_k,omitempty"`
}

// RetrievalResult 检索结果
type RetrievalResult struct {
	ChunkID  string                 `json:"chunk_id"`
	Content  string                 `json:"content"`
	Score    float64                `json:"score"`
	Source   string                 `json:"source"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// HybridRetrieveResponse 混合检索响应
type HybridRetrieveResponse struct {
	Query   string            `json:"query"`
	Results []RetrievalResult `json:"results"`
	Total   int               `json:"total"`
}

// BuildGraphRAGIndex 构建 GraphRAG 索引
func (c *KnowledgeServiceClient) BuildGraphRAGIndex(ctx context.Context, req *BuildGraphRAGIndexRequest) (*BuildGraphRAGIndexResponse, error) {
	var result BuildGraphRAGIndexResponse
	err := c.Post(ctx, "/api/v1/graphrag/build-index", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// HybridRetrieve 混合检索
func (c *KnowledgeServiceClient) HybridRetrieve(ctx context.Context, query, mode string, topK int) (*HybridRetrieveResponse, error) {
	req := &HybridRetrieveRequest{
		Query: query,
		Mode:  mode,
		TopK:  topK,
	}
	var result HybridRetrieveResponse
	err := c.Post(ctx, "/api/v1/graphrag/retrieve/hybrid", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}
