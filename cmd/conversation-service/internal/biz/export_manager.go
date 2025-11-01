package biz

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/conversation-service/internal/domain"
)

// ExportManager 导出管理器
type ExportManager struct {
	conversationRepo domain.ConversationRepository
	messageRepo      domain.MessageRepository
	logger           *log.Helper
}

// ExportFormat 导出格式
type ExportFormat string

const (
	ExportFormatJSON     ExportFormat = "json"
	ExportFormatMarkdown ExportFormat = "markdown"
	ExportFormatText     ExportFormat = "text"
	ExportFormatHTML     ExportFormat = "html"
)

// ExportOptions 导出选项
type ExportOptions struct {
	Format          ExportFormat  `json:"format"`
	IncludeMetadata bool          `json:"include_metadata"`
	IncludeSystem   bool          `json:"include_system"` // 是否包含系统消息
	TimeFormat      string        `json:"time_format"`
	StartTime       *time.Time    `json:"start_time,omitempty"`
	EndTime         *time.Time    `json:"end_time,omitempty"`
}

// ExportedConversation 导出的对话
type ExportedConversation struct {
	Conversation *domain.Conversation `json:"conversation"`
	Messages     []*ExportedMessage   `json:"messages"`
	ExportedAt   time.Time            `json:"exported_at"`
	Format       string               `json:"format"`
}

// ExportedMessage 导出的消息
type ExportedMessage struct {
	ID        string            `json:"id"`
	Role      string            `json:"role"`
	Content   string            `json:"content"`
	CreatedAt time.Time         `json:"created_at"`
	Metadata  map[string]string `json:"metadata,omitempty"`
}

// NewExportManager 创建导出管理器
func NewExportManager(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
	logger log.Logger,
) *ExportManager {
	return &ExportManager{
		conversationRepo: conversationRepo,
		messageRepo:      messageRepo,
		logger:           log.NewHelper(log.With(logger, "module", "export-manager")),
	}
}

// ExportConversation 导出对话
func (em *ExportManager) ExportConversation(
	ctx context.Context,
	conversationID, userID string,
	options *ExportOptions,
) ([]byte, string, error) {
	// 1. 获取对话
	conversation, err := em.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, "", err
	}

	// 2. 权限检查
	if conversation.UserID != userID {
		return nil, "", domain.ErrPermissionDenied
	}

	// 3. 获取消息
	messages, err := em.messageRepo.ListMessages(ctx, conversationID, 10000, 0)
	if err != nil {
		return nil, "", fmt.Errorf("failed to list messages: %w", err)
	}

	// 4. 应用默认选项
	if options == nil {
		options = &ExportOptions{
			Format:          ExportFormatJSON,
			IncludeMetadata: true,
			IncludeSystem:   true,
			TimeFormat:      time.RFC3339,
		}
	}

	// 5. 过滤消息
	filteredMessages := em.filterMessages(messages, options)

	// 6. 根据格式导出
	var content []byte
	var filename string

	switch options.Format {
	case ExportFormatJSON:
		content, err = em.exportJSON(conversation, filteredMessages, options)
		filename = fmt.Sprintf("conversation_%s_%s.json", conversationID, time.Now().Format("20060102_150405"))

	case ExportFormatMarkdown:
		content, err = em.exportMarkdown(conversation, filteredMessages, options)
		filename = fmt.Sprintf("conversation_%s_%s.md", conversationID, time.Now().Format("20060102_150405"))

	case ExportFormatText:
		content, err = em.exportText(conversation, filteredMessages, options)
		filename = fmt.Sprintf("conversation_%s_%s.txt", conversationID, time.Now().Format("20060102_150405"))

	case ExportFormatHTML:
		content, err = em.exportHTML(conversation, filteredMessages, options)
		filename = fmt.Sprintf("conversation_%s_%s.html", conversationID, time.Now().Format("20060102_150405"))

	default:
		return nil, "", fmt.Errorf("unsupported export format: %s", options.Format)
	}

	if err != nil {
		return nil, "", err
	}

	em.logger.Infof("Conversation exported: id=%s, format=%s, messages=%d",
		conversationID, options.Format, len(filteredMessages))

	return content, filename, nil
}

