package application

import (
	"context"
	"fmt"

	"ai-orchestrator/internal/infrastructure"
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
}

// NewDirectChatExecutor 创建直接对话执行器
func NewDirectChatExecutor(circuitBreaker *infrastructure.CircuitBreaker) *DirectChatExecutor {
	return &DirectChatExecutor{
		circuitBreaker: circuitBreaker,
	}
}

// Execute 执行直接对话
func (e *DirectChatExecutor) Execute(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	// 使用熔断器保护
	return e.circuitBreaker.ExecuteWithContext(ctx, func(ctx context.Context) error {
		// 模拟调用 Model Adapter
		// TODO: 实现真实的 LLM 调用

		// 发送响应
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "text",
			Content: fmt.Sprintf("Direct response to: %s", req.Message),
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
}

// NewRAGChatExecutor 创建RAG对话执行器
func NewRAGChatExecutor(circuitBreaker *infrastructure.CircuitBreaker) *RAGChatExecutor {
	return &RAGChatExecutor{
		circuitBreaker: circuitBreaker,
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

		// 2. 模拟检索
		// TODO: 调用 RAG Engine

		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "retrieved",
			Content: "Retrieved 5 documents",
		})

		// 3. 发送生成的回答
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "text",
			Content: fmt.Sprintf("RAG response to: %s (with context)", req.Message),
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
}

// NewAgentChatExecutor 创建Agent对话执行器
func NewAgentChatExecutor(circuitBreaker *infrastructure.CircuitBreaker) *AgentChatExecutor {
	return &AgentChatExecutor{
		circuitBreaker: circuitBreaker,
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

		// 2. 模拟工具调用
		// TODO: 调用 Agent Engine

		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "tool_call",
			Content: "Calling search tool...",
		})

		// 3. 发送最终答案
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "text",
			Content: fmt.Sprintf("Agent response to: %s (with reasoning)", req.Message),
		})

		stream.SendSafe(&ChatResponse{
			TaskID: req.TaskID,
			Type:   "final",
			Done:   true,
		})

		return nil
	})
}
