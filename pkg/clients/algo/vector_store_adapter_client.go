package algo

import (
	"context"
	"fmt"
)

// VectorStoreAdapterClient Vector Store Adapter 客户端
type VectorStoreAdapterClient struct {
	*BaseClient
}

// NewVectorStoreAdapterClient 创建 Vector Store Adapter 客户端
func NewVectorStoreAdapterClient(baseURL string) *VectorStoreAdapterClient {
	return &VectorStoreAdapterClient{
		BaseClient: NewBaseClient(BaseClientConfig{
			ServiceName: "vector-store-adapter",
			BaseURL:     baseURL,
			Timeout:     10,
			MaxRetries:  3,
		}),
	}
}

// VectorData 向量数据
type VectorData struct {
	ID       string                 `json:"id"`
	Vector   []float64              `json:"vector"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// InsertVectorsRequest 插入向量请求
type InsertVectorsRequest struct {
	Backend string       `json:"backend"` // milvus/pgvector
	Data    []VectorData `json:"data"`
}

// InsertVectorsResponse 插入向量响应
type InsertVectorsResponse struct {
	Status     string      `json:"status"`
	Collection string      `json:"collection"`
	Backend    string      `json:"backend"`
	Inserted   int         `json:"inserted"`
	Result     interface{} `json:"result,omitempty"`
}

// SearchVectorsRequest 检索向量请求
type SearchVectorsRequest struct {
	Backend      string                 `json:"backend"`
	QueryVector  []float64              `json:"query_vector"`
	TopK         int                    `json:"top_k"`
	TenantID     string                 `json:"tenant_id,omitempty"`
	Filters      map[string]interface{} `json:"filters,omitempty"`
	SearchParams map[string]interface{} `json:"search_params,omitempty"`
}

// SearchVectorsResponse 检索向量响应
type SearchVectorsResponse struct {
	Status     string         `json:"status"`
	Collection string         `json:"collection"`
	Backend    string         `json:"backend"`
	Results    []VectorResult `json:"results"`
	Count      int            `json:"count"`
}

// VectorResult 向量检索结果
type VectorResult struct {
	ID       string                 `json:"id"`
	Score    float64                `json:"score"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// DeleteResponse 删除响应
type DeleteResponse struct {
	Status       string      `json:"status"`
	Collection   string      `json:"collection"`
	Backend      string      `json:"backend"`
	DocumentID   string      `json:"document_id"`
	DeletedCount int         `json:"deleted_count,omitempty"`
	Result       interface{} `json:"result,omitempty"`
}

// CollectionCountResponse 集合计数响应
type CollectionCountResponse struct {
	Status     string `json:"status"`
	Collection string `json:"collection"`
	Backend    string `json:"backend"`
	Count      int    `json:"count"`
}

// InsertVectors 插入向量
func (c *VectorStoreAdapterClient) InsertVectors(ctx context.Context, collectionName string, req *InsertVectorsRequest) (*InsertVectorsResponse, error) {
	path := fmt.Sprintf("/collections/%s/insert", collectionName)
	var result InsertVectorsResponse
	err := c.Post(ctx, path, req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// SearchVectors 检索向量
func (c *VectorStoreAdapterClient) SearchVectors(ctx context.Context, collectionName string, req *SearchVectorsRequest) (*SearchVectorsResponse, error) {
	path := fmt.Sprintf("/collections/%s/search", collectionName)
	var result SearchVectorsResponse
	err := c.Post(ctx, path, req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// DeleteByDocument 删除文档的所有向量
func (c *VectorStoreAdapterClient) DeleteByDocument(ctx context.Context, collectionName, documentID, backend string) (*DeleteResponse, error) {
	path := fmt.Sprintf("/collections/%s/documents/%s?backend=%s", collectionName, documentID, backend)
	var result DeleteResponse
	err := c.Delete(ctx, path)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// GetCollectionCount 获取集合中的向量数量
func (c *VectorStoreAdapterClient) GetCollectionCount(ctx context.Context, collectionName, backend string) (*CollectionCountResponse, error) {
	path := fmt.Sprintf("/collections/%s/count?backend=%s", collectionName, backend)
	var result CollectionCountResponse
	err := c.Get(ctx, path, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// GetStats 获取统计信息
func (c *VectorStoreAdapterClient) GetStats(ctx context.Context) (map[string]interface{}, error) {
	var result struct {
		Status            string                 `json:"status"`
		VectorStoreManager map[string]interface{} `json:"vector_store_manager"`
	}
	err := c.Get(ctx, "/stats", &result)
	if err != nil {
		return nil, err
	}
	return result.VectorStoreManager, nil
}

