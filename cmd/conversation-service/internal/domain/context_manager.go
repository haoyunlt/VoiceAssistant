package domain

import (
	"context"
	"fmt"
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
	if err == nil && cached != nil && m.isValid(cached) {
		return cached, nil
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
	_ = m.contextRepo.Cache(ctx, contextData, 5*time.Minute)

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

	// 2. 追加新消息
	cached.Messages = append(cached.Messages, newMessage)
	cached.TotalTokens += m.estimateTokens([]*Message{newMessage})
	cached.GeneratedAt = time.Now()

	// 3. 检查是否超过限制
	if cached.TotalTokens > m.maxTokens {
		// 裁剪旧消息
		cached.Messages = m.trimMessages(cached.Messages, m.maxTokens)
		cached.TotalTokens = m.estimateTokens(cached.Messages)
	}

	// 4. 更新缓存
	return m.contextRepo.Cache(ctx, cached, 5*time.Minute)
}

// CompressContext 压缩上下文（长对话优化）
func (m *ContextManagerImpl) CompressContext(
	ctx context.Context,
	conversationID string,
) error {
	// TODO: 实现上下文压缩逻辑
	// 可以使用LLM对历史对话进行摘要
	return nil
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

// SetStrategy 设置窗口策略
func (m *ContextManagerImpl) SetStrategy(strategy WindowStrategy) {
	m.windowStrategy = strategy
}
