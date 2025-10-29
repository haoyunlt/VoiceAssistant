package clients

import (
	"context"
	"fmt"

	pb "voicehelper/api/proto/knowledge/v1"
	grpcpkg "voicehelper/pkg/grpc"
)

// KnowledgeClient Knowledge 服务客户端包装器
type KnowledgeClient struct {
	client  pb.KnowledgeServiceClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewKnowledgeClient 创建 Knowledge 服务客户端
func NewKnowledgeClient(factory *grpcpkg.ClientFactory, target string) (*KnowledgeClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &KnowledgeClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *KnowledgeClient) getClient(ctx context.Context) (pb.KnowledgeServiceClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "knowledge-service", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get knowledge service connection: %w", err)
	}

	c.client = pb.NewKnowledgeServiceClient(conn)
	return c.client, nil
}

// UploadDocument 上传文档
func (c *KnowledgeClient) UploadDocument(ctx context.Context, req *pb.UploadDocumentRequest) (*pb.Document, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UploadDocument(ctx, req)
}

// GetDocument 获取文档
func (c *KnowledgeClient) GetDocument(ctx context.Context, documentID, userID string) (*pb.Document, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetDocument(ctx, &pb.GetDocumentRequest{
		Id:     documentID,
		UserId: userID,
	})
}

// ListDocuments 列出文档
func (c *KnowledgeClient) ListDocuments(ctx context.Context, req *pb.ListDocumentsRequest) (*pb.ListDocumentsResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListDocuments(ctx, req)
}

// UpdateDocument 更新文档
func (c *KnowledgeClient) UpdateDocument(ctx context.Context, req *pb.UpdateDocumentRequest) (*pb.Document, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateDocument(ctx, req)
}

// DeleteDocument 删除文档
func (c *KnowledgeClient) DeleteDocument(ctx context.Context, documentID, userID string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.DeleteDocument(ctx, &pb.DeleteDocumentRequest{
		Id:     documentID,
		UserId: userID,
	})
	return err
}

// DownloadDocument 下载文档（流式）
func (c *KnowledgeClient) DownloadDocument(ctx context.Context, documentID, userID string) (pb.KnowledgeService_DownloadDocumentClient, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.DownloadDocument(ctx, &pb.DownloadDocumentRequest{
		Id:     documentID,
		UserId: userID,
	})
}

// CreateCollection 创建集合
func (c *KnowledgeClient) CreateCollection(ctx context.Context, req *pb.CreateCollectionRequest) (*pb.Collection, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CreateCollection(ctx, req)
}

// GetCollection 获取集合
func (c *KnowledgeClient) GetCollection(ctx context.Context, collectionID, userID string) (*pb.Collection, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetCollection(ctx, &pb.GetCollectionRequest{
		Id:     collectionID,
		UserId: userID,
	})
}

// ListCollections 列出集合
func (c *KnowledgeClient) ListCollections(ctx context.Context, req *pb.ListCollectionsRequest) (*pb.ListCollectionsResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListCollections(ctx, req)
}

// UpdateCollection 更新集合
func (c *KnowledgeClient) UpdateCollection(ctx context.Context, req *pb.UpdateCollectionRequest) (*pb.Collection, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateCollection(ctx, req)
}

// DeleteCollection 删除集合
func (c *KnowledgeClient) DeleteCollection(ctx context.Context, collectionID, userID string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.DeleteCollection(ctx, &pb.DeleteCollectionRequest{
		Id:     collectionID,
		UserId: userID,
	})
	return err
}

// GetDocumentVersion 获取文档版本
func (c *KnowledgeClient) GetDocumentVersion(ctx context.Context, documentID string, version int32, userID string) (*pb.DocumentVersion, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetDocumentVersion(ctx, &pb.GetDocumentVersionRequest{
		DocumentId: documentID,
		Version:    version,
		UserId:     userID,
	})
}

// ListDocumentVersions 列出文档版本
func (c *KnowledgeClient) ListDocumentVersions(ctx context.Context, documentID, userID string) (*pb.ListDocumentVersionsResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListDocumentVersions(ctx, &pb.ListDocumentVersionsRequest{
		DocumentId: documentID,
		UserId:     userID,
	})
}
