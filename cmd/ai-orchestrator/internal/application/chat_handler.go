package application

import (
	"context"
	"fmt"
	"time"
)

// ChatHandler 聊天处理器接口（责任链模式）
type ChatHandler interface {
	Handle(ctx context.Context, req *ChatRequest, stream *ChatStream) error
	SetNext(handler ChatHandler)
}

// BaseChatHandler 基础处理器
type BaseChatHandler struct {
	next ChatHandler
}

// SetNext 设置下一个处理器
func (h *BaseChatHandler) SetNext(handler ChatHandler) {
	h.next = handler
}

// ChatRequest 聊天请求
type ChatRequest struct {
	TaskID         string
	UserID         string
	TenantID       string
	ConversationID string
	Message        string
	Mode           string // direct, rag, agent
	Params         map[string]interface{}
	Context        *RequestContext
}

// RequestContext 请求上下文
type RequestContext struct {
	User          interface{}
	ModelID       string
	ModelProvider string
	StartTime     time.Time
	Metadata      map[string]interface{}
}

// ChatStream 流式响应封装
type ChatStream struct {
	ch      chan<- *ChatResponse
	timeout time.Duration
}

// ChatResponse 聊天响应
type ChatResponse struct {
	TaskID   string
	Type     string
	Content  string
	Done     bool
	Error    string
	Metadata map[string]interface{}
}

// NewChatStream 创建流式响应
func NewChatStream(ch chan<- *ChatResponse, timeout time.Duration) *ChatStream {
	return &ChatStream{
		ch:      ch,
		timeout: timeout,
	}
}

// Send 安全发送（带超时）
func (s *ChatStream) Send(response *ChatResponse) error {
	select {
	case s.ch <- response:
		return nil
	case <-time.After(s.timeout):
		return fmt.Errorf("stream send timeout")
	}
}

// SendSafe 安全发送（忽略错误）
func (s *ChatStream) SendSafe(response *ChatResponse) {
	_ = s.Send(response)
}

// --- 具体处理器实现 ---

// LoggingHandler 日志处理器
type LoggingHandler struct {
	BaseChatHandler
}

// NewLoggingHandler 创建日志处理器
func NewLoggingHandler() *LoggingHandler {
	return &LoggingHandler{}
}

// Handle 处理请求
func (h *LoggingHandler) Handle(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	// 记录请求开始
	fmt.Printf("[LOG] Request started: task=%s, user=%s, mode=%s\n", req.TaskID, req.UserID, req.Mode)

	// 初始化上下文
	if req.Context == nil {
		req.Context = &RequestContext{
			StartTime: time.Now(),
			Metadata:  make(map[string]interface{}),
		}
	}

	// 传递给下一个处理器
	var err error
	if h.next != nil {
		err = h.next.Handle(ctx, req, stream)
	}

	// 记录请求完成
	duration := time.Since(req.Context.StartTime)
	if err != nil {
		fmt.Printf("[LOG] Request failed: task=%s, duration=%v, error=%v\n", req.TaskID, duration, err)
	} else {
		fmt.Printf("[LOG] Request completed: task=%s, duration=%v\n", req.TaskID, duration)
	}

	return err
}

// ValidationHandler 验证处理器
type ValidationHandler struct {
	BaseChatHandler
}

// NewValidationHandler 创建验证处理器
func NewValidationHandler() *ValidationHandler {
	return &ValidationHandler{}
}

// Handle 处理请求
func (h *ValidationHandler) Handle(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	// 验证必填字段
	if req.Message == "" {
		return fmt.Errorf("message is required")
	}

	if req.UserID == "" {
		return fmt.Errorf("user_id is required")
	}

	if req.TenantID == "" {
		return fmt.Errorf("tenant_id is required")
	}

	// 验证模式
	validModes := map[string]bool{
		"direct": true,
		"rag":    true,
		"agent":  true,
	}
	if !validModes[req.Mode] {
		return fmt.Errorf("invalid mode: %s", req.Mode)
	}

	// 传递给下一个处理器
	if h.next != nil {
		return h.next.Handle(ctx, req, stream)
	}

	return nil
}

// MetricsHandler 指标处理器
type MetricsHandler struct {
	BaseChatHandler
}

// NewMetricsHandler 创建指标处理器
func NewMetricsHandler() *MetricsHandler {
	return &MetricsHandler{}
}

// Handle 处理请求
func (h *MetricsHandler) Handle(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	startTime := time.Now()

	// 传递给下一个处理器
	var err error
	if h.next != nil {
		err = h.next.Handle(ctx, req, stream)
	}

	// 记录指标
	duration := time.Since(startTime)
	success := err == nil

	// TODO: 发送到Prometheus
	fmt.Printf("[METRICS] task=%s, mode=%s, duration=%v, success=%v\n",
		req.TaskID, req.Mode, duration, success)

	return err
}

// BuildChatPipeline 构建聊天处理管道
func BuildChatPipeline(executionHandler ChatHandler) ChatHandler {
	// 构建责任链：Logging -> Validation -> Metrics -> Execution
	loggingHandler := NewLoggingHandler()
	validationHandler := NewValidationHandler()
	metricsHandler := NewMetricsHandler()

	// 链接处理器
	loggingHandler.SetNext(validationHandler)
	validationHandler.SetNext(metricsHandler)
	metricsHandler.SetNext(executionHandler)

	// 返回头部处理器
	return loggingHandler
}
