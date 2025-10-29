package service

import (
	"context"
	"fmt"

	aiorchestratorpb "voicehelper/api/proto/ai-orchestrator/v1"
	pb "voicehelper/api/proto/conversation/v1"
	"voicehelper/pkg/clients"
	grpcpkg "voicehelper/pkg/grpc"
)

// ConversationServiceWithIntegration 集成了其他服务调用的对话服务
type ConversationServiceWithIntegration struct {
	pb.UnimplementedConversationServiceServer

	// 本地依赖
	// repo ConversationRepository
	// cache CacheService

	// 远程服务客户端
	clientManager *clients.ClientManager
}

// NewConversationServiceWithIntegration 创建集成服务
func NewConversationServiceWithIntegration(clientManager *clients.ClientManager) *ConversationServiceWithIntegration {
	return &ConversationServiceWithIntegration{
		clientManager: clientManager,
	}
}

// SendMessage 发送消息（集成示例）
func (s *ConversationServiceWithIntegration) SendMessage(ctx context.Context, req *pb.SendMessageRequest) (*pb.Message, error) {
	// 1. 验证用户权限（调用 Identity Service）
	identityClient, err := s.clientManager.Identity()
	if err != nil {
		return nil, fmt.Errorf("failed to get identity client: %w", err)
	}

	// 从 context 中提取 token（由 Gateway 中间件注入）
	token := grpcpkg.ExtractToken(ctx)
	if token != "" {
		ctx = grpcpkg.WithToken(ctx, token)
	}

	// 验证权限：检查用户是否有权限访问该对话
	permResult, err := identityClient.CheckPermission(ctx, req.UserId, "conversation", "write")
	if err != nil {
		return nil, fmt.Errorf("failed to check permission: %w", err)
	}
	if !permResult.Allowed {
		return nil, fmt.Errorf("permission denied: %s", permResult.Reason)
	}

	// 2. 保存消息到数据库
	// message := s.repo.SaveMessage(...)

	// 3. 如果需要 AI 处理，调用 AI Orchestrator
	if req.Role == pb.MessageRole_MESSAGE_ROLE_USER {
		orchestratorClient, err := s.clientManager.Orchestrator()
		if err != nil {
			return nil, fmt.Errorf("failed to get orchestrator client: %w", err)
		}

		// 调用 AI 处理
		aiResp, err := orchestratorClient.ProcessMessage(ctx, &aiorchestratorpb.ProcessMessageRequest{
			ConversationId: req.ConversationId,
			Message:        req.Content,
			UserId:         req.UserId,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to process message with AI: %w", err)
		}

		// 保存 AI 回复
		// aiMessage := s.repo.SaveMessage(aiResp.Reply, ...)
		_ = aiResp
	}

	// 4. 返回消息
	return &pb.Message{
		Id:             "msg-123",
		ConversationId: req.ConversationId,
		Role:           req.Role,
		Content:        req.Content,
	}, nil
}

// CreateConversation 创建对话（集成示例）
func (s *ConversationServiceWithIntegration) CreateConversation(ctx context.Context, req *pb.CreateConversationRequest) (*pb.Conversation, error) {
	// 1. 验证用户存在（调用 Identity Service）
	identityClient, err := s.clientManager.Identity()
	if err != nil {
		return nil, fmt.Errorf("failed to get identity client: %w", err)
	}

	user, err := identityClient.GetUser(ctx, req.UserId)
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	// 2. 检查租户配额（调用 Identity Service）
	tenant, err := identityClient.GetTenant(ctx, req.TenantId)
	if err != nil {
		return nil, fmt.Errorf("failed to get tenant: %w", err)
	}

	// 检查是否超出配额
	if tenant.Usage.ApiCallsToday >= tenant.Quota.MaxApiCallsPerDay {
		return nil, fmt.Errorf("tenant quota exceeded")
	}

	// 3. 创建对话
	// conversation := s.repo.CreateConversation(...)

	_ = user

	return &pb.Conversation{
		Id:       "conv-123",
		UserId:   req.UserId,
		TenantId: req.TenantId,
		Title:    req.Title,
		Mode:     req.Mode,
	}, nil
}

// 其他方法示例...
