package clients

import (
	"context"
	"fmt"

	pb "voicehelper/api/proto/ai-orchestrator/v1"
	grpcpkg "voicehelper/pkg/grpc"
)

// OrchestratorClient AI Orchestrator 服务客户端包装器
type OrchestratorClient struct {
	client  pb.OrchestratorClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewOrchestratorClient 创建 Orchestrator 服务客户端
func NewOrchestratorClient(factory *grpcpkg.ClientFactory, target string) (*OrchestratorClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &OrchestratorClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *OrchestratorClient) getClient(ctx context.Context) (pb.OrchestratorClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "ai-orchestrator", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get orchestrator connection: %w", err)
	}

	c.client = pb.NewOrchestratorClient(conn)
	return c.client, nil
}

// ProcessMessage 处理消息（非流式）
func (c *OrchestratorClient) ProcessMessage(ctx context.Context, req *pb.ProcessMessageRequest) (*pb.ProcessMessageResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ProcessMessage(ctx, req)
}

// ProcessMessageStream 处理消息（流式）
func (c *OrchestratorClient) ProcessMessageStream(ctx context.Context, req *pb.ProcessMessageRequest) (pb.Orchestrator_ProcessMessageStreamClient, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ProcessMessageStream(ctx, req)
}

// ExecuteWorkflow 执行工作流
func (c *OrchestratorClient) ExecuteWorkflow(ctx context.Context, req *pb.ExecuteWorkflowRequest) (*pb.ExecuteWorkflowResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ExecuteWorkflow(ctx, req)
}

// CancelTask 取消任务
func (c *OrchestratorClient) CancelTask(ctx context.Context, taskID, userID string) (*pb.CancelTaskResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CancelTask(ctx, &pb.CancelTaskRequest{
		TaskId: taskID,
		UserId: userID,
	})
}

// GetTaskStatus 获取任务状态
func (c *OrchestratorClient) GetTaskStatus(ctx context.Context, taskID, userID string) (*pb.GetTaskStatusResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetTaskStatus(ctx, &pb.GetTaskStatusRequest{
		TaskId: taskID,
		UserId: userID,
	})
}
