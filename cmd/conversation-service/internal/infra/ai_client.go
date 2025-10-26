package infra

import (
	"context"
	"fmt"
	"io"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "voiceassistant/api/proto/ai-orchestrator/v1"
	"voiceassistant/cmd/conversation-service/internal/domain"
)

// AIClient AI Orchestrator 客户端
type AIClient struct {
	conn   *grpc.ClientConn
	client pb.OrchestratorClient
	logger *log.Helper
	config *AIClientConfig
}

// AIClientConfig AI 客户端配置
type AIClientConfig struct {
	// 服务地址
	Address string

	// 连接超时
	ConnectTimeout time.Duration

	// 请求超时
	RequestTimeout time.Duration

	// 重试次数
	MaxRetries int

	// 默认配置
	DefaultConfig *ProcessConfig
}

// ProcessConfig 处理配置
type ProcessConfig struct {
	Model       string
	Temperature float32
	MaxTokens   int32
	Stream      bool
	EnableRAG   bool
	EnableAgent bool
}

// NewAIClient 创建 AI 客户端
func NewAIClient(config *AIClientConfig, logger log.Logger) (*AIClient, error) {
	// 创建 gRPC 连接
	ctx, cancel := context.WithTimeout(context.Background(), config.ConnectTimeout)
	defer cancel()

	conn, err := grpc.DialContext(ctx, config.Address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to AI orchestrator: %w", err)
	}

	client := pb.NewOrchestratorClient(conn)

	return &AIClient{
		conn:   conn,
		client: client,
		logger: log.NewHelper(logger),
		config: config,
	}, nil
}

// Close 关闭连接
func (c *AIClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// ========================================
// 消息处理（非流式）
// ========================================

// ProcessMessage 处理消息（非流式）
func (c *AIClient) ProcessMessage(ctx context.Context, req *ProcessRequest) (*ProcessResponse, error) {
	// 设置超时
	ctx, cancel := context.WithTimeout(ctx, c.config.RequestTimeout)
	defer cancel()

	// 构建请求
	pbReq := &pb.ProcessMessageRequest{
		ConversationId: req.ConversationID,
		Message:        req.Message,
		UserId:         req.UserID,
		TenantId:       req.TenantID,
		Context:        c.buildContext(req.Context),
		Mode:           c.convertMode(req.Mode),
		Config:         c.buildConfig(req.Config),
	}

	// 调用 gRPC
	resp, err := c.client.ProcessMessage(ctx, pbReq)
	if err != nil {
		return nil, fmt.Errorf("failed to process message: %w", err)
	}

	// 转换响应
	return c.convertResponse(resp), nil
}

// ========================================
// 消息处理（流式）
// ========================================

// ProcessMessageStream 处理消息（流式）
func (c *AIClient) ProcessMessageStream(ctx context.Context, req *ProcessRequest) (<-chan *StreamChunk, <-chan error) {
	chunkChan := make(chan *StreamChunk, 100)
	errChan := make(chan error, 1)

	go func() {
		defer close(chunkChan)
		defer close(errChan)

		// 构建请求
		pbReq := &pb.ProcessMessageRequest{
			ConversationId: req.ConversationID,
			Message:        req.Message,
			UserId:         req.UserID,
			TenantId:       req.TenantID,
			Context:        c.buildContext(req.Context),
			Mode:           c.convertMode(req.Mode),
			Config:         c.buildConfig(req.Config),
		}

		// 调用流式 gRPC
		stream, err := c.client.ProcessMessageStream(ctx, pbReq)
		if err != nil {
			errChan <- fmt.Errorf("failed to start stream: %w", err)
			return
		}

		// 接收流式响应
		for {
			resp, err := stream.Recv()
			if err == io.EOF {
				// 流结束
				break
			}
			if err != nil {
				errChan <- fmt.Errorf("failed to receive stream: %w", err)
				return
			}

			// 转换并发送 chunk
			chunk := c.convertStreamResponse(resp)
			select {
			case chunkChan <- chunk:
			case <-ctx.Done():
				errChan <- ctx.Err()
				return
			}
		}
	}()

	return chunkChan, errChan
}

// ========================================
// 工作流执行
// ========================================

// ExecuteWorkflow 执行工作流
func (c *AIClient) ExecuteWorkflow(ctx context.Context, req *WorkflowRequest) (*WorkflowResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, c.config.RequestTimeout)
	defer cancel()

	pbReq := &pb.ExecuteWorkflowRequest{
		WorkflowId:         req.WorkflowID,
		WorkflowDefinition: req.WorkflowDefinition,
		Inputs:             req.Inputs,
		UserId:             req.UserID,
		TenantId:           req.TenantID,
	}

	resp, err := c.client.ExecuteWorkflow(ctx, pbReq)
	if err != nil {
		return nil, fmt.Errorf("failed to execute workflow: %w", err)
	}

	return c.convertWorkflowResponse(resp), nil
}

