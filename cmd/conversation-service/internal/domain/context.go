package domain

import (
	"time"
)

// Context 对话上下文领域模型
type Context struct {
	ConversationID string
	Messages       []ContextMessage
	MaxTokens      int // 最大 Token 数
	CurrentTokens  int // 当前 Token 数
	UpdatedAt      time.Time
}

// ContextMessage 上下文消息
type ContextMessage struct {
	Role    MessageRole
	Content string
}

// AddMessage 添加消息到上下文
func (c *Context) AddMessage(role MessageRole, content string, tokens int) {
	c.Messages = append(c.Messages, ContextMessage{
		Role:    role,
		Content: content,
	})
	c.CurrentTokens += tokens
	c.UpdatedAt = time.Now()

	// 如果超过最大 Token 数，移除最早的消息
	c.TruncateIfNeeded()
}

// TruncateIfNeeded 如果超过最大 Token 数，截断上下文
func (c *Context) TruncateIfNeeded() {
	// 保留系统消息和最新的消息
	if c.CurrentTokens > c.MaxTokens && len(c.Messages) > 2 {
		// 简单策略：移除最早的非系统消息
		for i := 0; i < len(c.Messages); i++ {
			if c.Messages[i].Role != MessageRoleSystem {
				// 移除这条消息
				c.Messages = append(c.Messages[:i], c.Messages[i+1:]...)
				// 重新计算 Token（简化处理）
				c.CurrentTokens = c.EstimateTokens()
				break
			}
		}
	}
}

// EstimateTokens 估算 Token 数量（简化实现）
func (c *Context) EstimateTokens() int {
	// 简化估算：每个字符约 0.25 个 token
	totalChars := 0
	for _, msg := range c.Messages {
		totalChars += len(msg.Content)
	}
	return totalChars / 4
}

// Clear 清空上下文
func (c *Context) Clear() {
	c.Messages = []ContextMessage{}
	c.CurrentTokens = 0
	c.UpdatedAt = time.Now()
}

// ToMessages 转换为消息列表
func (c *Context) ToMessages() []ContextMessage {
	return c.Messages
}

// ContextRepository 上下文仓储接口（使用 Redis）
type ContextRepository interface {
	// Get 获取上下文
	Get(conversationID string) (*Context, error)

	// Set 设置上下文
	Set(context *Context) error

	// Delete 删除上下文
	Delete(conversationID string) error

	// Exists 检查上下文是否存在
	Exists(conversationID string) (bool, error)
}
