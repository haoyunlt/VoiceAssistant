package biz

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"

	"ai-orchestrator/internal/domain"
	"ai-orchestrator/internal/infra/grpc"
)

type OrchestratorUsecase struct {
	taskRepo        domain.TaskRepository
	ragClient       grpc.RAGClient
	agentClient     grpc.AgentClient
	retrievalClient grpc.RetrievalClient
	modelRouter     grpc.ModelRouterClient
}

func NewOrchestratorUsecase(
	taskRepo domain.TaskRepository,
	ragClient grpc.RAGClient,
	agentClient grpc.AgentClient,
	retrievalClient grpc.RetrievalClient,
	modelRouter grpc.ModelRouterClient,
) *OrchestratorUsecase {
	return &OrchestratorUsecase{
		taskRepo:        taskRepo,
		ragClient:       ragClient,
		agentClient:     agentClient,
		retrievalClient: retrievalClient,
		modelRouter:     modelRouter,
	}
}

// CreateTask 创建任务
func (uc *OrchestratorUsecase) CreateTask(ctx context.Context, req *CreateTaskRequest) (*domain.Task, error) {
	task := &domain.Task{
		ID:             "task_" + uuid.New().String(),
		UserID:         req.UserID,
		TenantID:       req.TenantID,
		ConversationID: req.ConversationID,
		Type:           req.TaskType,
		Status:         domain.TaskStatusPending,
		Input:          req.Input,
		Params:         req.Params,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	if err := uc.taskRepo.Create(task); err != nil {
		return nil, err
	}

	return task, nil
}

// ExecuteChat 执行对话任务
func (uc *OrchestratorUsecase) ExecuteChat(ctx context.Context, req *ExecuteChatRequest, stream chan<- *ChatResponse) error {
	// 创建任务
	task, err := uc.CreateTask(ctx, &CreateTaskRequest{
		UserID:         req.UserID,
		TenantID:       req.TenantID,
		ConversationID: req.ConversationID,
		TaskType:       domain.TaskTypeChat,
		Input:          req.Message,
		Params:         req.Params,
	})
	if err != nil {
		return err
	}

	// 更新任务状态
	task.Status = domain.TaskStatusRunning
	task.UpdatedAt = time.Now()
	if err := uc.taskRepo.Update(task); err != nil {
		return err
	}

	startTime := time.Now()

	// 根据模式路由
	switch req.Mode {
	case ChatModeDirect:
		// 直接对话
		err = uc.executeDirectChat(ctx, task, req, stream)
	case ChatModeRAG:
		// RAG 增强对话
		err = uc.executeRAGChat(ctx, task, req, stream)
	case ChatModeAgent:
		// Agent 模式
		err = uc.executeAgentChat(ctx, task, req, stream)
	default:
		err = fmt.Errorf("unknown chat mode: %s", req.Mode)
	}

	// 更新任务状态
	duration := time.Since(startTime)
	task.Metrics.DurationMS = float64(duration.Milliseconds())
	task.UpdatedAt = time.Now()

	if err != nil {
		task.Status = domain.TaskStatusFailed
		task.Error = err.Error()
	} else {
		task.Status = domain.TaskStatusCompleted
		completedAt := time.Now()
		task.CompletedAt = &completedAt
	}

	uc.taskRepo.Update(task)

	return err
}

// executeDirectChat 执行直接对话
func (uc *OrchestratorUsecase) executeDirectChat(ctx context.Context, task *domain.Task, req *ExecuteChatRequest, stream chan<- *ChatResponse) error {
	// 1. 路由模型
	modelDecision, err := uc.modelRouter.RouteModel(ctx, &ModelRouteRequest{
		TenantID:        req.TenantID,
		ModelType:       "llm",
		EstimatedTokens: len(req.Message) / 4, // 简单估算
	})
	if err != nil {
		return err
	}

	task.Metrics.ModelUsed = modelDecision.ModelID

	// 2. 调用 LLM (这里简化处理)
	// 实际应该调用 Model Adapter
	response := &ChatResponse{
		TaskID:  task.ID,
		Type:    ResponseTypeText,
		Content: fmt.Sprintf("Response to: %s", req.Message),
		Done:    false,
	}

	stream <- response

	// 最终响应
	finalResponse := &ChatResponse{
		TaskID:  task.ID,
		Type:    ResponseTypeFinal,
		Done:    true,
		Metrics: &task.Metrics,
	}
	stream <- finalResponse

	return nil
}

// executeRAGChat 执行 RAG 增强对话
func (uc *OrchestratorUsecase) executeRAGChat(ctx context.Context, task *domain.Task, req *ExecuteChatRequest, stream chan<- *ChatResponse) error {
	// 1. 检索相关文档
	chunks, err := uc.retrievalClient.Retrieve(ctx, &RetrievalRequest{
		Query:    req.Message,
		TenantID: req.TenantID,
		TopK:     5,
		Mode:     "hybrid",
	})
	if err != nil {
		return err
	}

	// 发送检索结果
	stream <- &ChatResponse{
		TaskID:  task.ID,
		Type:    ResponseTypeRetrieved,
		Content: fmt.Sprintf("Retrieved %d chunks", len(chunks)),
		Done:    false,
	}

	// 2. 使用 RAG Engine 生成回答
	ragResponse, err := uc.ragClient.Generate(ctx, &RAGRequest{
		Query:  req.Message,
		Chunks: chunks,
	})
	if err != nil {
		return err
	}

	// 流式输出
	for _, chunk := range ragResponse.Chunks {
		stream <- &ChatResponse{
			TaskID:  task.ID,
			Type:    ResponseTypeText,
			Content: chunk,
			Done:    false,
		}
	}

	// 更新指标
	task.Metrics.TokensUsed = ragResponse.TokensUsed
	task.Metrics.CostUSD = ragResponse.CostUSD
	task.Output = ragResponse.Answer

	// 最终响应
	stream <- &ChatResponse{
		TaskID:  task.ID,
		Type:    ResponseTypeFinal,
		Done:    true,
		Metrics: &task.Metrics,
	}

	return nil
}

// executeAgentChat 执行 Agent 模式对话
func (uc *OrchestratorUsecase) executeAgentChat(ctx context.Context, task *domain.Task, req *ExecuteChatRequest, stream chan<- *ChatResponse) error {
	// 调用 Agent Engine
	agentResponse, err := uc.agentClient.Execute(ctx, &AgentRequest{
		Task:           req.Message,
		AvailableTools: []string{"search", "calculator", "knowledge_base"},
		MaxIterations:  5,
	})
	if err != nil {
		return err
	}

	// 流式输出 Agent 步骤
	for _, step := range agentResponse.Steps {
		stream <- &ChatResponse{
			TaskID:  task.ID,
			Type:    ResponseTypeThinking,
			Content: fmt.Sprintf("Step %d: %s", step.StepNumber, step.Thought),
			Done:    false,
		}

		if step.ToolCall != nil {
			stream <- &ChatResponse{
				TaskID:   task.ID,
				Type:     ResponseTypeToolCall,
				Content:  fmt.Sprintf("Calling %s", step.ToolCall.ToolName),
				ToolCall: step.ToolCall,
				Done:     false,
			}
		}
	}

	// 最终答案
	stream <- &ChatResponse{
		TaskID:  task.ID,
		Type:    ResponseTypeText,
		Content: agentResponse.FinalAnswer,
		Done:    false,
	}

	// 更新任务
	task.Output = agentResponse.FinalAnswer
	task.Metrics.TotalSteps = len(agentResponse.Steps)
	task.Metrics.TokensUsed = agentResponse.TokensUsed
	task.Metrics.CostUSD = agentResponse.CostUSD

	// 最终响应
	stream <- &ChatResponse{
		TaskID:  task.ID,
		Type:    ResponseTypeFinal,
		Done:    true,
		Metrics: &task.Metrics,
	}

	return nil
}

// GetTask 获取任务
func (uc *OrchestratorUsecase) GetTask(ctx context.Context, taskID string) (*domain.Task, error) {
	return uc.taskRepo.GetByID(taskID)
}

// CancelTask 取消任务
func (uc *OrchestratorUsecase) CancelTask(ctx context.Context, taskID, reason string) error {
	task, err := uc.taskRepo.GetByID(taskID)
	if err != nil {
		return err
	}

	if task.Status == domain.TaskStatusCompleted || task.Status == domain.TaskStatusFailed {
		return fmt.Errorf("task already finished")
	}

	task.Status = domain.TaskStatusCancelled
	task.Error = reason
	task.UpdatedAt = time.Now()

	return uc.taskRepo.Update(task)
}

// Request types
type CreateTaskRequest struct {
	UserID         string
	TenantID       string
	ConversationID string
	TaskType       domain.TaskType
	Input          string
	Params         map[string]interface{}
}

type ExecuteChatRequest struct {
	UserID         string
	TenantID       string
	ConversationID string
	Message        string
	Mode           ChatMode
	Params         map[string]interface{}
}

type ChatMode string

const (
	ChatModeDirect ChatMode = "direct"
	ChatModeRAG    ChatMode = "rag"
	ChatModeAgent  ChatMode = "agent"
)

type ChatResponse struct {
	TaskID   string
	Type     ResponseType
	Content  string
	ToolCall *ToolCall
	Done     bool
	Metrics  *domain.TaskMetrics
}

type ResponseType string

const (
	ResponseTypeText      ResponseType = "text"
	ResponseTypeThinking  ResponseType = "thinking"
	ResponseTypeToolCall  ResponseType = "tool_call"
	ResponseTypeRetrieved ResponseType = "retrieved"
	ResponseTypeFinal     ResponseType = "final"
)

type ToolCall struct {
	ToolName  string
	Arguments map[string]string
	Result    string
}

// gRPC Client Request types
type ModelRouteRequest struct {
	TenantID        string
	ModelType       string
	EstimatedTokens int
}

type RetrievalRequest struct {
	Query    string
	TenantID string
	TopK     int
	Mode     string
}

type RAGRequest struct {
	Query  string
	Chunks []interface{}
}

type AgentRequest struct {
	Task           string
	AvailableTools []string
	MaxIterations  int
}
