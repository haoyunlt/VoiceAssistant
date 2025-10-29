package infrastructure

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"time"

	"github.com/sony/gobreaker"

	"voicehelper/pkg/config"
)

// AIServiceClient AI服务客户端
type AIServiceClient struct {
	httpClient      *http.Client
	baseURLs        map[string]string
	circuitBreakers map[string]*gobreaker.CircuitBreaker
	maxRetries      int
	retryDelay      time.Duration
}

// NewAIServiceClient 创建AI服务客户端
// Deprecated: 使用 NewAIServiceClientFromEnv 或 NewAIServiceClientFromYAML 代替
func NewAIServiceClient() *AIServiceClient {
	// 尝试从配置文件读取，失败则回退到硬编码（仅用于向后兼容）
	client, err := NewAIServiceClientFromEnv()
	if err != nil {
		// 回退到硬编码地址（向后兼容）
		return NewAIServiceClientFromConfig(map[string]string{
			"model-adapter":     "http://localhost:8005",
			"rag-engine":        "http://localhost:8006",
			"agent-engine":      "http://localhost:8003",
			"retrieval-service": "http://localhost:8012",
		}, 60*time.Second)
	}
	return client
}

// NewAIServiceClientFromConfig 从配置创建AI服务客户端（推荐）
func NewAIServiceClientFromConfig(serviceURLs map[string]string, timeout time.Duration) *AIServiceClient {
	if timeout == 0 {
		timeout = 60 * time.Second
	}
	client := &AIServiceClient{
		httpClient: &http.Client{
			Timeout: timeout,
		},
		baseURLs:        serviceURLs,
		circuitBreakers: make(map[string]*gobreaker.CircuitBreaker),
		maxRetries:      3,
		retryDelay:      100 * time.Millisecond,
	}

	// 为每个服务初始化熔断器
	for service := range client.baseURLs {
		client.circuitBreakers[service] = client.createCircuitBreaker(service)
	}

	return client
}

// NewAIServiceClientFromYAML 从 YAML 配置文件创建客户端（推荐）
func NewAIServiceClientFromYAML(configPath string) (*AIServiceClient, error) {
	// 加载配置
	cfg, err := config.LoadServicesConfig(configPath)
	if err != nil {
		return nil, fmt.Errorf("load services config: %w", err)
	}

	// 获取所有 HTTP 服务 URL
	baseURLs := cfg.GetHTTPServiceURLs()

	// 使用默认超时（60s）
	return NewAIServiceClientFromConfig(baseURLs, 60*time.Second), nil
}

// NewAIServiceClientFromEnv 从环境变量或默认路径创建客户端（推荐）
func NewAIServiceClientFromEnv() (*AIServiceClient, error) {
	cfg, err := config.LoadServicesConfigFromEnv()
	if err != nil {
		return nil, fmt.Errorf("load services config from env: %w", err)
	}

	baseURLs := cfg.GetHTTPServiceURLs()
	return NewAIServiceClientFromConfig(baseURLs, 60*time.Second), nil
}

// createCircuitBreaker 创建熔断器
func (c *AIServiceClient) createCircuitBreaker(service string) *gobreaker.CircuitBreaker {
	settings := gobreaker.Settings{
		Name:        service,
		MaxRequests: 3,                // 半开状态下最大请求数
		Interval:    10 * time.Second, // 统计周期
		Timeout:     30 * time.Second, // 熔断器开启后等待时间
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			// 失败率 >= 60% 且请求数 >= 5 时触发熔断
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 5 && failureRatio >= 0.6
		},
	}
	return gobreaker.NewCircuitBreaker(settings)
}

// callWithRetry 带重试的HTTP调用
func (c *AIServiceClient) callWithRetry(ctx context.Context, service, url string, reqBody []byte) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// 指数退避
			backoff := time.Duration(math.Pow(2, float64(attempt-1))) * c.retryDelay
			if backoff > 5*time.Second {
				backoff = 5 * time.Second
			}

			select {
			case <-time.After(backoff):
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}

		// 通过熔断器执行调用
		cb := c.circuitBreakers[service]
		result, err := cb.Execute(func() (interface{}, error) {
			return c.doHTTPCall(ctx, url, reqBody)
		})

		if err == nil {
			return result.([]byte), nil
		}

		lastErr = err

		// 判断是否应该重试
		if !c.shouldRetry(err) {
			break
		}
	}

	return nil, fmt.Errorf("failed after %d attempts: %w", c.maxRetries+1, lastErr)
}

