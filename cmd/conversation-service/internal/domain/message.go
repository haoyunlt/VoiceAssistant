package domain

import "time"

// Message 消息实体
type Message struct {
	ID             string
	ConversationID string
	TenantID       string
	UserID         string
	Role           MessageRole
	Content        string
	ContentType    ContentType
	Tokens         int
	Model          string
	Provider       string
	Status         string          // 状态：active, deleted, recalled
	Edited         bool            // 是否已编辑
	EditCount      int             // 编辑次数
	EditHistory    []MessageEdit   // 编辑历史
	RecalledAt     time.Time       // 撤回时间
	DeletedAt      time.Time       // 删除时间
	UpdatedAt      time.Time       // 更新时间
	Metadata       map[string]string
	CreatedAt      time.Time
}

// MessageEdit 消息编辑记录
type MessageEdit struct {
	OriginalContent string    // 原始内容
	EditedAt        time.Time // 编辑时间
}

// MessageRole 消息角色
type MessageRole string

const (
	RoleUser      MessageRole = "user"      // 用户
	RoleAssistant MessageRole = "assistant" // 助手
	RoleSystem    MessageRole = "system"    // 系统
	RoleTool      MessageRole = "tool"      // 工具
)

// ContentType 内容类型
type ContentType string

const (
	ContentTypeText  ContentType = "text"  // 文本
	ContentTypeAudio ContentType = "audio" // 音频
	ContentTypeImage ContentType = "image" // 图像
	ContentTypeVideo ContentType = "video" // 视频
)

// NewMessage 创建消息
func NewMessage(conversationID, tenantID, userID string, role MessageRole, content string) *Message {
	return &Message{
		ID:             generateMessageID(),
		ConversationID: conversationID,
		TenantID:       tenantID,
		UserID:         userID,
		Role:           role,
		Content:        content,
		ContentType:    ContentTypeText,
		Tokens:         0,
		Metadata:       make(map[string]string),
		CreatedAt:      time.Now(),
	}
}

// SetTokens 设置 Token 数
func (m *Message) SetTokens(tokens int) {
	m.Tokens = tokens
}

// SetModel 设置模型信息
func (m *Message) SetModel(model, provider string) {
	m.Model = model
	m.Provider = provider
}

func generateMessageID() string {
	// 简化实现，实际应使用 UUID
	return "msg_" + time.Now().Format("20060102150405")
}
