package infrastructure

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// AIServiceClient AI服务客户端
type AIServiceClient struct {
	httpClient *http.Client
	baseURLs   map[string]string
}

// NewAIServiceClient 创建AI服务客户端
func NewAIServiceClient() *AIServiceClient {
	return &AIServiceClient{
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
		baseURLs: map[string]string{
			"model-adapter":     "http://model-adapter:8000",
			"rag-engine":        "http://rag-engine:8004",
			"agent-engine":      "http://agent-engine:8003",
			"retrieval-service": "http://retrieval-service:8001",
		},
	}
}

// CallModelAdapter 调用模型适配器
func (c *AIServiceClient) CallModelAdapter(ctx context.Context, req *ModelRequest) (*ModelResponse, error) {
	url := fmt.Sprintf("%s/v1/chat/completions", c.baseURLs["model-adapter"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var result ModelResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// CallRAGEngine 调用RAG引擎
func (c *AIServiceClient) CallRAGEngine(ctx context.Context, req *RAGRequest) (*RAGResponse, error) {
	url := fmt.Sprintf("%s/generate", c.baseURLs["rag-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var result RAGResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// CallAgentEngine 调用Agent引擎
func (c *AIServiceClient) CallAgentEngine(ctx context.Context, req *AgentRequest) (*AgentResponse, error) {
	url := fmt.Sprintf("%s/execute", c.baseURLs["agent-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var result AgentResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// CallRetrievalService 调用检索服务
func (c *AIServiceClient) CallRetrievalService(ctx context.Context, req *RetrievalRequest) (*RetrievalResponse, error) {
	url := fmt.Sprintf("%s/retrieve", c.baseURLs["retrieval-service"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var result RetrievalResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// --- 请求和响应结构 ---

// ModelRequest 模型请求
type ModelRequest struct {
	Model    string         `json:"model"`
	Messages []ModelMessage `json:"messages"`
	Stream   bool           `json:"stream,omitempty"`
	Options  *ModelOptions  `json:"options,omitempty"`
}

// ModelMessage 消息
type ModelMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ModelOptions 模型选项
type ModelOptions struct {
	Temperature float64 `json:"temperature,omitempty"`
	MaxTokens   int     `json:"max_tokens,omitempty"`
}

// ModelResponse 模型响应
type ModelResponse struct {
	ID      string   `json:"id"`
	Choices []Choice `json:"choices"`
	Usage   Usage    `json:"usage"`
}

// Choice 选择
type Choice struct {
	Message      ModelMessage `json:"message"`
	FinishReason string       `json:"finish_reason"`
}

// Usage 使用统计
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// RAGRequest RAG请求
type RAGRequest struct {
	Query    string                 `json:"query"`
	TenantID string                 `json:"tenant_id"`
	History  []ModelMessage         `json:"history,omitempty"`
	Options  map[string]interface{} `json:"options,omitempty"`
}

// RAGResponse RAG响应
type RAGResponse struct {
	Answer   string                   `json:"answer"`
	Sources  []map[string]interface{} `json:"sources,omitempty"`
	Metadata map[string]interface{}   `json:"metadata,omitempty"`
}

// AgentRequest Agent请求
type AgentRequest struct {
	Input          string                 `json:"input"`
	ConversationID string                 `json:"conversation_id"`
	AgentType      string                 `json:"agent_type,omitempty"`
	Tools          []string               `json:"tools,omitempty"`
	Params         map[string]interface{} `json:"params,omitempty"`
}

// AgentResponse Agent响应
type AgentResponse struct {
	Output   string                   `json:"output"`
	Steps    []map[string]interface{} `json:"steps,omitempty"`
	Metadata map[string]interface{}   `json:"metadata,omitempty"`
}

// RetrievalRequest 检索请求
type RetrievalRequest struct {
	Query    string `json:"query"`
	TenantID string `json:"tenant_id"`
	TopK     int    `json:"top_k,omitempty"`
}

// RetrievalResponse 检索响应
type RetrievalResponse struct {
	Results []RetrievalResult `json:"results"`
}

// RetrievalResult 检索结果
type RetrievalResult struct {
	Content  string                 `json:"content"`
	Score    float64                `json:"score"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}