// ========================================
// 任务管理
// ========================================

// CancelTask 取消任务
func (c *AIClient) CancelTask(ctx context.Context, taskID string, userID string) error {
	ctx, cancel := context.WithTimeout(ctx, c.config.RequestTimeout)
	defer cancel()

	req := &pb.CancelTaskRequest{
		TaskId: taskID,
		UserId: userID,
	}

	resp, err := c.client.CancelTask(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to cancel task: %w", err)
	}

	if !resp.Success {
		return fmt.Errorf("cancel task failed: %s", resp.Message)
	}

	return nil
}

// GetTaskStatus 获取任务状态
func (c *AIClient) GetTaskStatus(ctx context.Context, taskID string, userID string) (*TaskStatus, error) {
	ctx, cancel := context.WithTimeout(ctx, c.config.RequestTimeout)
	defer cancel()

	req := &pb.GetTaskStatusRequest{
		TaskId: taskID,
		UserId: userID,
	}

	resp, err := c.client.GetTaskStatus(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to get task status: %w", err)
	}

	return c.convertTaskStatus(resp), nil
}

// ========================================
// 辅助方法
// ========================================

// buildContext 构建上下文
func (c *AIClient) buildContext(context *domain.ConversationContext) *pb.MessageContext {
	if context == nil {
		return nil
	}

	pbContext := &pb.MessageContext{
		SystemPrompt:    context.SystemPrompt,
		UserPreferences: make(map[string]string),
		Metadata:        context.Metadata,
	}

	// 转换历史消息
	for _, msg := range context.Messages {
		pbContext.History = append(pbContext.History, &pb.HistoryMessage{
			Role:    msg.Role,
			Content: msg.Content,
		})
	}

	return pbContext
}

// convertMode 转换处理模式
func (c *AIClient) convertMode(mode string) pb.ProcessMode {
	switch mode {
	case "rag":
		return pb.ProcessMode_MODE_RAG
	case "agent":
		return pb.ProcessMode_MODE_AGENT
	case "chat":
		return pb.ProcessMode_MODE_CHAT
	case "voice":
		return pb.ProcessMode_MODE_VOICE
	case "multimodal":
		return pb.ProcessMode_MODE_MULTIMODAL
	default:
		return pb.ProcessMode_MODE_AUTO
	}
}

// buildConfig 构建配置
func (c *AIClient) buildConfig(config *ProcessConfig) *pb.ProcessConfig {
	if config == nil {
		config = c.config.DefaultConfig
	}

	return &pb.ProcessConfig{
		Model:       config.Model,
		Temperature: config.Temperature,
		MaxTokens:   config.MaxTokens,
		Stream:      config.Stream,
		EnableRag:   config.EnableRAG,
	}
}

// convertResponse 转换响应
func (c *AIClient) convertResponse(resp *pb.ProcessMessageResponse) *ProcessResponse {
	return &ProcessResponse{
		TaskID:     resp.TaskId,
		Reply:      resp.Reply,
		Engine:     resp.Engine,
		Citations:  c.convertCitations(resp.Citations),
		ToolCalls:  c.convertToolCalls(resp.ToolCalls),
		Metadata:   resp.Metadata,
		TokenUsage: c.convertTokenUsage(resp.TokenUsage),
		DurationMs: resp.DurationMs,
	}
}

// convertStreamResponse 转换流式响应
func (c *AIClient) convertStreamResponse(resp *pb.ProcessMessageStreamResponse) *StreamChunk {
	return &StreamChunk{
		TaskID:     resp.TaskId,
		EventType:  resp.EventType.String(),
		Delta:      resp.Delta,
		Citations:  c.convertCitations(resp.Citations),
		ToolCall:   c.convertToolCall(resp.ToolCall),
		Metadata:   resp.Metadata,
		Finished:   resp.Finished,
		FinalStats: c.convertFinalStats(resp.FinalStats),
	}
}

// convertCitations 转换引用
func (c *AIClient) convertCitations(citations []*pb.Citation) []Citation {
	result := make([]Citation, len(citations))
	for i, citation := range citations {
		result[i] = Citation{
			ID:         citation.Id,
			DocumentID: citation.DocumentId,
			Title:      citation.Title,
			Snippet:    citation.Snippet,
			Score:      citation.Score,
			Metadata:   citation.Metadata,
		}
	}
	return result
}

