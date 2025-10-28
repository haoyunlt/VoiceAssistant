package adapter

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// AdapterClient model-adapter客户端
type AdapterClient struct {
	baseURL    string
	httpClient *http.Client
}

// NewAdapterClient 创建adapter客户端
func NewAdapterClient(baseURL string) *AdapterClient {
	return &AdapterClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

// ChatRequest 聊天请求
type ChatRequest struct {
	Model       string                   `json:"model"`
	Messages    []map[string]interface{} `json:"messages"`
	Temperature float64                  `json:"temperature,omitempty"`
	MaxTokens   int                      `json:"max_tokens,omitempty"`
	Stream      bool                     `json:"stream,omitempty"`
}

// ChatResponse 聊天响应
type ChatResponse struct {
	ID      string `json:"id"`
	Model   string `json:"model"`
	Choices []struct {
		Message struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		} `json:"message"`
		FinishReason string `json:"finish_reason"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		TotalTokens      int `json:"total_tokens"`
	} `json:"usage"`
}

// ForwardChatRequest 转发聊天请求到model-adapter
func (c *AdapterClient) ForwardChatRequest(ctx context.Context, req *ChatRequest) (*ChatResponse, error) {
	// 构造请求体
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	// 创建HTTP请求
	httpReq, err := http.NewRequestWithContext(
		ctx,
		"POST",
		fmt.Sprintf("%s/api/v1/chat/completions", c.baseURL),
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// 发送请求
	startTime := time.Now()
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
		return nil, fmt.Errorf("adapter request failed: status=%d, body=%s", resp.StatusCode, string(respBody))
	}

	// 解析响应
	var chatResp ChatResponse
	if err := json.Unmarshal(respBody, &chatResp); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	// 记录延迟
	latency := time.Since(startTime)
	_ = latency // 可用于统计

	return &chatResp, nil
}

// EmbeddingRequest embedding请求
type EmbeddingRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

// EmbeddingResponse embedding响应
type EmbeddingResponse struct {
	Data []struct {
		Embedding []float64 `json:"embedding"`
		Index     int       `json:"index"`
	} `json:"data"`
	Model string `json:"model"`
	Usage struct {
		PromptTokens int `json:"prompt_tokens"`
		TotalTokens  int `json:"total_tokens"`
	} `json:"usage"`
}

// ForwardEmbeddingRequest 转发embedding请求
func (c *AdapterClient) ForwardEmbeddingRequest(ctx context.Context, req *EmbeddingRequest) (*EmbeddingResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(
		ctx,
		"POST",
		fmt.Sprintf("%s/api/v1/embedding/create", c.baseURL),
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

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
		return nil, fmt.Errorf("adapter request failed: status=%d, body=%s", resp.StatusCode, string(respBody))
	}

	var embResp EmbeddingResponse
	if err := json.Unmarshal(respBody, &embResp); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &embResp, nil
}

// HealthCheckRequest 健康检查请求
type HealthCheckRequest struct {
	Model string `json:"model"`
}

// HealthCheckResponse 健康检查响应
type HealthCheckResponse struct {
	Status         string  `json:"status"` // "healthy", "degraded", "unhealthy"
	ResponseTimeMs float64 `json:"response_time_ms"`
	Available      bool    `json:"available"`
	Message        string  `json:"message,omitempty"`
	Error          string  `json:"error,omitempty"`
}

// HealthCheck 执行真实的健康检查
func (c *AdapterClient) HealthCheck(ctx context.Context, modelName string) (*HealthCheckResponse, error) {
	startTime := time.Now()

	// 方法1：使用简单的测试prompt
	testReq := &ChatRequest{
		Model: modelName,
		Messages: []map[string]interface{}{
			{
				"role":    "user",
				"content": "Hello",
			},
		},
		MaxTokens:   5,
		Temperature: 0.1,
	}

	// 设置较短的超时
	checkCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	resp, err := c.ForwardChatRequest(checkCtx, testReq)
	responseTime := time.Since(startTime).Milliseconds()

	if err != nil {
		return &HealthCheckResponse{
			Status:         "unhealthy",
			ResponseTimeMs: float64(responseTime),
			Available:      false,
			Error:          err.Error(),
		}, nil
	}

	// 检查响应是否有效
	if len(resp.Choices) == 0 {
		return &HealthCheckResponse{
			Status:         "degraded",
			ResponseTimeMs: float64(responseTime),
			Available:      true,
			Message:        "Model responded but returned empty choices",
		}, nil
	}

	// 判断健康状态
	status := "healthy"
	if responseTime > 5000 { // 超过5秒认为是degraded
		status = "degraded"
	}

	return &HealthCheckResponse{
		Status:         status,
		ResponseTimeMs: float64(responseTime),
		Available:      true,
		Message:        fmt.Sprintf("Model %s is responding normally", modelName),
	}, nil
}

// BatchHealthCheck 批量健康检查
func (c *AdapterClient) BatchHealthCheck(ctx context.Context, modelNames []string) map[string]*HealthCheckResponse {
	results := make(map[string]*HealthCheckResponse)

	// 并发检查所有模型
	resultChan := make(chan struct {
		modelName string
		result    *HealthCheckResponse
	}, len(modelNames))

	for _, modelName := range modelNames {
		go func(name string) {
			result, _ := c.HealthCheck(ctx, name)
			resultChan <- struct {
				modelName string
				result    *HealthCheckResponse
			}{name, result}
		}(modelName)
	}

	// 收集结果
	for i := 0; i < len(modelNames); i++ {
		res := <-resultChan
		results[res.modelName] = res.result
	}

	return results
}
