package domain

import "time"

// Conversation 对话聚合根
type Conversation struct {
	ID          string
	TenantID    string
	UserID      string
	Title       string
	Mode        ConversationMode
	Status      ConversationStatus
	Context     *ConversationContext
	Metadata    map[string]string
	CreatedAt   time.Time
	UpdatedAt   time.Time
	LastActiveAt time.Time
}

// ConversationMode 对话模式
type ConversationMode string

const (
	ModeText  ConversationMode = "text"  // 文本对话
	ModeVoice ConversationMode = "voice" // 语音对话
	ModeVideo ConversationMode = "video" // 视频对话
)

// ConversationStatus 对话状态
type ConversationStatus string

const (
	StatusActive   ConversationStatus = "active"   // 活跃
	StatusPaused   ConversationStatus = "paused"   // 暂停
	StatusArchived ConversationStatus = "archived" // 归档
	StatusDeleted  ConversationStatus = "deleted"  // 删除
)

// ConversationContext 对话上下文
type ConversationContext struct {
	MaxMessages     int               // 最大消息数
	CurrentMessages int               // 当前消息数
	TokenLimit      int               // Token 限制
	CurrentTokens   int               // 当前 Token 数
	SystemPrompt    string            // 系统提示词
	Variables       map[string]string // 上下文变量
}

// NewConversation 创建对话
func NewConversation(tenantID, userID, title string, mode ConversationMode) *Conversation {
	now := time.Now()
	return &Conversation{
		ID:          generateConversationID(),
		TenantID:    tenantID,
		UserID:      userID,
		Title:       title,
		Mode:        mode,
		Status:      StatusActive,
		Context: &ConversationContext{
			MaxMessages:   100,
			CurrentMessages: 0,
			TokenLimit:    4000,
			CurrentTokens: 0,
			Variables:     make(map[string]string),
		},
		Metadata:     make(map[string]string),
		CreatedAt:    now,
		UpdatedAt:    now,
		LastActiveAt: now,
	}
}

// UpdateTitle 更新标题
func (c *Conversation) UpdateTitle(title string) {
	c.Title = title
	c.UpdatedAt = time.Now()
}

// Archive 归档对话
func (c *Conversation) Archive() error {
	if c.Status == StatusDeleted {
		return ErrConversationDeleted
	}
	c.Status = StatusArchived
	c.UpdatedAt = time.Now()
	return nil
}

// Delete 删除对话
func (c *Conversation) Delete() {
	c.Status = StatusDeleted
	c.UpdatedAt = time.Now()
}

// UpdateActivity 更新活跃时间
func (c *Conversation) UpdateActivity() {
	c.LastActiveAt = time.Now()
	c.UpdatedAt = time.Now()
}

// CanSendMessage 检查是否可以发送消息
func (c *Conversation) CanSendMessage() bool {
	if c.Status != StatusActive {
		return false
	}
	if c.Context.CurrentMessages >= c.Context.MaxMessages {
		return false
	}
	return true
}

// IncrementMessageCount 增加消息计数
func (c *Conversation) IncrementMessageCount() {
	c.Context.CurrentMessages++
	c.UpdateActivity()
}

// AddTokens 添加 Token 计数
func (c *Conversation) AddTokens(tokens int) {
	c.Context.CurrentTokens += tokens
	c.UpdateActivity()
}

func generateConversationID() string {
	// 简化实现，实际应使用 UUID
	return "conv_" + time.Now().Format("20060102150405")
}
