package service

import (
	"context"

	"voicehelper/cmd/ai-orchestrator/internal/biz"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/timestamppb"
	// 假设proto文件生成了对应的包
	// pb "voicehelper/api/proto/orchestrator/v1"
)

// 临时定义，实际应该从proto生成
type CreateTaskRequest struct {
	TaskType       string
	ConversationID string
	UserID         string
	TenantID       string
	Input          *TaskInputRequest
}

type TaskInputRequest struct {
	Content string
	Mode    string
	Context map[string]interface{}
	Options map[string]interface{}
}

type TaskResponse struct {
	ID             string
	Type           string
	Status         string
	Priority       int32
	ConversationID string
	UserID         string
	TenantID       string
	CreatedAt      *timestamppb.Timestamp
	UpdatedAt      *timestamppb.Timestamp
}

type ExecuteTaskRequest struct {
	TaskID string
}

type ExecuteTaskResponse struct {
	Task   *TaskResponse
	Output *TaskOutputResponse
}

type TaskOutputResponse struct {
	Content    string
	Metadata   map[string]interface{}
	TokensUsed int32
	Model      string
	CostUSD    float64
	LatencyMS  int32
}

type GetTaskRequest struct {
	TaskID string
}

type GetTaskResponse struct {
	Task *TaskResponse
}

// OrchestratorService AI编排服务
type OrchestratorService struct {
	taskUC *biz.TaskUsecase
	log    *log.Helper
}

// NewOrchestratorService 创建编排服务
func NewOrchestratorService(
	taskUC *biz.TaskUsecase,
	logger log.Logger,
) *OrchestratorService {
	return &OrchestratorService{
		taskUC: taskUC,
		log:    log.NewHelper(logger),
	}
}

// CreateTask 创建AI任务
func (s *OrchestratorService) CreateTask(ctx context.Context, req *CreateTaskRequest) (*TaskResponse, error) {
	// 转换输入
	input := &domain.TaskInput{
		Content: req.Input.Content,
		Mode:    req.Input.Mode,
		Context: req.Input.Context,
		Options: req.Input.Options,
	}

	// 创建任务
	task, err := s.taskUC.CreateTask(
		ctx,
		domain.TaskType(req.TaskType),
		req.ConversationID,
		req.UserID,
		req.TenantID,
		input,
	)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to create task: %v", err)
		return nil, err
	}

	return s.toTaskResponse(task), nil
}

// ExecuteTask 执行任务
func (s *OrchestratorService) ExecuteTask(ctx context.Context, req *ExecuteTaskRequest) (*ExecuteTaskResponse, error) {
	// 执行任务
	output, err := s.taskUC.ExecuteTask(ctx, req.TaskID)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to execute task: %v", err)
		return nil, err
	}

	// 获取更新后的任务
	task, err := s.taskUC.GetTask(ctx, req.TaskID)
	if err != nil {
		return nil, err
	}

	return &ExecuteTaskResponse{
		Task:   s.toTaskResponse(task),
		Output: s.toTaskOutputResponse(output),
	}, nil
}

// GetTask 获取任务详情
func (s *OrchestratorService) GetTask(ctx context.Context, req *GetTaskRequest) (*GetTaskResponse, error) {
	task, err := s.taskUC.GetTask(ctx, req.TaskID)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to get task: %v", err)
		return nil, err
	}

	return &GetTaskResponse{
		Task: s.toTaskResponse(task),
	}, nil
}

// CreateAndExecuteTask 创建并执行任务（同步）
func (s *OrchestratorService) CreateAndExecuteTask(ctx context.Context, req *CreateTaskRequest) (*ExecuteTaskResponse, error) {
	// 转换输入
	input := &domain.TaskInput{
		Content: req.Input.Content,
		Mode:    req.Input.Mode,
		Context: req.Input.Context,
		Options: req.Input.Options,
	}

	// 创建并执行
	task, output, err := s.taskUC.CreateAndExecuteTask(
		ctx,
		domain.TaskType(req.TaskType),
		req.ConversationID,
		req.UserID,
		req.TenantID,
		input,
	)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to create and execute task: %v", err)
		return nil, err
	}

	return &ExecuteTaskResponse{
		Task:   s.toTaskResponse(task),
		Output: s.toTaskOutputResponse(output),
	}, nil
}

// CancelTask 取消任务
func (s *OrchestratorService) CancelTask(ctx context.Context, req *GetTaskRequest) (*TaskResponse, error) {
	if err := s.taskUC.CancelTask(ctx, req.TaskID); err != nil {
		s.log.WithContext(ctx).Errorf("failed to cancel task: %v", err)
		return nil, err
	}

	task, err := s.taskUC.GetTask(ctx, req.TaskID)
	if err != nil {
		return nil, err
	}

	return s.toTaskResponse(task), nil
}

// toTaskResponse 转换为响应对象
func (s *OrchestratorService) toTaskResponse(task *domain.Task) *TaskResponse {
	return &TaskResponse{
		ID:             task.ID,
		Type:           string(task.Type),
		Status:         string(task.Status),
		Priority:       int32(task.Priority),
		ConversationID: task.ConversationID,
		UserID:         task.UserID,
		TenantID:       task.TenantID,
		CreatedAt:      timestamppb.New(task.CreatedAt),
		UpdatedAt:      timestamppb.New(task.UpdatedAt),
	}
}

// toTaskOutputResponse 转换输出为响应对象
func (s *OrchestratorService) toTaskOutputResponse(output *domain.TaskOutput) *TaskOutputResponse {
	return &TaskOutputResponse{
		Content:    output.Content,
		Metadata:   output.Metadata,
		TokensUsed: int32(output.TokensUsed),
		Model:      output.Model,
		CostUSD:    output.CostUSD,
		LatencyMS:  int32(output.LatencyMS),
	}
}