// doHTTPCall 执行实际的HTTP调用
func (c *AIServiceClient) doHTTPCall(ctx context.Context, url string, reqBody []byte) ([]byte, error) {
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	return respBody, nil
}

// shouldRetry 判断错误是否应该重试
func (c *AIServiceClient) shouldRetry(err error) bool {
	// 超时错误、临时错误应该重试
	if err == context.DeadlineExceeded || err == context.Canceled {
		return false
	}
	// 熔断器开启时不重试
	if err == gobreaker.ErrOpenState || err == gobreaker.ErrTooManyRequests {
		return false
	}
	// 其他错误默认重试
	return true
}

// CallModelAdapter 调用模型适配器
func (c *AIServiceClient) CallModelAdapter(ctx context.Context, req *ModelRequest) (*ModelResponse, error) {
	url := fmt.Sprintf("%s/v1/chat/completions", c.baseURLs["model-adapter"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	// 使用带重试和熔断的调用
	respBody, err := c.callWithRetry(ctx, "model-adapter", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result ModelResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
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

	// 使用带重试和熔断的调用
	respBody, err := c.callWithRetry(ctx, "rag-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result RAGResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
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

	// 使用带重试和熔断的调用
	respBody, err := c.callWithRetry(ctx, "agent-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result AgentResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
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

	// 使用带重试和熔断的调用
	respBody, err := c.callWithRetry(ctx, "retrieval-service", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result RetrievalResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// ============ Multi-Agent 协作相关方法 ============

// MultiAgentCollaborate 调用Multi-Agent协作
func (c *AIServiceClient) MultiAgentCollaborate(ctx context.Context, req *MultiAgentCollaborateRequest) (*MultiAgentCollaborateResponse, error) {
	url := fmt.Sprintf("%s/multi-agent/collaborate", c.baseURLs["agent-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	respBody, err := c.callWithRetry(ctx, "agent-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result MultiAgentCollaborateResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// RegisterAgent 注册Agent
func (c *AIServiceClient) RegisterAgent(ctx context.Context, req *RegisterAgentRequest) (*RegisterAgentResponse, error) {
	url := fmt.Sprintf("%s/multi-agent/agents/register", c.baseURLs["agent-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	respBody, err := c.callWithRetry(ctx, "agent-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result RegisterAgentResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// ListAgents 列出所有Agents
func (c *AIServiceClient) ListAgents(ctx context.Context, tenantID, userID string) (*ListAgentsResponse, error) {
	url := fmt.Sprintf("%s/multi-agent/agents?tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result ListAgentsResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// UnregisterAgent 注销Agent
func (c *AIServiceClient) UnregisterAgent(ctx context.Context, agentID, tenantID, userID string) error {
	url := fmt.Sprintf("%s/multi-agent/agents/%s?tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], agentID, tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "DELETE", url, nil)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// GetMultiAgentStats 获取Multi-Agent统计信息
func (c *AIServiceClient) GetMultiAgentStats(ctx context.Context, tenantID, userID string) (*MultiAgentStatsResponse, error) {
	url := fmt.Sprintf("%s/multi-agent/stats?tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result MultiAgentStatsResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// ============ Self-RAG 相关方法 ============

// SelfRAGQuery 执行Self-RAG查询
func (c *AIServiceClient) SelfRAGQuery(ctx context.Context, req *SelfRAGQueryRequest) (*SelfRAGQueryResponse, error) {
	url := fmt.Sprintf("%s/self-rag/query", c.baseURLs["agent-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	respBody, err := c.callWithRetry(ctx, "agent-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result SelfRAGQueryResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// GetSelfRAGStats 获取Self-RAG统计信息
func (c *AIServiceClient) GetSelfRAGStats(ctx context.Context, tenantID, userID string) (*SelfRAGStatsResponse, error) {
	url := fmt.Sprintf("%s/self-rag/stats?tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result SelfRAGStatsResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// ============ Smart Memory 相关方法 ============

// AddMemory 添加记忆
func (c *AIServiceClient) AddMemory(ctx context.Context, req *AddMemoryRequest) (*AddMemoryResponse, error) {
	url := fmt.Sprintf("%s/smart-memory/add", c.baseURLs["agent-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	respBody, err := c.callWithRetry(ctx, "agent-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result AddMemoryResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// RetrieveMemory 检索记忆
func (c *AIServiceClient) RetrieveMemory(ctx context.Context, req *RetrieveMemoryRequest) (*RetrieveMemoryResponse, error) {
	url := fmt.Sprintf("%s/smart-memory/retrieve", c.baseURLs["agent-engine"])

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	respBody, err := c.callWithRetry(ctx, "agent-engine", url, reqBody)
	if err != nil {
		return nil, err
	}

	var result RetrieveMemoryResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// CompressMemory 压缩记忆
func (c *AIServiceClient) CompressMemory(ctx context.Context, tier, tenantID, userID string) (*CompressMemoryResponse, error) {
	url := fmt.Sprintf("%s/smart-memory/compress?tier=%s&tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], tier, tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result CompressMemoryResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result, nil
}

// MaintainMemory 维护记忆
func (c *AIServiceClient) MaintainMemory(ctx context.Context, tenantID, userID string) (*MemoryStatsResponse, error) {
	url := fmt.Sprintf("%s/smart-memory/maintain?tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	// 响应包含 message 和 stats
	var result struct {
		Message string              `json:"message"`
		Stats   MemoryStatsResponse `json:"stats"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &result.Stats, nil
}

// GetMemoryStats 获取记忆统计信息
func (c *AIServiceClient) GetMemoryStats(ctx context.Context, tenantID, userID string) (*MemoryStatsResponse, error) {
	url := fmt.Sprintf("%s/smart-memory/stats?tenant_id=%s&user_id=%s",
		c.baseURLs["agent-engine"], tenantID, userID)

	httpReq, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result MemoryStatsResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
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

// ============ Multi-Agent 协作相关 ============

// MultiAgentCollaborateRequest Multi-Agent协作请求
type MultiAgentCollaborateRequest struct {
	Task     string   `json:"task"`
	Mode     string   `json:"mode"`                // sequential/parallel/debate/voting/hierarchical
	AgentIDs []string `json:"agent_ids,omitempty"` // 参与的agent ID列表
	Priority int      `json:"priority,omitempty"`  // 任务优先级（1-10）
	TenantID string   `json:"tenant_id,omitempty"`
	UserID   string   `json:"user_id,omitempty"`
}

// MultiAgentCollaborateResponse Multi-Agent协作响应
type MultiAgentCollaborateResponse struct {
	Task           string                 `json:"task"`
	Mode           string                 `json:"mode"`
	AgentsInvolved []string               `json:"agents_involved"`
	FinalResult    interface{}            `json:"final_result"`
	QualityScore   float64                `json:"quality_score,omitempty"`
	CompletionTime float64                `json:"completion_time"`
	Status         string                 `json:"status"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
}

// RegisterAgentRequest 注册Agent请求
type RegisterAgentRequest struct {
	AgentID  string   `json:"agent_id"`
	Role     string   `json:"role"` // coordinator/researcher/planner/executor/reviewer
	Tools    []string `json:"tools,omitempty"`
	TenantID string   `json:"tenant_id,omitempty"`
	UserID   string   `json:"user_id,omitempty"`
}

// RegisterAgentResponse 注册Agent响应
type RegisterAgentResponse struct {
	AgentID string `json:"agent_id"`
	Role    string `json:"role"`
	Message string `json:"message"`
}

// ListAgentsResponse 列出Agents响应
type ListAgentsResponse struct {
	Agents []AgentInfo `json:"agents"`
	Count  int         `json:"count"`
}

// AgentInfo Agent信息
type AgentInfo struct {
	AgentID           string `json:"agent_id"`
	Role              string `json:"role"`
	ToolsCount        int    `json:"tools_count"`
	ProcessedMessages int    `json:"processed_messages"`
}

// MultiAgentStatsResponse Multi-Agent统计响应
type MultiAgentStatsResponse struct {
	TotalTasks              int            `json:"total_tasks"`
	CompletedTasks          int            `json:"completed_tasks"`
	FailedTasks             int            `json:"failed_tasks"`
	SuccessRate             float64        `json:"success_rate"`
	AvgCompletionTime       float64        `json:"avg_completion_time"`
	CollaborationQualityAvg float64        `json:"collaboration_quality_avg"`
	ActiveAgents            int            `json:"active_agents"`
	AgentLoad               map[string]int `json:"agent_load"`
}

// ============ Self-RAG 相关 ============

// SelfRAGQueryRequest Self-RAG查询请求
type SelfRAGQueryRequest struct {
	Query           string                 `json:"query"`
	Mode            string                 `json:"mode,omitempty"` // standard/adaptive/strict/fast
	Context         map[string]interface{} `json:"context,omitempty"`
	EnableCitations bool                   `json:"enable_citations,omitempty"`
	MaxRefinements  int                    `json:"max_refinements,omitempty"`
	TenantID        string                 `json:"tenant_id,omitempty"`
	UserID          string                 `json:"user_id,omitempty"`
}

// SelfRAGQueryResponse Self-RAG查询响应
type SelfRAGQueryResponse struct {
	Query              string                 `json:"query"`
	Answer             string                 `json:"answer"`
	Confidence         float64                `json:"confidence"`
	RetrievalStrategy  string                 `json:"retrieval_strategy"`
	RefinementCount    int                    `json:"refinement_count"`
	HallucinationLevel string                 `json:"hallucination_level,omitempty"`
	IsGrounded         bool                   `json:"is_grounded,omitempty"`
	Citations          []Citation             `json:"citations,omitempty"`
	Metadata           map[string]interface{} `json:"metadata,omitempty"`
}

// Citation 引用
type Citation struct {
	Source         string  `json:"source"`
	Content        string  `json:"content"`
	URL            string  `json:"url,omitempty"`
	RelevanceScore float64 `json:"relevance_score"`
}

// SelfRAGStatsResponse Self-RAG统计响应
type SelfRAGStatsResponse struct {
	TotalQueries          int     `json:"total_queries"`
	RefinementTriggered   int     `json:"refinement_triggered"`
	HallucinationDetected int     `json:"hallucination_detected"`
	QueryRewrites         int     `json:"query_rewrites"`
	RefinementRate        float64 `json:"refinement_rate"`
	HallucinationRate     float64 `json:"hallucination_rate"`
	CacheHitRate          float64 `json:"cache_hit_rate"`
}

// ============ Smart Memory 相关 ============

// AddMemoryRequest 添加记忆请求
type AddMemoryRequest struct {
	Content    string                 `json:"content"`
	Tier       string                 `json:"tier,omitempty"`       // working/short_term/long_term
	Importance float64                `json:"importance,omitempty"` // 0-1
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
	TenantID   string                 `json:"tenant_id,omitempty"`
	UserID     string                 `json:"user_id,omitempty"`
}

// AddMemoryResponse 添加记忆响应
type AddMemoryResponse struct {
	MemoryID   string  `json:"memory_id"`
	Tier       string  `json:"tier"`
	Importance float64 `json:"importance"`
	Message    string  `json:"message"`
}

// RetrieveMemoryRequest 检索记忆请求
type RetrieveMemoryRequest struct {
	Query         string  `json:"query"`
	TopK          int     `json:"top_k,omitempty"`
	TierFilter    string  `json:"tier_filter,omitempty"`
	MinImportance float64 `json:"min_importance,omitempty"`
	TenantID      string  `json:"tenant_id,omitempty"`
	UserID        string  `json:"user_id,omitempty"`
}

// RetrieveMemoryResponse 检索记忆响应
type RetrieveMemoryResponse struct {
	Memories []MemoryItem `json:"memories"`
	Count    int          `json:"count"`
}

// MemoryItem 记忆项
type MemoryItem struct {
	MemoryID          string  `json:"memory_id"`
	Content           string  `json:"content"`
	Tier              string  `json:"tier"`
	Importance        float64 `json:"importance"`
	CurrentImportance float64 `json:"current_importance"`
	AccessCount       int     `json:"access_count"`
	CreatedAt         string  `json:"created_at"`
	LastAccessed      string  `json:"last_accessed"`
}

// CompressMemoryResponse 压缩记忆响应
type CompressMemoryResponse struct {
	Summary         string  `json:"summary"`
	OriginalCount   int     `json:"original_count"`
	CompressedRatio float64 `json:"compressed_ratio"`
	Message         string  `json:"message"`
}

// MemoryStatsResponse 记忆统计响应
type MemoryStatsResponse struct {
	TotalAdded      int            `json:"total_added"`
	TotalForgotten  int            `json:"total_forgotten"`
	TotalPromoted   int            `json:"total_promoted"`
	TotalDemoted    int            `json:"total_demoted"`
	TotalCompressed int            `json:"total_compressed"`
	MemoryCounts    map[string]int `json:"memory_counts"`
	TotalMemories   int            `json:"total_memories"`
	AvgImportance   float64        `json:"avg_importance"`
}
