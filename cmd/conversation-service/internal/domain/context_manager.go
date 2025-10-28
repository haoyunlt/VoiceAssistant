package domain

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// ContextManagerImpl 上下文管理器实现
type ContextManagerImpl struct {
	messageRepo    MessageRepository
	contextRepo    ContextRepository
	maxTokens      int
	windowStrategy WindowStrategy
}

// ContextOptions 上下文选项
type ContextOptions struct {
	MaxMessages   int
	MaxTokens     int
	IncludeSystem bool
	CompressOld   bool
	Priority      string // recent, relevant, mixed
}

// ManagedContext 管理的对话上下文
type ManagedContext struct {
	ConversationID    string
	Messages          []*Message
	CompressedSummary string
	TotalTokens       int
	Strategy          string
	GeneratedAt       time.Time
	CacheKey          string
}

// NewContextManager 创建上下文管理器
func NewContextManager(
	messageRepo MessageRepository,
	contextRepo ContextRepository,
	maxTokens int,
) *ContextManagerImpl {
	return &ContextManagerImpl{
		messageRepo:    messageRepo,
		contextRepo:    contextRepo,
		maxTokens:      maxTokens,
		windowStrategy: &RecentWindowStrategy{},
	}
}

// GetContext 获取上下文（智能策略）
func (m *ContextManagerImpl) GetContext(
	ctx context.Context,
	conversationID string,
	options *ContextOptions,
) (*ManagedContext, error) {
	if options == nil {
		options = &ContextOptions{
			MaxMessages:   20,
			MaxTokens:     4000,
			IncludeSystem: true,
			Priority:      "recent",
		}
	}

	// 1. 尝试从缓存获取
	cached, err := m.contextRepo.GetCached(ctx, conversationID)
	if err == nil && cached != nil && m.isValidConversationContext(cached) {
		// 转换为 ManagedContext
		return m.convertToManagedContext(cached), nil
	}

	// 2. 根据策略获取消息
	messages, err := m.windowStrategy.Select(ctx, m.messageRepo, conversationID, options)
	if err != nil {
		return nil, err
	}

	// 3. 计算总Token数
	totalTokens := m.estimateTokens(messages)

	// 4. 如果超过限制，进行裁剪
	if totalTokens > options.MaxTokens {
		messages = m.trimMessages(messages, options.MaxTokens)
		totalTokens = m.estimateTokens(messages)
	}

	// 5. 构建上下文
	contextData := &ManagedContext{
		ConversationID: conversationID,
		Messages:       messages,
		TotalTokens:    totalTokens,
		Strategy:       options.Priority,
		GeneratedAt:    time.Now(),
		CacheKey:       fmt.Sprintf("context:%s", conversationID),
	}

	// 6. 缓存结果
	convContext := m.convertToConversationContext(contextData)
	_ = m.contextRepo.Cache(ctx, convContext, 5*time.Minute)

	return contextData, nil
}

// UpdateContext 更新上下文（增量）
func (m *ContextManagerImpl) UpdateContext(
	ctx context.Context,
	conversationID string,
	newMessage *Message,
) error {
	// 1. 获取当前缓存的上下文
	cached, err := m.contextRepo.GetCached(ctx, conversationID)
	if err != nil {
		// 缓存不存在，不需要更新
		return nil
	}

	// 2. 转换为 ManagedContext
	managed := m.convertToManagedContext(cached)

	// 3. 追加新消息
	managed.Messages = append(managed.Messages, newMessage)
	managed.TotalTokens += m.estimateTokens([]*Message{newMessage})
	managed.GeneratedAt = time.Now()

	// 4. 检查是否超过限制
	if managed.TotalTokens > m.maxTokens {
		// 裁剪旧消息
		managed.Messages = m.trimMessages(managed.Messages, m.maxTokens)
		managed.TotalTokens = m.estimateTokens(managed.Messages)
	}

	// 5. 转换回 ConversationContext 并更新缓存
	convContext := m.convertToConversationContext(managed)
	return m.contextRepo.Cache(ctx, convContext, 5*time.Minute)
}

// CompressContext 压缩上下文（长对话优化）
func (m *ContextManagerImpl) CompressContext(
	ctx context.Context,
	conversationID string,
) error {
	// 获取对话历史
	messages, err := m.messageRepo.GetRecentMessages(ctx, conversationID, 100)
	if err != nil {
		return err
	}

	if len(messages) < 10 {
		// 消息数量少，不需要压缩
		return nil
	}

	// 1. 保留最近的N条消息（不压缩）
	recentCount := 5
	if len(messages) <= recentCount {
		return nil
	}

	// 2. 对较早的消息进行压缩（摘要）
	oldMessages := messages[:len(messages)-recentCount]
	summary := m.generateSummary(oldMessages)

	// 3. 创建系统摘要消息
	summaryMsg := &Message{
		ConversationID: conversationID,
		Role:           RoleSystem,
		Content:        fmt.Sprintf("Previous conversation summary: %s", summary),
		ContentType:    ContentTypeText,
		Metadata: map[string]string{
			"compressed_message_count": fmt.Sprintf("%d", len(oldMessages)),
			"compression_time":         time.Now().Format(time.RFC3339),
		},
	}

	// 4. 保存摘要（可以选择删除旧消息或标记为已压缩）
	// 这里简化实现，只创建摘要消息
	// 实际应用中可能需要：
	// - 标记旧消息为已压缩
	// - 或者将旧消息移到归档表
	// - 或者直接删除非关键消息

	// 保存摘要消息
	if err := m.messageRepo.CreateMessage(ctx, summaryMsg); err != nil {
		return fmt.Errorf("save summary message: %w", err)
	}

	return nil
}

