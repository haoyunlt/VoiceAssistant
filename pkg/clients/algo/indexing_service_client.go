package algo

import (
	"context"
	"fmt"
)

// IndexingServiceClient Indexing Service 客户端
type IndexingServiceClient struct {
	*BaseClient
}

// NewIndexingServiceClient 创建 Indexing Service 客户端
func NewIndexingServiceClient(baseURL string) *IndexingServiceClient {
	return &IndexingServiceClient{
		BaseClient: NewBaseClient(BaseClientConfig{
			ServiceName: "indexing-service",
			BaseURL:     baseURL,
			Timeout:     300, // 索引任务可能较长
			MaxRetries:  2,
		}),
	}
}

// DocumentChunk 文档块
type DocumentChunk struct {
	Content  string                 `json:"content"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// IncrementalUpdateRequest 增量更新请求
type IncrementalUpdateRequest struct {
	DocumentID string          `json:"document_id"`
	TenantID   string          `json:"tenant_id"`
	Chunks     []DocumentChunk `json:"chunks"`
}

// IncrementalUpdateResponse 增量更新响应
type IncrementalUpdateResponse struct {
	DocumentID      string `json:"document_id"`
	ChunksProcessed int    `json:"chunks_processed"`
	VectorsStored   int    `json:"vectors_stored"`
}

// IndexingStats 索引统计
type IndexingStats struct {
	DocumentsProcessed int     `json:"documents_processed"`
	ChunksCreated      int     `json:"chunks_created"`
	VectorsStored      int     `json:"vectors_stored"`
	ProcessingTimeAvg  float64 `json:"processing_time_avg"`
}

// TriggerIndexing 触发文档索引
func (c *IndexingServiceClient) TriggerIndexing(ctx context.Context, documentID string) error {
	path := fmt.Sprintf("/trigger?document_id=%s", documentID)
	var result map[string]interface{}
	return c.Post(ctx, path, nil, &result)
}

// IncrementalUpdate 增量更新文档
func (c *IndexingServiceClient) IncrementalUpdate(ctx context.Context, req *IncrementalUpdateRequest) (*IncrementalUpdateResponse, error) {
	var result IncrementalUpdateResponse
	err := c.Post(ctx, "/incremental/update", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// DeleteDocument 删除文档
func (c *IndexingServiceClient) DeleteDocument(ctx context.Context, documentID, tenantID string) error {
	path := fmt.Sprintf("/incremental/delete?document_id=%s&tenant_id=%s", documentID, tenantID)
	return c.Delete(ctx, path)
}

// GetStats 获取索引统计信息
func (c *IndexingServiceClient) GetStats(ctx context.Context) (*IndexingStats, error) {
	var result IndexingStats
	err := c.Get(ctx, "/stats", &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

