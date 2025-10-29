package service

import (
	"context"
	"fmt"

	pb "voicehelper/api/proto/ai-orchestrator/v1"
	conversationpb "voicehelper/api/proto/conversation/v1"
	knowledgepb "voicehelper/api/proto/knowledge/v1"
	modelrouterpb "voicehelper/api/proto/model-router/v1"
	"voicehelper/pkg/clients"
)

// OrchestratorServiceWithIntegration 集成了其他服务调用的编排服务
type OrchestratorServiceWithIntegration struct {
	pb.UnimplementedOrchestratorServer

	// 远程服务客户端
	clientManager *clients.ClientManager
}

// NewOrchestratorServiceWithIntegration 创建集成服务
func NewOrchestratorServiceWithIntegration(clientManager *clients.ClientManager) *OrchestratorServiceWithIntegration {
	return &OrchestratorServiceWithIntegration{
		clientManager: clientManager,
	}
}

// ProcessMessage 处理消息（集成示例）
func (s *OrchestratorServiceWithIntegration) ProcessMessage(ctx context.Context, req *pb.ProcessMessageRequest) (*pb.ProcessMessageResponse, error) {
	// 1. 获取对话历史（调用 Conversation Service）
	conversationClient, err := s.clientManager.Conversation()
	if err != nil {
		return nil, fmt.Errorf("failed to get conversation client: %w", err)
	}

	// 获取对话上下文
	contextResp, err := conversationClient.GetContext(ctx, req.ConversationId, req.UserId)
	if err != nil {
		return nil, fmt.Errorf("failed to get conversation context: %w", err)
	}

	// 2. 如果启用 RAG，从 Knowledge Service 检索相关文档
	var citations []*pb.Citation
	if req.Config != nil && req.Config.EnableRag {
		knowledgeClient, err := s.clientManager.Knowledge()
		if err != nil {
			return nil, fmt.Errorf("failed to get knowledge client: %w", err)
		}

		// 获取知识库中的相关文档
		// 注意：这里简化了，实际应该调用专门的检索服务
		docs, err := knowledgeClient.ListDocuments(ctx, &knowledgepb.ListDocumentsRequest{
			UserId:   req.UserId,
			TenantId: req.TenantId,
			Status:   knowledgepb.DocumentStatus_DOCUMENT_STATUS_READY,
			Page:     1,
			PageSize: 5,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to list documents: %w", err)
		}

		// 构建引用
		for _, doc := range docs.Documents {
			citations = append(citations, &pb.Citation{
				Id:         doc.Id,
				DocumentId: doc.Id,
				Title:      doc.Name,
				Snippet:    fmt.Sprintf("Document: %s", doc.Name),
				Score:      0.85,
			})
		}
	}

	// 3. 路由到最佳模型（调用 Model Router）
	modelRouterClient, err := s.clientManager.ModelRouter()
	if err != nil {
		return nil, fmt.Errorf("failed to get model router client: %w", err)
	}

	modelRoute, err := modelRouterClient.RouteModel(ctx, &modelrouterpb.RouteModelRequest{
		TenantId:        req.TenantId,
		UserId:          req.UserId,
		ModelType:       modelrouterpb.ModelType_MODEL_TYPE_LLM,
		Task:            "chat",
		EstimatedTokens: int32(len(req.Message) * 2), // 粗略估算
		Requirements: map[string]string{
			"quality": "high",
			"latency": "medium",
		},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to route model: %w", err)
	}

	// 4. 调用实际的 LLM（这里简化，实际应该调用 Model Adapter 或直接调用 LLM API）
	// response := callLLM(modelRoute.ModelId, req.Message, contextResp.Messages, citations)

	_ = contextResp
	_ = modelRoute

	// 5. 保存消息（调用 Conversation Service）
	_, err = conversationClient.SendMessage(ctx, &conversationpb.SendMessageRequest{
		ConversationId: req.ConversationId,
		UserId:         req.UserId,
		Content:        req.Message,
		Role:           conversationpb.MessageRole_MESSAGE_ROLE_USER,
		Stream:         false,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to save user message: %w", err)
	}

	// 6. 返回响应
	return &pb.ProcessMessageResponse{
		TaskId:    "task-123",
		Reply:     "This is a sample AI response",
		Engine:    "rag",
		Citations: citations,
		TokenUsage: &pb.TokenUsage{
			PromptTokens:     100,
			CompletionTokens: 50,
			TotalTokens:      150,
			CostUsd:          0.001,
		},
		DurationMs: 1500,
	}, nil
}

// ExecuteWorkflow 执行工作流（集成示例）
func (s *OrchestratorServiceWithIntegration) ExecuteWorkflow(ctx context.Context, req *pb.ExecuteWorkflowRequest) (*pb.ExecuteWorkflowResponse, error) {
	// 工作流编排示例：串行调用多个服务

	// 1. 验证用户权限
	identityClient, err := s.clientManager.Identity()
	if err != nil {
		return nil, fmt.Errorf("failed to get identity client: %w", err)
	}

	permResult, err := identityClient.CheckPermission(ctx, req.UserId, "workflow", "execute")
	if err != nil {
		return nil, fmt.Errorf("failed to check permission: %w", err)
	}
	if !permResult.Allowed {
		return nil, fmt.Errorf("permission denied")
	}

	// 2. 执行工作流步骤（简化示例）
	steps := []*pb.WorkflowStep{
		{
			Id:     "step-1",
			Name:   "Retrieve Knowledge",
			Status: pb.WorkflowStatus_STATUS_COMPLETED,
			Engine: "knowledge-service",
		},
		{
			Id:     "step-2",
			Name:   "Process with AI",
			Status: pb.WorkflowStatus_STATUS_COMPLETED,
			Engine: "agent-engine",
		},
		{
			Id:     "step-3",
			Name:   "Generate Response",
			Status: pb.WorkflowStatus_STATUS_COMPLETED,
			Engine: "model-adapter",
		},
	}

	return &pb.ExecuteWorkflowResponse{
		TaskId:     "workflow-123",
		InstanceId: "instance-456",
		Status:     pb.WorkflowStatus_STATUS_COMPLETED,
		Steps:      steps,
		Outputs: map[string]string{
			"result": "Workflow completed successfully",
		},
	}, nil
}

// 其他方法示例...
