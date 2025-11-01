package server

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"voicehelper/cmd/ai-orchestrator/internal/biz"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/gorilla/mux"
)

// StreamHandler SSE流式处理器
type StreamHandler struct {
	taskUC *biz.TaskUsecase
	logger *log.Helper
}

// NewStreamHandler 创建流式处理器
func NewStreamHandler(taskUC *biz.TaskUsecase, logger log.Logger) *StreamHandler {
	return &StreamHandler{
		taskUC: taskUC,
		logger: log.NewHelper(logger),
	}
}

// CreateTaskRequest 创建任务请求
type CreateTaskRequest struct {
	TaskType       string                 `json:"task_type"`
	ConversationID string                 `json:"conversation_id"`
	UserID         string                 `json:"user_id"`
	TenantID       string                 `json:"tenant_id"`
	Content        string                 `json:"content"`
	Context        map[string]interface{} `json:"context"`
	Options        map[string]interface{} `json:"options"`
	Stream         bool                   `json:"stream"` // 是否流式
}

// TaskResponse 任务响应
type TaskResponse struct {
	TaskID  string `json:"task_id"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

// RegisterStreamRoutes 注册流式路由
func RegisterStreamRoutes(router *mux.Router, handler *StreamHandler) {
	router.HandleFunc("/v1/chat", handler.HandleChat).Methods("POST")
	router.HandleFunc("/v1/chat/stream", handler.HandleChatStream).Methods("POST")
}

// HandleChat 处理普通聊天请求
func (h *StreamHandler) HandleChat(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// 解析请求
	var req CreateTaskRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// 验证参数
	if req.Content == "" || req.UserID == "" || req.TenantID == "" {
		h.respondError(w, http.StatusBadRequest, "Missing required fields")
		return
	}

	// 创建任务输入
	input := &domain.TaskInput{
		Content: req.Content,
		Context: req.Context,
		Options: req.Options,
	}

	// 判断是否流式
	if req.Stream {
		h.handleStreamRequest(w, r, req, input)
		return
	}

	// 非流式：创建并同步执行
	taskType := h.inferTaskType(req.TaskType)
	task, output, err := h.taskUC.CreateAndExecuteTask(
		ctx,
		taskType,
		req.ConversationID,
		req.UserID,
		req.TenantID,
		input,
	)

	if err != nil {
		h.logger.Errorf("failed to execute task: %v", err)
		h.respondError(w, http.StatusInternalServerError, fmt.Sprintf("Task execution failed: %v", err))
		return
	}

	// 返回结果
	response := map[string]interface{}{
		"task_id": task.ID,
		"status":  task.Status,
		"output":  output.Content,
		"metadata": map[string]interface{}{
			"tokens_used": output.TokensUsed,
			"cost_usd":    output.CostUSD,
			"model":       output.Model,
			"latency_ms":  output.LatencyMS,
		},
	}

	h.respondJSON(w, http.StatusOK, response)
}

// HandleChatStream 处理流式聊天请求
func (h *StreamHandler) HandleChatStream(w http.ResponseWriter, r *http.Request) {
	// 解析请求
	var req CreateTaskRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// 验证参数
	if req.Content == "" || req.UserID == "" || req.TenantID == "" {
		h.respondError(w, http.StatusBadRequest, "Missing required fields")
		return
	}

	// 创建任务输入
	input := &domain.TaskInput{
		Content: req.Content,
		Context: req.Context,
		Options: req.Options,
	}

	h.handleStreamRequest(w, r, req, input)
}

// handleStreamRequest 处理流式请求
func (h *StreamHandler) handleStreamRequest(
	w http.ResponseWriter,
	r *http.Request,
	req CreateTaskRequest,
	input *domain.TaskInput,
) {
	ctx := r.Context()

	// 生成或获取幂等键
	idempotencyKey := r.Header.Get("X-Idempotency-Key")
	if idempotencyKey == "" && req.Content != "" {
		// 自动生成幂等键
		idempotencyKey = biz.GenerateIdempotencyKeyFromRequest(
			req.UserID,
			req.TenantID,
			req.ConversationID,
			req.Content,
		)
	}

	// 创建任务（异步执行，带幂等性）
	taskType := h.inferTaskType(req.TaskType)
	task, err := h.taskUC.CreateTaskAsync(
		ctx,
		taskType,
		req.ConversationID,
		req.UserID,
		req.TenantID,
		input,
		idempotencyKey,
	)

	if err != nil {
		h.logger.Errorf("failed to create task: %v", err)
		h.respondError(w, http.StatusInternalServerError, fmt.Sprintf("Task creation failed: %v", err))
		return
	}

	// 设置SSE响应头
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no") // 禁用Nginx缓冲

	flusher, ok := w.(http.Flusher)
	if !ok {
		h.respondError(w, http.StatusInternalServerError, "Streaming not supported")
		return
	}

	// 发送任务ID
	h.sendSSE(w, flusher, &domain.StreamEvent{
		Type:    "task_created",
		Content: task.ID,
		Metadata: map[string]interface{}{
			"task_id": task.ID,
			"status":  "pending",
		},
		Timestamp: time.Now(),
	})

	// 创建流式通道
	stream := make(chan *domain.StreamEvent, 100)

	// 启动执行
	go func() {
		err := h.taskUC.ExecuteTaskStream(ctx, task.ID, stream)
		if err != nil {
			h.logger.Errorf("stream execution failed: %v", err)
		}
	}()

	// 发送流式事件
	for event := range stream {
		h.sendSSE(w, flusher, event)

		// 如果是最终事件，结束
		if event.Done {
			break
		}
	}

	// 发送完成标记
	fmt.Fprintf(w, "data: [DONE]\n\n")
	flusher.Flush()
}

// sendSSE 发送SSE事件
func (h *StreamHandler) sendSSE(w http.ResponseWriter, flusher http.Flusher, event *domain.StreamEvent) {
	data, err := json.Marshal(event)
	if err != nil {
		h.logger.Errorf("failed to marshal event: %v", err)
		return
	}

	fmt.Fprintf(w, "data: %s\n\n", string(data))
	flusher.Flush()
}

// inferTaskType 推断任务类型
func (h *StreamHandler) inferTaskType(taskTypeStr string) domain.TaskType {
	switch taskTypeStr {
	case "rag", "knowledge":
		return domain.TaskTypeRAG
	case "agent", "tool":
		return domain.TaskTypeAgent
	case "voice", "audio":
		return domain.TaskTypeVoice
	case "multimodal", "image":
		return domain.TaskTypeMultimodal
	default:
		return domain.TaskTypeRAG // 默认RAG
	}
}

// respondJSON 返回JSON响应
func (h *StreamHandler) respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteStatus(status)
	json.NewEncoder(w).Encode(data)
}

// respondError 返回错误响应
func (h *StreamHandler) respondError(w http.ResponseWriter, status int, message string) {
	h.respondJSON(w, status, map[string]string{
		"error": message,
	})
}
