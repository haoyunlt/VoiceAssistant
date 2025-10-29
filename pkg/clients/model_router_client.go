package clients

import (
	"context"
	"fmt"

	pb "voicehelper/api/proto/model-router/v1"
	grpcpkg "voicehelper/pkg/grpc"
)

// ModelRouterClient Model Router 服务客户端包装器
type ModelRouterClient struct {
	client  pb.ModelRouterClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewModelRouterClient 创建 Model Router 服务客户端
func NewModelRouterClient(factory *grpcpkg.ClientFactory, target string) (*ModelRouterClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &ModelRouterClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *ModelRouterClient) getClient(ctx context.Context) (pb.ModelRouterClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "model-router", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get model router connection: %w", err)
	}

	c.client = pb.NewModelRouterClient(conn)
	return c.client, nil
}

// RouteModel 路由模型请求
func (c *ModelRouterClient) RouteModel(ctx context.Context, req *pb.RouteModelRequest) (*pb.RouteModelResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.RouteModel(ctx, req)
}

// GetModelCost 获取模型成本
func (c *ModelRouterClient) GetModelCost(ctx context.Context, modelID string, inputTokens, outputTokens int32) (*pb.ModelCost, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetModelCost(ctx, &pb.GetModelCostRequest{
		ModelId:      modelID,
		InputTokens:  inputTokens,
		OutputTokens: outputTokens,
	})
}

// BatchRoute 批量路由
func (c *ModelRouterClient) BatchRoute(ctx context.Context, req *pb.BatchRouteRequest) (*pb.BatchRouteResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.BatchRoute(ctx, req)
}

// RecommendModel 获取推荐模型
func (c *ModelRouterClient) RecommendModel(ctx context.Context, req *pb.RecommendModelRequest) (*pb.RecommendModelResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.RecommendModel(ctx, req)
}

// UpdateModelConfig 更新模型配置
func (c *ModelRouterClient) UpdateModelConfig(ctx context.Context, req *pb.UpdateModelConfigRequest) (*pb.ModelConfig, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateModelConfig(ctx, req)
}