// convertToolCalls 转换工具调用列表
func (c *AIClient) convertToolCalls(toolCalls []*pb.ToolCall) []ToolCall {
	result := make([]ToolCall, len(toolCalls))
	for i, tc := range toolCalls {
		result[i] = c.convertToolCall(tc)
	}
	return result
}

// convertToolCall 转换工具调用
func (c *AIClient) convertToolCall(toolCall *pb.ToolCall) ToolCall {
	if toolCall == nil {
		return ToolCall{}
	}

	return ToolCall{
		ID:         toolCall.Id,
		Tool:       toolCall.Tool,
		Arguments:  toolCall.Arguments,
		Result:     toolCall.Result,
		Status:     toolCall.Status,
		Error:      toolCall.Error,
		DurationMs: toolCall.DurationMs,
	}
}

// convertTokenUsage 转换 Token 使用量
func (c *AIClient) convertTokenUsage(usage *pb.TokenUsage) *TokenUsage {
	if usage == nil {
		return nil
	}

	return &TokenUsage{
		PromptTokens:     usage.PromptTokens,
		CompletionTokens: usage.CompletionTokens,
		TotalTokens:      usage.TotalTokens,
		CostUSD:          usage.CostUsd,
	}
}

// convertFinalStats 转换最终统计
func (c *AIClient) convertFinalStats(stats *pb.FinalStats) *FinalStats {
	if stats == nil {
		return nil
	}

	return &FinalStats{
		TokenUsage:     c.convertTokenUsage(stats.TokenUsage),
		DurationMs:     stats.DurationMs,
		Engine:         stats.Engine,
		ToolCallsCount: stats.ToolCallsCount,
	}
}

// convertWorkflowResponse 转换工作流响应
func (c *AIClient) convertWorkflowResponse(resp *pb.ExecuteWorkflowResponse) *WorkflowResponse {
	return &WorkflowResponse{
		TaskID:     resp.TaskId,
		InstanceID: resp.InstanceId,
		Status:     resp.Status.String(),
		Outputs:    resp.Outputs,
		Metadata:   resp.Metadata,
	}
}

// convertTaskStatus 转换任务状态
func (c *AIClient) convertTaskStatus(resp *pb.GetTaskStatusResponse) *TaskStatus {
	return &TaskStatus{
		TaskID:      resp.TaskId,
		Status:      resp.Status.String(),
		Progress:    resp.Progress,
		CurrentStep: resp.CurrentStep,
		Metadata:    resp.Metadata,
	}
}

// ========================================
// 请求/响应类型定义
// ========================================

// ProcessRequest 处理请求
type ProcessRequest struct {
	ConversationID string
	Message        string
	UserID         string
	TenantID       string
	Context        *domain.ConversationContext
	Mode           string
	Config         *ProcessConfig
}

// ProcessResponse 处理响应
type ProcessResponse struct {
	TaskID     string
	Reply      string
	Engine     string
	Citations  []Citation
	ToolCalls  []ToolCall
	Metadata   map[string]string
	TokenUsage *TokenUsage
	DurationMs int64
}

// StreamChunk 流式响应块
type StreamChunk struct {
	TaskID     string
	EventType  string
	Delta      string
	Citations  []Citation
	ToolCall   ToolCall
	Metadata   map[string]string
	Finished   bool
	FinalStats *FinalStats
}

// Citation 引用
type Citation struct {
	ID         string
	DocumentID string
	Title      string
	Snippet    string
	Score      float32
	Metadata   map[string]string
}

// ToolCall 工具调用
type ToolCall struct {
	ID         string
	Tool       string
	Arguments  string
	Result     string
	Status     string
	Error      string
	DurationMs int64
}

// TokenUsage Token 使用量
type TokenUsage struct {
	PromptTokens     int32
	CompletionTokens int32
	TotalTokens      int32
	CostUSD          float32
}

// FinalStats 最终统计
type FinalStats struct {
	TokenUsage     *TokenUsage
	DurationMs     int64
	Engine         string
	ToolCallsCount int32
}

// WorkflowRequest 工作流请求
type WorkflowRequest struct {
	WorkflowID         string
	WorkflowDefinition string
	Inputs             map[string]string
	UserID             string
	TenantID           string
}

// WorkflowResponse 工作流响应
type WorkflowResponse struct {
	TaskID     string
	InstanceID string
	Status     string
	Outputs    map[string]string
	Metadata   map[string]string
}

// TaskStatus 任务状态
type TaskStatus struct {
	TaskID      string
	Status      string
	Progress    int32
	CurrentStep string
	Metadata    map[string]string
}
