package biz

import (
	"context"
	"errors"
	"fmt"
	"io"

	"github.com/VoiceAssistant/cmd/conversation-service/internal/domain"
)

// MessageChunk 消息片段
type MessageChunk struct {
	Content   string
	IsPartial bool
	MessageID string
	Error     error
}

// OrchestratorClient AI编排客户端接口
type OrchestratorClient interface {
	GenerateStream(ctx context.Context, req *GenerateRequest) (GenerateStreamClient, error)
}

// GenerateRequest 生成请求
type GenerateRequest struct {
	ConversationID string
	Query          string
	History        []HistoryMessage
	Model          string
	Temperature    float32
}

// HistoryMessage 历史消息
type HistoryMessage struct {
	Role    string
	Content string
}

// GenerateStreamClient 流式生成客户端
type GenerateStreamClient interface {
	Recv() (*GenerateChunk, error)
}

// GenerateChunk 生成片段
type GenerateChunk struct {
	Content string
	Done    bool
}

// ConversationStreamUsecase 流式对话用例
type ConversationStreamUsecase struct {
	conversationRepo   domain.ConversationRepository
	messageRepo        domain.MessageRepository
	orchestratorClient OrchestratorClient
}

// NewConversationStreamUsecase 创建流式对话用例
func NewConversationStreamUsecase(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
	orchestratorClient OrchestratorClient,
) *ConversationStreamUsecase {
	return &ConversationStreamUsecase{
		conversationRepo:   conversationRepo,
		messageRepo:        messageRepo,
		orchestratorClient: orchestratorClient,
	}
}

// SendMessageStream 发送消息并流式返回响应
func (uc *ConversationStreamUsecase) SendMessageStream(
	ctx context.Context,
	conversationID, userID, content string,
) (<-chan MessageChunk, error) {
	// 1. 验证对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, fmt.Errorf("get conversation: %w", err)
	}

	// 2. 权限检查
	if conversation.UserID != userID {
		return nil, errors.New("unauthorized")
	}

	// 3. 创建用户消息
	userMsg := domain.NewMessage(
		conversationID,
		conversation.TenantID,
		userID,
		domain.MessageRoleUser,
		content,
	)
	if err := uc.messageRepo.CreateMessage(ctx, userMsg); err != nil {
		return nil, fmt.Errorf("create user message: %w", err)
	}

	// 4. 更新对话消息计数
	conversation.MessageCount++
	if err := uc.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return nil, fmt.Errorf("update conversation: %w", err)
	}

	// 5. 创建流式通道
	chunkChan := make(chan MessageChunk, 100)

	// 6. 异步处理
	go func() {
		defer close(chunkChan)

		// 获取对话历史
		history, err := uc.messageRepo.ListMessages(ctx, conversationID, 10, 0)
		if err != nil {
			chunkChan <- MessageChunk{Error: fmt.Errorf("get history: %w", err)}
			return
		}

		// 转换历史消息
		historyMsgs := make([]HistoryMessage, len(history))
		for i, msg := range history {
			historyMsgs[i] = HistoryMessage{
				Role:    string(msg.Role),
				Content: msg.Content,
			}
		}

		// 调用AI Orchestrator流式生成
		stream, err := uc.orchestratorClient.GenerateStream(ctx, &GenerateRequest{
			ConversationID: conversationID,
			Query:          content,
			History:        historyMsgs,
			Model:          conversation.ModelName,
			Temperature:    0.7,
		})

		if err != nil {
			chunkChan <- MessageChunk{Error: fmt.Errorf("generate stream: %w", err)}
			return
		}

		var fullContent string
		for {
			chunk, err := stream.Recv()
			if err == io.EOF {
				break
			}
			if err != nil {
				chunkChan <- MessageChunk{Error: fmt.Errorf("receive chunk: %w", err)}
				return
			}

			fullContent += chunk.Content
			chunkChan <- MessageChunk{
				Content:   chunk.Content,
				IsPartial: !chunk.Done,
			}

			if chunk.Done {
				break
			}
		}

		// 保存完整的助手消息
		assistantMsg := domain.NewMessage(
			conversationID,
			conversation.TenantID,
			"assistant",
			domain.MessageRoleAssistant,
			fullContent,
		)
		if err := uc.messageRepo.CreateMessage(ctx, assistantMsg); err != nil {
			chunkChan <- MessageChunk{Error: fmt.Errorf("save assistant message: %w", err)}
			return
		}

		// 更新对话
		conversation.MessageCount++
		conversation.LastMessageAt = assistantMsg.CreatedAt
		uc.conversationRepo.UpdateConversation(ctx, conversation)

		// 发送完成信号
		chunkChan <- MessageChunk{
			Content:   fullContent,
			IsPartial: false,
			MessageID: assistantMsg.ID,
		}
	}()

	return chunkChan, nil
}
