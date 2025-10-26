package domain

import "time"

// ConversationContext 会话上下文
type ConversationContext struct {
	// 会话 ID
	ConversationID string `json:"conversation_id"`

	// 用户 ID
	UserID string `json:"user_id"`

	// 租户 ID
	TenantID string `json:"tenant_id"`

	// 系统提示
	SystemPrompt string `json:"system_prompt"`

	// 消息列表
	Messages []ContextMessage `json:"messages"`

	// 消息数量
	MessageCount int `json:"message_count"`

	// 总 Token 数
	TotalTokens int `json:"total_tokens"`

	// 元数据
	Metadata map[string]string `json:"metadata"`

	// 创建时间
	CreatedAt time.Time `json:"created_at"`

	// 更新时间
	UpdatedAt time.Time `json:"updated_at"`
}

// ContextMessage 上下文消息
type ContextMessage struct {
	// 消息 ID
	ID string `json:"id"`

	// 角色 (user/assistant/system/function)
	Role string `json:"role"`

	// 内容
	Content string `json:"content"`

	// Token 数
	Tokens int `json:"tokens"`

	// 函数调用（可选）
	FunctionCall *FunctionCall `json:"function_call,omitempty"`

	// 时间戳
	Timestamp time.Time `json:"timestamp"`
}

// FunctionCall 函数调用
type FunctionCall struct {
	// 函数名称
	Name string `json:"name"`

	// 参数（JSON 字符串）
	Arguments string `json:"arguments"`
}

// ContextSummary 上下文摘要
type ContextSummary struct {
	// 会话 ID
	ConversationID string `json:"conversation_id"`

	// 用户 ID
	UserID string `json:"user_id"`

	// 租户 ID
	TenantID string `json:"tenant_id"`

	// 消息数量
	MessageCount int `json:"message_count"`

	// 总 Token 数
	TotalTokens int `json:"total_tokens"`

	// 创建时间
	CreatedAt time.Time `json:"created_at"`

	// 更新时间
	UpdatedAt time.Time `json:"updated_at"`
}

// ContextTruncateStrategy 上下文截断策略
type ContextTruncateStrategy string

const (
	// 保留最近的消息
	StrategyKeepRecent ContextTruncateStrategy = "keep_recent"

	// 保留重要消息（基于相似度）
	StrategyKeepImportant ContextTruncateStrategy = "keep_important"

	// 摘要压缩
	StrategySummarize ContextTruncateStrategy = "summarize"
)

// ContextManager 上下文管理器接口
type ContextManager interface {
	// 获取上下文
	GetContext(conversationID string) (*ConversationContext, error)

	// 设置上下文
	SetContext(context *ConversationContext) error

	// 追加消息
	AppendMessage(conversationID string, message ContextMessage) error

	// 截断上下文
	TruncateContext(context *ConversationContext, maxTokens int) *ConversationContext

	// 清空上下文
	ClearContext(conversationID string) error
}
