package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// IndexingClient 索引服务客户端
type IndexingClient struct {
	baseURL    string
	httpClient *http.Client
}

// NewIndexingClient 创建索引服务客户端
func NewIndexingClient(baseURL string) *IndexingClient {
	return &IndexingClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

// IndexDocumentRequest 索引文档请求
type IndexDocumentRequest struct {
	DocumentID      string                 `json:"document_id"`
	TenantID        string                 `json:"tenant_id"`
	KnowledgeBaseID string                 `json:"knowledge_base_id"`
	Options         map[string]interface{} `json:"options"`
}

// IndexDocumentResponse 索引文档响应
type IndexDocumentResponse struct {
	JobID   string `json:"job_id"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

// TriggerIndexing 触发文档索引
func (c *IndexingClient) TriggerIndexing(ctx context.Context, req *IndexDocumentRequest) (*IndexDocumentResponse, error) {
	// 构造请求体
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	// 发送POST请求
	httpReq, err := http.NewRequestWithContext(
		ctx,
		"POST",
		fmt.Sprintf("%s/api/v1/documents/index", c.baseURL),
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// 执行请求
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	// 检查状态码
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("indexing request failed: status=%d, body=%s", resp.StatusCode, string(respBody))
	}

	// 解析响应
	var indexResp IndexDocumentResponse
	if err := json.Unmarshal(respBody, &indexResp); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &indexResp, nil
}

// GetIndexingStatus 获取索引状态
func (c *IndexingClient) GetIndexingStatus(ctx context.Context, jobID string) (map[string]interface{}, error) {
	httpReq, err := http.NewRequestWithContext(
		ctx,
		"GET",
		fmt.Sprintf("%s/api/v1/documents/index/%s", c.baseURL, jobID),
		nil,
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("get status failed: status=%d, body=%s", resp.StatusCode, string(respBody))
	}

	var status map[string]interface{}
	if err := json.Unmarshal(respBody, &status); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return status, nil
}
