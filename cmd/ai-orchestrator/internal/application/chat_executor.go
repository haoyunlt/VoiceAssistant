package application

import (
	"ai-orchestrator/internal/infrastructure"
	"context"
	"fmt"
)

// ChatExecutor 聊天执行器接口（策略模式）
type ChatExecutor interface {
	Execute(ctx context.Context, req *ChatRequest, stream *ChatStream) error
}

// ExecutionHandler 执行处理器（使用策略模式）
type ExecutionHandler struct {
	BaseChatHandler
	executors map[string]ChatExecutor
}

// NewExecutionHandler 创建执行处理器
func NewExecutionHandler(executors map[string]ChatExecutor) *ExecutionHandler {
	return &ExecutionHandler{
		executors: executors,
	}
}

// Handle 处理请求
func (h *ExecutionHandler) Handle(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	// 根据模式选择执行器
	executor, exists := h.executors[req.Mode]
	if !exists {
		return fmt.Errorf("unsupported chat mode: %s", req.Mode)
	}

	// 执行
	return executor.Execute(ctx, req, stream)
}

// --- 具体执行器实现 ---

// DirectChatExecutor 直接对话执行器
type DirectChatExecutor struct {
	circuitBreaker *infrastructure.CircuitBreaker
	aiClient       *infrastructure.AIServiceClient
}

// NewDirectChatExecutor 创建直接对话执行器
func NewDirectChatExecutor(circuitBreaker *infrastructure.CircuitBreaker, aiClient *infrastructure.AIServiceClient) *DirectChatExecutor {
	return &DirectChatExecutor{
		circuitBreaker: circuitBreaker,
		aiClient:       aiClient,
	}
}

// Execute 执行直接对话
func (e *DirectChatExecutor) Execute(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	// 使用熔断器保护
	return e.circuitBreaker.ExecuteWithContext(ctx, func(ctx context.Context) error {
		// 构建历史消息
		messages := []infrastructure.ModelMessage{
			{
				Role:    "user",
				Content: req.Message,
			},
		}

		// 调用模型适配器
		modelReq := &infrastructure.ModelRequest{
			Model:    req.Context.ModelID,
			Messages: messages,
			Stream:   false,
			Options: &infrastructure.ModelOptions{
				Temperature: 0.7,
				MaxTokens:   2000,
			},
		}

		resp, err := e.aiClient.CallModelAdapter(ctx, modelReq)
		if err != nil {
			return fmt.Errorf("call model adapter: %w", err)
		}

		// 提取响应内容
		var content string
		if len(resp.Choices) > 0 {
			content = resp.Choices[0].Message.Content
		}

		// 发送响应
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "text",
			Content: content,
			Metadata: map[string]interface{}{
				"model": req.Context.ModelID,
				"usage": resp.Usage,
			},
		})

		stream.SendSafe(&ChatResponse{
			TaskID: req.TaskID,
			Type:   "final",
			Done:   true,
		})

		return nil
	})
}

// RAGChatExecutor RAG对话执行器
type RAGChatExecutor struct {
	circuitBreaker *infrastructure.CircuitBreaker
	aiClient       *infrastructure.AIServiceClient
}

// NewRAGChatExecutor 创建RAG对话执行器
func NewRAGChatExecutor(circuitBreaker *infrastructure.CircuitBreaker, aiClient *infrastructure.AIServiceClient) *RAGChatExecutor {
	return &RAGChatExecutor{
		circuitBreaker: circuitBreaker,
		aiClient:       aiClient,
	}
}

// Execute 执行RAG对话
func (e *RAGChatExecutor) Execute(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	return e.circuitBreaker.ExecuteWithContext(ctx, func(ctx context.Context) error {
		// 1. 发送检索状态
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "retrieving",
			Content: "Retrieving relevant documents...",
		})

		// 2. 构建历史消息
		history := []infrastructure.ModelMessage{}
		if req.Params != nil {
			if h, ok := req.Params["history"].([]interface{}); ok {
				for _, msg := range h {
					if m, ok := msg.(map[string]interface{}); ok {
						history = append(history, infrastructure.ModelMessage{
							Role:    m["role"].(string),
							Content: m["content"].(string),
						})
					}
				}
			}
		}

		// 3. 调用 RAG Engine
		ragReq := &infrastructure.RAGRequest{
			Query:    req.Message,
			TenantID: req.TenantID,
			History:  history,
			Options: map[string]interface{}{
				"top_k": 5,
			},
		}

		ragResp, err := e.aiClient.CallRAGEngine(ctx, ragReq)
		if err != nil {
			return fmt.Errorf("call rag engine: %w", err)
		}

		// 4. 发送检索完成状态
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "retrieved",
			Content: fmt.Sprintf("Retrieved %d documents", len(ragResp.Sources)),
			Metadata: map[string]interface{}{
				"sources": ragResp.Sources,
			},
		})

		// 5. 发送生成的回答
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "text",
			Content: ragResp.Answer,
			Metadata: map[string]interface{}{
				"sources":  ragResp.Sources,
				"metadata": ragResp.Metadata,
			},
		})

		stream.SendSafe(&ChatResponse{
			TaskID: req.TaskID,
			Type:   "final",
			Done:   true,
		})

		return nil
	})
}

// AgentChatExecutor Agent对话执行器
type AgentChatExecutor struct {
	circuitBreaker *infrastructure.CircuitBreaker
	aiClient       *infrastructure.AIServiceClient
}

// NewAgentChatExecutor 创建Agent对话执行器
func NewAgentChatExecutor(circuitBreaker *infrastructure.CircuitBreaker, aiClient *infrastructure.AIServiceClient) *AgentChatExecutor {
	return &AgentChatExecutor{
		circuitBreaker: circuitBreaker,
		aiClient:       aiClient,
	}
}

// Execute 执行Agent对话
func (e *AgentChatExecutor) Execute(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	return e.circuitBreaker.ExecuteWithContext(ctx, func(ctx context.Context) error {
		// 1. 发送思考过程
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "thinking",
			Content: "Analyzing the task...",
		})

		// 2. 提取工具列表
		tools := []string{"search", "calculator", "knowledge_search"}
		if req.Params != nil {
			if t, ok := req.Params["tools"].([]string); ok {
				tools = t
			}
		}

		// 3. 调用 Agent Engine
		agentReq := &infrastructure.AgentRequest{
			Input:          req.Message,
			ConversationID: req.ConversationID,
			AgentType:      "react", // 默认使用 ReAct
			Tools:          tools,
			Params: map[string]interface{}{
				"tenant_id": req.TenantID,
				"user_id":   req.UserID,
			},
		}

		agentResp, err := e.aiClient.CallAgentEngine(ctx, agentReq)
		if err != nil {
			return fmt.Errorf("call agent engine: %w", err)
		}

		// 4. 发送中间步骤
		if len(agentResp.Steps) > 0 {
			for _, step := range agentResp.Steps {
				stream.SendSafe(&ChatResponse{
					TaskID:   req.TaskID,
					Type:     "tool_call",
					Content:  fmt.Sprintf("%v", step),
					Metadata: step,
				})
			}
		}

		// 5. 发送最终答案
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "text",
			Content: agentResp.Output,
			Metadata: map[string]interface{}{
				"steps":    agentResp.Steps,
				"metadata": agentResp.Metadata,
			},
		})

		stream.SendSafe(&ChatResponse{
			TaskID: req.TaskID,
			Type:   "final",
			Done:   true,
		})

		return nil
	})
}
