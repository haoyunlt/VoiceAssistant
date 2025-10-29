package service

import (
	"context"
	"fmt"

	pb "voicehelper/api/proto/knowledge/v1"
	"voicehelper/pkg/clients"
)

// KnowledgeServiceWithIntegration 集成了其他服务调用的知识服务
type KnowledgeServiceWithIntegration struct {
	pb.UnimplementedKnowledgeServiceServer

	// 远程服务客户端
	clientManager *clients.ClientManager
}

// NewKnowledgeServiceWithIntegration 创建集成服务
func NewKnowledgeServiceWithIntegration(clientManager *clients.ClientManager) *KnowledgeServiceWithIntegration {
	return &KnowledgeServiceWithIntegration{
		clientManager: clientManager,
	}
}

// UploadDocument 上传文档（集成示例）
func (s *KnowledgeServiceWithIntegration) UploadDocument(ctx context.Context, req *pb.UploadDocumentRequest) (*pb.Document, error) {
	// 1. 验证用户权限和配额（调用 Identity Service）
	identityClient, err := s.clientManager.Identity()
	if err != nil {
		return nil, fmt.Errorf("failed to get identity client: %w", err)
	}

	// 检查权限
	permResult, err := identityClient.CheckPermission(ctx, req.UserId, "document", "create")
	if err != nil {
		return nil, fmt.Errorf("failed to check permission: %w", err)
	}
	if !permResult.Allowed {
		return nil, fmt.Errorf("permission denied: %s", permResult.Reason)
	}

	// 检查租户配额
	tenant, err := identityClient.GetTenant(ctx, req.TenantId)
	if err != nil {
		return nil, fmt.Errorf("failed to get tenant: %w", err)
	}

	// 检查文档数量配额
	if tenant.Usage.DocumentCount >= tenant.Quota.MaxDocuments {
		return nil, fmt.Errorf("document quota exceeded: %d/%d",
			tenant.Usage.DocumentCount, tenant.Quota.MaxDocuments)
	}

	// 检查存储空间配额
	if tenant.Usage.StorageBytes+int64(len(req.Content)) > tenant.Quota.MaxStorageBytes {
		return nil, fmt.Errorf("storage quota exceeded")
	}

	// 2. 保存文档到对象存储（MinIO）
	// storagePath := s.storage.SaveDocument(req.Content)

	// 3. 创建文档记录
	// document := s.repo.CreateDocument(...)

	// 4. 触发索引任务（异步，通过消息队列或直接调用 Indexing Service）
	// s.indexingService.IndexDocument(document.Id)

	return &pb.Document{
		Id:           "doc-123",
		UserId:       req.UserId,
		TenantId:     req.TenantId,
		CollectionId: req.CollectionId,
		Name:         req.Name,
		ContentType:  req.ContentType,
		SizeBytes:    int64(len(req.Content)),
		Status:       pb.DocumentStatus_DOCUMENT_STATUS_PROCESSING,
	}, nil
}

// CreateCollection 创建集合（集成示例）
func (s *KnowledgeServiceWithIntegration) CreateCollection(ctx context.Context, req *pb.CreateCollectionRequest) (*pb.Collection, error) {
	// 1. 验证用户（调用 Identity Service）
	identityClient, err := s.clientManager.Identity()
	if err != nil {
		return nil, fmt.Errorf("failed to get identity client: %w", err)
	}

	user, err := identityClient.GetUser(ctx, req.UserId)
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	// 2. 检查权限
	permResult, err := identityClient.CheckPermission(ctx, req.UserId, "collection", "create")
	if err != nil {
		return nil, fmt.Errorf("failed to check permission: %w", err)
	}
	if !permResult.Allowed {
		return nil, fmt.Errorf("permission denied")
	}

	// 3. 创建集合
	// collection := s.repo.CreateCollection(...)

	_ = user

	return &pb.Collection{
		Id:          "coll-123",
		UserId:      req.UserId,
		TenantId:    req.TenantId,
		Name:        req.Name,
		Description: req.Description,
		Type:        req.Type,
	}, nil
}

// ListDocuments 列出文档（集成示例）
func (s *KnowledgeServiceWithIntegration) ListDocuments(ctx context.Context, req *pb.ListDocumentsRequest) (*pb.ListDocumentsResponse, error) {
	// 1. 验证用户权限
	identityClient, err := s.clientManager.Identity()
	if err != nil {
		return nil, fmt.Errorf("failed to get identity client: %w", err)
	}

	permResult, err := identityClient.CheckPermission(ctx, req.UserId, "document", "read")
	if err != nil {
		return nil, fmt.Errorf("failed to check permission: %w", err)
	}
	if !permResult.Allowed {
		return nil, fmt.Errorf("permission denied")
	}

	// 2. 查询文档列表
	// documents := s.repo.ListDocuments(...)

	return &pb.ListDocumentsResponse{
		Documents: []*pb.Document{
			{
				Id:       "doc-1",
				UserId:   req.UserId,
				TenantId: req.TenantId,
				Name:     "Sample Document 1",
				Status:   pb.DocumentStatus_DOCUMENT_STATUS_READY,
			},
		},
		Total: 1,
	}, nil
}

// 其他方法示例...
