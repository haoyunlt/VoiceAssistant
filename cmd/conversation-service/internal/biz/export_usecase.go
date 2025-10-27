package biz

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"voiceassistant/cmd/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// ExportFormat 导出格式
type ExportFormat string

const (
	ExportFormatMarkdown ExportFormat = "markdown"
	ExportFormatPDF      ExportFormat = "pdf"
	ExportFormatJSON     ExportFormat = "json"
	ExportFormatHTML     ExportFormat = "html"
)

// ExportUsecase 导出用例
type ExportUsecase struct {
	convRepo    domain.ConversationRepository
	messageRepo domain.MessageRepository
	log         *log.Helper
}

// NewExportUsecase 创建导出用例
func NewExportUsecase(
	convRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
	logger log.Logger,
) *ExportUsecase {
	return &ExportUsecase{
		convRepo:    convRepo,
		messageRepo: messageRepo,
		log:         log.NewHelper(logger),
	}
}

// ExportConversation 导出对话
func (uc *ExportUsecase) ExportConversation(
	ctx context.Context,
	conversationID, userID string,
	format ExportFormat,
) ([]byte, string, error) {
	// 1. 获取对话
	conversation, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, "", fmt.Errorf("获取对话失败: %w", err)
	}

	// 2. 检查权限
	if conversation.UserID != userID {
		return nil, "", fmt.Errorf("无权导出该对话")
	}

	// 3. 获取所有消息
	messages, _, err := uc.messageRepo.ListMessages(ctx, conversationID, 10000, 0)
	if err != nil {
		return nil, "", fmt.Errorf("获取消息列表失败: %w", err)
	}

	// 4. 根据格式导出
	var data []byte
	var filename string

	switch format {
	case ExportFormatMarkdown:
		data = uc.exportAsMarkdown(conversation, messages)
		filename = fmt.Sprintf("conversation_%s_%s.md", conversationID, time.Now().Format("20060102_150405"))
	case ExportFormatPDF:
		data, err = uc.exportAsPDF(conversation, messages)
		if err != nil {
			return nil, "", fmt.Errorf("导出PDF失败: %w", err)
		}
		filename = fmt.Sprintf("conversation_%s_%s.pdf", conversationID, time.Now().Format("20060102_150405"))
	case ExportFormatJSON:
		data = uc.exportAsJSON(conversation, messages)
		filename = fmt.Sprintf("conversation_%s_%s.json", conversationID, time.Now().Format("20060102_150405"))
	case ExportFormatHTML:
		data = uc.exportAsHTML(conversation, messages)
		filename = fmt.Sprintf("conversation_%s_%s.html", conversationID, time.Now().Format("20060102_150405"))
	default:
		return nil, "", fmt.Errorf("不支持的导出格式: %s", format)
	}

	return data, filename, nil
}

// exportAsMarkdown 导出为Markdown格式
func (uc *ExportUsecase) exportAsMarkdown(conversation *domain.Conversation, messages []*domain.Message) []byte {
	var buf bytes.Buffer

	// 标题
	buf.WriteString(fmt.Sprintf("# %s\n\n", conversation.Title))

	// 元数据
	buf.WriteString("## 对话信息\n\n")
	buf.WriteString(fmt.Sprintf("- **对话ID**: %s\n", conversation.ID))
	buf.WriteString(fmt.Sprintf("- **创建时间**: %s\n", conversation.CreatedAt.Format("2006-01-02 15:04:05")))
	buf.WriteString(fmt.Sprintf("- **最后活跃**: %s\n", conversation.LastActiveAt.Format("2006-01-02 15:04:05")))
	buf.WriteString(fmt.Sprintf("- **消息数量**: %d\n", conversation.MessageCount))
	buf.WriteString(fmt.Sprintf("- **模式**: %s\n", conversation.Mode))
	buf.WriteString("\n---\n\n")

	// 消息内容
	buf.WriteString("## 对话内容\n\n")

	for i, msg := range messages {
		// 角色
		role := "未知"
		switch msg.Role {
		case domain.RoleUser:
			role = "👤 用户"
		case domain.RoleAssistant:
			role = "🤖 助手"
		case domain.RoleSystem:
			role = "⚙️ 系统"
		}

		buf.WriteString(fmt.Sprintf("### 消息 %d - %s\n\n", i+1, role))
		buf.WriteString(fmt.Sprintf("**时间**: %s\n\n", msg.CreatedAt.Format("2006-01-02 15:04:05")))
		buf.WriteString(fmt.Sprintf("%s\n\n", msg.Content))

		// 附件信息
		if len(msg.Attachments) > 0 {
			buf.WriteString("**附件**:\n")
			for _, att := range msg.Attachments {
				buf.WriteString(fmt.Sprintf("- %s (%s)\n", att.Name, att.Type))
			}
			buf.WriteString("\n")
		}

		buf.WriteString("---\n\n")
	}

	// 统计信息
	buf.WriteString("## 统计信息\n\n")
	userMsgCount := 0
	assistantMsgCount := 0
	for _, msg := range messages {
		if msg.Role == domain.RoleUser {
			userMsgCount++
		} else if msg.Role == domain.RoleAssistant {
			assistantMsgCount++
		}
	}
	buf.WriteString(fmt.Sprintf("- 用户消息: %d\n", userMsgCount))
	buf.WriteString(fmt.Sprintf("- 助手消息: %d\n", assistantMsgCount))
	buf.WriteString(fmt.Sprintf("- 总消息数: %d\n", len(messages)))

	return buf.Bytes()
}