// exportJSON 导出为 JSON
func (em *ExportManager) exportJSON(
	conversation *domain.Conversation,
	messages []*domain.Message,
	options *ExportOptions,
) ([]byte, error) {
	exportedMessages := make([]*ExportedMessage, 0, len(messages))

	for _, msg := range messages {
		exported := &ExportedMessage{
			ID:        msg.ID,
			Role:      string(msg.Role),
			Content:   msg.Content,
			CreatedAt: msg.CreatedAt,
		}

		if options.IncludeMetadata {
			exported.Metadata = msg.Metadata
		}

		exportedMessages = append(exportedMessages, exported)
	}

	exported := &ExportedConversation{
		Conversation: conversation,
		Messages:     exportedMessages,
		ExportedAt:   time.Now(),
		Format:       string(ExportFormatJSON),
	}

	data, err := json.MarshalIndent(exported, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("failed to marshal JSON: %w", err)
	}

	return data, nil
}

// exportMarkdown 导出为 Markdown
func (em *ExportManager) exportMarkdown(
	conversation *domain.Conversation,
	messages []*domain.Message,
	options *ExportOptions,
) ([]byte, error) {
	var buf bytes.Buffer

	// 标题
	buf.WriteString(fmt.Sprintf("# %s\n\n", conversation.Title))

	// 元数据
	if options.IncludeMetadata {
		buf.WriteString("## Metadata\n\n")
		buf.WriteString(fmt.Sprintf("- **ID**: %s\n", conversation.ID))
		buf.WriteString(fmt.Sprintf("- **Mode**: %s\n", conversation.Mode))
		buf.WriteString(fmt.Sprintf("- **Status**: %s\n", conversation.Status))
		buf.WriteString(fmt.Sprintf("- **Created**: %s\n", conversation.CreatedAt.Format(time.RFC3339)))
		buf.WriteString(fmt.Sprintf("- **Updated**: %s\n", conversation.UpdatedAt.Format(time.RFC3339)))
		buf.WriteString(fmt.Sprintf("- **Messages**: %d\n\n", len(messages)))
	}

	// 消息
	buf.WriteString("## Messages\n\n")

	for i, msg := range messages {
		// 角色标记
		roleEmoji := em.getRoleEmoji(string(msg.Role))
		buf.WriteString(fmt.Sprintf("### %s Message %d\n\n", roleEmoji, i+1))

		// 时间戳
		buf.WriteString(fmt.Sprintf("**Time**: %s\n\n", msg.CreatedAt.Format(options.TimeFormat)))

		// 内容
		buf.WriteString(fmt.Sprintf("%s\n\n", msg.Content))

		// 分隔线
		if i < len(messages)-1 {
			buf.WriteString("---\n\n")
		}
	}

	// 导出信息
	buf.WriteString(fmt.Sprintf("\n---\n*Exported at %s*\n", time.Now().Format(time.RFC3339)))

	return buf.Bytes(), nil
}

// exportText 导出为纯文本
func (em *ExportManager) exportText(
	conversation *domain.Conversation,
	messages []*domain.Message,
	options *ExportOptions,
) ([]byte, error) {
	var buf bytes.Buffer

	// 标题
	buf.WriteString(fmt.Sprintf("%s\n", conversation.Title))
	buf.WriteString(strings.Repeat("=", len(conversation.Title)) + "\n\n")

	// 元数据
	if options.IncludeMetadata {
		buf.WriteString(fmt.Sprintf("Created: %s\n", conversation.CreatedAt.Format(options.TimeFormat)))
		buf.WriteString(fmt.Sprintf("Messages: %d\n\n", len(messages)))
	}

	// 消息
	for i, msg := range messages {
		// 角色
		buf.WriteString(fmt.Sprintf("[%s] ", strings.ToUpper(string(msg.Role))))

		// 时间
		buf.WriteString(fmt.Sprintf("(%s)\n", msg.CreatedAt.Format(options.TimeFormat)))

		// 内容
		buf.WriteString(fmt.Sprintf("%s\n", msg.Content))

		// 空行
		if i < len(messages)-1 {
			buf.WriteString("\n")
		}
	}

	// 导出信息
	buf.WriteString(fmt.Sprintf("\n---\nExported at %s\n", time.Now().Format(time.RFC3339)))

	return buf.Bytes(), nil
}