// generateSummary 生成对话摘要
func (m *ContextManagerImpl) generateSummary(messages []*Message) string {
	if len(messages) == 0 {
		return ""
	}

	// 简单实现：提取关键信息
	// 实际应用中应该调用LLM API进行智能摘要
	var keyPoints []string

	// 提取用户问题
	var userQuestions []string
	var assistantResponses []string

	for _, msg := range messages {
		if msg.Role == "user" {
			if len(msg.Content) > 100 {
				userQuestions = append(userQuestions, msg.Content[:100]+"...")
			} else {
				userQuestions = append(userQuestions, msg.Content)
			}
		} else if msg.Role == "assistant" {
			if len(msg.Content) > 150 {
				assistantResponses = append(assistantResponses, msg.Content[:150]+"...")
			} else {
				assistantResponses = append(assistantResponses, msg.Content)
			}
		}
	}

	// 限制摘要长度
	maxQuestions := 3
	maxResponses := 3

	if len(userQuestions) > maxQuestions {
		userQuestions = userQuestions[len(userQuestions)-maxQuestions:]
	}
	if len(assistantResponses) > maxResponses {
		assistantResponses = assistantResponses[len(assistantResponses)-maxResponses:]
	}

	// 构建摘要
	if len(userQuestions) > 0 {
		keyPoints = append(keyPoints, "User asked about: "+strings.Join(userQuestions, "; "))
	}
	if len(assistantResponses) > 0 {
		keyPoints = append(keyPoints, "Assistant discussed: "+strings.Join(assistantResponses, "; "))
	}

	summary := strings.Join(keyPoints, " ")

	// TODO: 实际应该调用LLM API进行更智能的摘要
	// 例如: callLLMForSummary(messages)

	return summary
}

// estimateTokens 估算Token数（简单实现）
func (m *ContextManagerImpl) estimateTokens(messages []*Message) int {
	total := 0
	for _, msg := range messages {
		// 英文约 4 字符 = 1 token，中文约 1.5 字符 = 1 token
		// 简化计算：平均 3 字符 = 1 token
		total += len(msg.Content) / 3
	}
	return total
}

// trimMessages 裁剪消息以适应Token限制
func (m *ContextManagerImpl) trimMessages(messages []*Message, maxTokens int) []*Message {
	if len(messages) == 0 {
		return messages
	}

	// 从最新的消息开始保留
	totalTokens := 0
	var result []*Message

	// 反向遍历
	for i := len(messages) - 1; i >= 0; i-- {
		msgTokens := m.estimateTokens([]*Message{messages[i]})
		if totalTokens+msgTokens > maxTokens {
			break
		}
		result = append([]*Message{messages[i]}, result...)
		totalTokens += msgTokens
	}

	return result
}

// isValid 检查缓存的上下文是否有效
func (m *ContextManagerImpl) isValid(context *ManagedContext) bool {
	// 缓存5分钟内有效
	return time.Since(context.GeneratedAt) < 5*time.Minute
}

// isValidConversationContext 检查 ConversationContext 是否有效
func (m *ContextManagerImpl) isValidConversationContext(context *ConversationContext) bool {
	// 缓存5分钟内有效
	return time.Since(context.UpdatedAt) < 5*time.Minute
}

// SetStrategy 设置窗口策略
func (m *ContextManagerImpl) SetStrategy(strategy WindowStrategy) {
	m.windowStrategy = strategy
}

// convertToManagedContext 将 ConversationContext 转换为 ManagedContext
func (m *ContextManagerImpl) convertToManagedContext(convCtx *ConversationContext) *ManagedContext {
	messages := make([]*Message, len(convCtx.Messages))
	for i, ctxMsg := range convCtx.Messages {
		messages[i] = &Message{
			ID:             ctxMsg.ID,
			ConversationID: convCtx.ConversationID,
			TenantID:       convCtx.TenantID,
			UserID:         convCtx.UserID,
			Role:           MessageRole(ctxMsg.Role),
			Content:        ctxMsg.Content,
			ContentType:    ContentTypeText,
			Tokens:         ctxMsg.Tokens,
			CreatedAt:      ctxMsg.Timestamp,
		}
	}

	return &ManagedContext{
		ConversationID: convCtx.ConversationID,
		Messages:       messages,
		TotalTokens:    convCtx.TotalTokens,
		GeneratedAt:    convCtx.UpdatedAt,
		CacheKey:       fmt.Sprintf("context:%s", convCtx.ConversationID),
	}
}

// convertToConversationContext 将 ManagedContext 转换为 ConversationContext
func (m *ContextManagerImpl) convertToConversationContext(managed *ManagedContext) *ConversationContext {
	messages := make([]ContextMessage, len(managed.Messages))
	for i, msg := range managed.Messages {
		messages[i] = ContextMessage{
			ID:        msg.ID,
			Role:      string(msg.Role),
			Content:   msg.Content,
			Tokens:    msg.Tokens,
			Timestamp: msg.CreatedAt,
		}
	}

	return &ConversationContext{
		ConversationID: managed.ConversationID,
		Messages:       messages,
		TotalTokens:    managed.TotalTokens,
		MessageCount:   len(managed.Messages),
		UpdatedAt:      managed.GeneratedAt,
		CreatedAt:      managed.GeneratedAt,
	}
}
