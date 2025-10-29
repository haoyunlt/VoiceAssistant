package clients

import (
	"context"
	"fmt"

	pb "voicehelper/api/proto/conversation/v1"
	grpcpkg "voicehelper/pkg/grpc"
)

// ConversationClient Conversation 服务客户端包装器
type ConversationClient struct {
	client  pb.ConversationServiceClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewConversationClient 创建 Conversation 服务客户端
func NewConversationClient(factory *grpcpkg.ClientFactory, target string) (*ConversationClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &ConversationClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *ConversationClient) getClient(ctx context.Context) (pb.ConversationServiceClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "conversation-service", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get conversation service connection: %w", err)
	}

	c.client = pb.NewConversationServiceClient(conn)
	return c.client, nil
}

// CreateConversation 创建对话
func (c *ConversationClient) CreateConversation(ctx context.Context, req *pb.CreateConversationRequest) (*pb.Conversation, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CreateConversation(ctx, req)
}

// GetConversation 获取对话
func (c *ConversationClient) GetConversation(ctx context.Context, conversationID, userID string) (*pb.Conversation, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetConversation(ctx, &pb.GetConversationRequest{
		Id:     conversationID,
		UserId: userID,
	})
}

// ListConversations 列出对话
func (c *ConversationClient) ListConversations(ctx context.Context, req *pb.ListConversationsRequest) (*pb.ListConversationsResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListConversations(ctx, req)
}

// UpdateConversation 更新对话
func (c *ConversationClient) UpdateConversation(ctx context.Context, req *pb.UpdateConversationRequest) (*pb.Conversation, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateConversation(ctx, req)
}

// DeleteConversation 删除对话
func (c *ConversationClient) DeleteConversation(ctx context.Context, conversationID, userID string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.DeleteConversation(ctx, &pb.DeleteConversationRequest{
		Id:     conversationID,
		UserId: userID,
	})
	return err
}

// SendMessage 发送消息
func (c *ConversationClient) SendMessage(ctx context.Context, req *pb.SendMessageRequest) (*pb.Message, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.SendMessage(ctx, req)
}

// GetMessage 获取消息
func (c *ConversationClient) GetMessage(ctx context.Context, messageID, conversationID string) (*pb.Message, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetMessage(ctx, &pb.GetMessageRequest{
		Id:             messageID,
		ConversationId: conversationID,
	})
}

// ListMessages 列出消息
func (c *ConversationClient) ListMessages(ctx context.Context, req *pb.ListMessagesRequest) (*pb.ListMessagesResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListMessages(ctx, req)
}

// StreamMessages 流式发送消息
func (c *ConversationClient) StreamMessages(ctx context.Context, req *pb.StreamMessagesRequest) (pb.ConversationService_StreamMessagesClient, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.StreamMessages(ctx, req)
}

// GetContext 获取上下文
func (c *ConversationClient) GetContext(ctx context.Context, conversationID, userID string) (*pb.Context, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetContext(ctx, &pb.GetContextRequest{
		ConversationId: conversationID,
		UserId:         userID,
	})
}

// UpdateContext 更新上下文
func (c *ConversationClient) UpdateContext(ctx context.Context, req *pb.UpdateContextRequest) (*pb.Context, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateContext(ctx, req)
}

// ClearContext 清除上下文
func (c *ConversationClient) ClearContext(ctx context.Context, conversationID, userID string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.ClearContext(ctx, &pb.ClearContextRequest{
		ConversationId: conversationID,
		UserId:         userID,
	})
	return err
}