// exportHTML 导出为 HTML
func (em *ExportManager) exportHTML(
	conversation *domain.Conversation,
	messages []*domain.Message,
	options *ExportOptions,
) ([]byte, error) {
	var buf bytes.Buffer

	// HTML 头部
	buf.WriteString(`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>` + conversation.Title + `</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .metadata {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .message {
            margin: 20px 0;
            padding: 15px;
            border-radius: 8px;
        }
        .message.user {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
        }
        .message.assistant {
            background: #f3e5f5;
            border-left: 4px solid #9c27b0;
        }
        .message.system {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
        }
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 12px;
            color: #666;
        }
        .role {
            font-weight: bold;
            text-transform: uppercase;
        }
        .content {
            white-space: pre-wrap;
            line-height: 1.6;
        }
        .footer {
            text-align: center;
            color: #999;
            margin-top: 30px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>` + conversation.Title + `</h1>
`)

	// 元数据
	if options.IncludeMetadata {
		buf.WriteString(`        <div class="metadata">
            <p><strong>ID:</strong> ` + conversation.ID + `</p>
            <p><strong>Created:</strong> ` + conversation.CreatedAt.Format(time.RFC3339) + `</p>
            <p><strong>Messages:</strong> ` + fmt.Sprintf("%d", len(messages)) + `</p>
        </div>
`)
	}

	// 消息
	for _, msg := range messages {
		role := string(msg.Role)
		buf.WriteString(fmt.Sprintf(`        <div class="message %s">
            <div class="message-header">
                <span class="role">%s</span>
                <span class="time">%s</span>
            </div>
            <div class="content">%s</div>
        </div>
`, role, role, msg.CreatedAt.Format(options.TimeFormat), em.escapeHTML(msg.Content)))
	}

	// HTML 尾部
	buf.WriteString(`        <div class="footer">
            <p>Exported at ` + time.Now().Format(time.RFC3339) + `</p>
        </div>
    </div>
</body>
</html>`)

	return buf.Bytes(), nil
}

// filterMessages 过滤消息
func (em *ExportManager) filterMessages(messages []*domain.Message, options *ExportOptions) []*domain.Message {
	filtered := make([]*domain.Message, 0, len(messages))

	for _, msg := range messages {
		// 过滤系统消息
		if !options.IncludeSystem && msg.Role == domain.RoleSystem {
			continue
		}

		// 时间过滤
		if options.StartTime != nil && msg.CreatedAt.Before(*options.StartTime) {
			continue
		}
		if options.EndTime != nil && msg.CreatedAt.After(*options.EndTime) {
			continue
		}

		filtered = append(filtered, msg)
	}

	return filtered
}

// getRoleEmoji 获取角色 emoji
func (em *ExportManager) getRoleEmoji(role string) string {
	switch role {
	case "user":
		return "👤"
	case "assistant":
		return "🤖"
	case "system":
		return "⚙️"
	case "tool":
		return "🔧"
	default:
		return "💬"
	}
}

// escapeHTML HTML 转义
func (em *ExportManager) escapeHTML(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, "\"", "&quot;")
	s = strings.ReplaceAll(s, "'", "&#39;")
	return s
}

// BatchExport 批量导出对话
func (em *ExportManager) BatchExport(
	ctx context.Context,
	conversationIDs []string,
	userID string,
	options *ExportOptions,
) (map[string][]byte, error) {
	results := make(map[string][]byte)

	for _, convID := range conversationIDs {
		content, _, err := em.ExportConversation(ctx, convID, userID, options)
		if err != nil {
			em.logger.Errorf("Failed to export conversation %s: %v", convID, err)
			continue
		}

		results[convID] = content
	}

	return results, nil
}