// exportAsPDF 导出为PDF格式
func (uc *ExportUsecase) exportAsPDF(conversation *domain.Conversation, messages []*domain.Message) ([]byte, error) {
	// 实现PDF导出
	// 可以使用第三方库如 gofpdf 或 调用外部服务

	// 简化实现：先生成HTML，然后转换为PDF
	htmlContent := uc.exportAsHTML(conversation, messages)

	// TODO: 使用wkhtmltopdf或类似工具转换HTML为PDF
	// 这里返回HTML作为临时方案
	return htmlContent, nil
}

// exportAsJSON 导出为JSON格式
func (uc *ExportUsecase) exportAsJSON(conversation *domain.Conversation, messages []*domain.Message) []byte {
	export := map[string]interface{}{
		"conversation": conversation,
		"messages":     messages,
		"exported_at":  time.Now(),
	}

	data, _ := json.MarshalIndent(export, "", "  ")
	return data
}

// exportAsHTML 导出为HTML格式
func (uc *ExportUsecase) exportAsHTML(conversation *domain.Conversation, messages []*domain.Message) []byte {
	var buf bytes.Buffer

	// HTML头部
	buf.WriteString("<!DOCTYPE html>\n")
	buf.WriteString("<html lang='zh-CN'>\n")
	buf.WriteString("<head>\n")
	buf.WriteString("  <meta charset='UTF-8'>\n")
	buf.WriteString("  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n")
	buf.WriteString(fmt.Sprintf("  <title>%s</title>\n", uc.escapeHTML(conversation.Title)))
	buf.WriteString("  <style>\n")
	buf.WriteString(uc.getHTMLStyles())
	buf.WriteString("  </style>\n")
	buf.WriteString("</head>\n")
	buf.WriteString("<body>\n")

	// 标题
	buf.WriteString("  <div class='container'>\n")
	buf.WriteString(fmt.Sprintf("    <h1>%s</h1>\n", uc.escapeHTML(conversation.Title)))

	// 元数据
	buf.WriteString("    <div class='metadata'>\n")
	buf.WriteString(fmt.Sprintf("      <p><strong>对话ID:</strong> %s</p>\n", conversation.ID))
	buf.WriteString(fmt.Sprintf("      <p><strong>创建时间:</strong> %s</p>\n", conversation.CreatedAt.Format("2006-01-02 15:04:05")))
	buf.WriteString(fmt.Sprintf("      <p><strong>最后活跃:</strong> %s</p>\n", conversation.LastActiveAt.Format("2006-01-02 15:04:05")))
	buf.WriteString(fmt.Sprintf("      <p><strong>消息数量:</strong> %d</p>\n", conversation.MessageCount))
	buf.WriteString("    </div>\n")

	// 消息内容
	buf.WriteString("    <div class='messages'>\n")
	for _, msg := range messages {
		roleClass := "message-user"
		roleIcon := "👤"
		roleName := "用户"

		switch msg.Role {
		case domain.RoleAssistant:
			roleClass = "message-assistant"
			roleIcon = "🤖"
			roleName = "助手"
		case domain.RoleSystem:
			roleClass = "message-system"
			roleIcon = "⚙️"
			roleName = "系统"
		}

		buf.WriteString(fmt.Sprintf("      <div class='message %s'>\n", roleClass))
		buf.WriteString("        <div class='message-header'>\n")
		buf.WriteString(fmt.Sprintf("          <span class='role'>%s %s</span>\n", roleIcon, roleName))
		buf.WriteString(fmt.Sprintf("          <span class='time'>%s</span>\n", msg.CreatedAt.Format("2006-01-02 15:04:05")))
		buf.WriteString("        </div>\n")
		buf.WriteString(fmt.Sprintf("        <div class='message-content'>%s</div>\n", uc.escapeHTML(msg.Content)))
		buf.WriteString("      </div>\n")
	}
	buf.WriteString("    </div>\n")

	// 页脚
	buf.WriteString("    <div class='footer'>\n")
	buf.WriteString(fmt.Sprintf("      <p>导出时间: %s</p>\n", time.Now().Format("2006-01-02 15:04:05")))
	buf.WriteString("    </div>\n")
	buf.WriteString("  </div>\n")

	buf.WriteString("</body>\n")
	buf.WriteString("</html>\n")

	return buf.Bytes()
}

// getHTMLStyles 获取HTML样式
func (uc *ExportUsecase) getHTMLStyles() string {
	return `
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 900px;
      margin: 0 auto;
      padding: 20px;
      background-color: #f5f5f5;
    }
    .container {
      background-color: white;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    h1 {
      color: #2c3e50;
      border-bottom: 3px solid #3498db;
      padding-bottom: 10px;
    }
    .metadata {
      background-color: #ecf0f1;
      padding: 15px;
      border-radius: 5px;
      margin: 20px 0;
    }
    .metadata p {
      margin: 5px 0;
    }
    .messages {
      margin-top: 30px;
    }
    .message {
      margin: 15px 0;
      padding: 15px;
      border-radius: 8px;
      border-left: 4px solid #3498db;
    }
    .message-user {
      background-color: #e3f2fd;
      border-left-color: #2196f3;
    }
    .message-assistant {
      background-color: #f1f8e9;
      border-left-color: #8bc34a;
    }
    .message-system {
      background-color: #fff3e0;
      border-left-color: #ff9800;
    }
    .message-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
      font-size: 14px;
    }
    .role {
      font-weight: bold;
    }
    .time {
      color: #666;
    }
    .message-content {
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .footer {
      margin-top: 30px;
      padding-top: 15px;
      border-top: 1px solid #ddd;
      text-align: center;
      color: #666;
      font-size: 12px;
    }
  `
}

// escapeHTML 转义HTML特殊字符
func (uc *ExportUsecase) escapeHTML(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, "\"", "&quot;")
	s = strings.ReplaceAll(s, "'", "&#39;")
	return s
}
