package biz

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/VoiceAssistant/cmd/conversation-service/internal/domain"
)

var (
	ErrNoMessages = errors.New("no messages to generate title from")
)

// LLMClient LLM客户端接口
type LLMClient interface {
	ChatCompletion(ctx context.Context, req *LLMRequest) (*LLMResponse, error)
}

// LLMRequest LLM请求
type LLMRequest struct {
	Model       string
	Messages    []LLMMessage
	MaxTokens   int
	Temperature float32
}

// LLMMessage LLM消息
type LLMMessage struct {
	Role    string
	Content string
}

// LLMResponse LLM响应
type LLMResponse struct {
	Choices []LLMChoice
}

// LLMChoice LLM选择
type LLMChoice struct {
	Message LLMMessage
}

// TitleGeneratorUsecase 标题生成用例
type TitleGeneratorUsecase struct {
	llmClient        LLMClient
	conversationRepo domain.ConversationRepository
	messageRepo      domain.MessageRepository
}

// NewTitleGeneratorUsecase 创建标题生成用例
func NewTitleGeneratorUsecase(
	llmClient LLMClient,
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
) *TitleGeneratorUsecase {
	return &TitleGeneratorUsecase{
		llmClient:        llmClient,
		conversationRepo: conversationRepo,
		messageRepo:      messageRepo,
	}
}

// GenerateTitle 生成对话标题
func (uc *TitleGeneratorUsecase) GenerateTitle(
	ctx context.Context,
	conversationID string,
) (string, error) {
	// 1. 获取对话的前3条消息
	messages, err := uc.messageRepo.ListMessages(ctx, conversationID, 3, 0)
	if err != nil {
		return "", fmt.Errorf("list messages: %w", err)
	}

	if len(messages) == 0 {
		return "", ErrNoMessages
	}

	// 2. 构建提示词
	prompt := uc.buildTitlePrompt(messages)

	// 3. 调用LLM生成标题
	response, err := uc.llmClient.ChatCompletion(ctx, &LLMRequest{
		Model: "gpt-3.5-turbo",
		Messages: []LLMMessage{
			{
				Role:    "user",
				Content: prompt,
			},
		},
		MaxTokens:   20,
		Temperature: 0.7,
	})

	if err != nil {
		return "", fmt.Errorf("llm chat completion: %w", err)
	}

	if len(response.Choices) == 0 {
		return "", errors.New("no response from llm")
	}

	title := strings.TrimSpace(response.Choices[0].Message.Content)

	// 4. 清理标题（去除引号等）
	title = cleanTitle(title)

	// 5. 更新对话标题
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return "", fmt.Errorf("get conversation: %w", err)
	}

	conversation.Title = title
	if err := uc.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return "", fmt.Errorf("update conversation: %w", err)
	}

	return title, nil
}

// buildTitlePrompt 构建标题生成提示词
func (uc *TitleGeneratorUsecase) buildTitlePrompt(messages []*domain.Message) string {
	var conversationText strings.Builder

	for _, msg := range messages {
		role := "用户"
		if msg.Role == domain.MessageRoleAssistant {
			role = "助手"
		}
		conversationText.WriteString(fmt.Sprintf("%s: %s\n", role, msg.Content))
	}

	return fmt.Sprintf(`根据以下对话内容，生成一个简洁的标题（不超过10个字）：

%s

要求：
1. 标题要简洁明了，能概括对话主题
2. 不要使用标点符号
3. 不要使用引号
4. 直接返回标题文本，不要其他内容

标题：`, conversationText.String())
}

// GenerateTitleAsync 异步生成标题
func (uc *TitleGeneratorUsecase) GenerateTitleAsync(
	ctx context.Context,
	conversationID string,
) {
	go func() {
		_, err := uc.GenerateTitle(context.Background(), conversationID)
		if err != nil {
			// 记录错误但不影响主流程
			// logger.Errorf("Failed to generate title for conversation %s: %v", conversationID, err)
		}
	}()
}

// cleanTitle 清理标题
func cleanTitle(title string) string {
	// 去除首尾引号
	title = strings.Trim(title, `"'""''`)

	// 去除"标题："等前缀
	prefixes := []string{"标题：", "标题:", "Title:", "Title："}
	for _, prefix := range prefixes {
		if strings.HasPrefix(title, prefix) {
			title = strings.TrimPrefix(title, prefix)
			title = strings.TrimSpace(title)
		}
	}

	// 限制长度
	if len([]rune(title)) > 20 {
		runes := []rune(title)
		title = string(runes[:20]) + "..."
	}

	return title
}

// ShouldGenerateTitle 判断是否应该生成标题
func (uc *TitleGeneratorUsecase) ShouldGenerateTitle(
	conversation *domain.Conversation,
) bool {
	// 如果已有标题且不是默认标题，不重新生成
	if conversation.Title != "" && conversation.Title != "新对话" {
		return false
	}

	// 如果消息数量达到2条（1条用户+1条助手），生成标题
	if conversation.MessageCount >= 2 {
		return true
	}

	return false
}
