package biz

import (
	"context"
	"fmt"
	"voiceassistant/cmd/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// SystemMessageService 系统消息服务
type SystemMessageService struct {
	messageRepo domain.MessageRepository
	log         *log.Helper
}

// NewSystemMessageService 创建系统消息服务
func NewSystemMessageService(
	messageRepo domain.MessageRepository,
	logger log.Logger,
) *SystemMessageService {
	return &SystemMessageService{
		messageRepo: messageRepo,
		log:         log.NewHelper(logger),
	}
}

// GetSystemMessages 获取对话中的系统消息
func (s *SystemMessageService) GetSystemMessages(
	ctx context.Context,
	conversationID string,
) ([]*domain.Message, error) {
	s.log.Infof("Getting system messages for conversation: %s", conversationID)

	messages, err := s.messageRepo.GetSystemMessages(ctx, conversationID)
	if err != nil {
		s.log.Errorf("Failed to get system messages: %v", err)
		return nil, err
	}

	s.log.Infof("Found %d system messages", len(messages))
	return messages, nil
}

// GetMessagesByRole 根据角色获取消息
func (s *SystemMessageService) GetMessagesByRole(
	ctx context.Context,
	conversationID string,
	role domain.MessageRole,
	limit int,
) ([]*domain.Message, error) {
	s.log.Infof("Getting messages by role: %s for conversation: %s", role, conversationID)

	messages, err := s.messageRepo.GetMessagesByRole(ctx, conversationID, role, limit)
	if err != nil {
		s.log.Errorf("Failed to get messages by role: %v", err)
		return nil, err
	}

	s.log.Infof("Found %d messages with role %s", len(messages), role)
	return messages, nil
}

// GetTenantSystemMessages 获取租户的所有系统消息（跨对话）
func (s *SystemMessageService) GetTenantSystemMessages(
	ctx context.Context,
	tenantID string,
	limit, offset int,
) ([]*domain.Message, int, error) {
	s.log.Infof("Getting tenant system messages: tenant=%s, limit=%d, offset=%d", tenantID, limit, offset)

	messages, total, err := s.messageRepo.GetMessagesByTenantAndRole(
		ctx,
		tenantID,
		domain.RoleSystem,
		limit,
		offset,
	)
	if err != nil {
		s.log.Errorf("Failed to get tenant system messages: %v", err)
		return nil, 0, err
	}

	s.log.Infof("Found %d/%d tenant system messages", len(messages), total)
	return messages, total, nil
}

// MessageStatistics 消息统计
type MessageStatistics struct {
	ConversationID string          `json:"conversation_id"`
	TotalMessages  int             `json:"total_messages"`
	MessagesByRole map[string]int  `json:"messages_by_role"`
	LatestMessage  *domain.Message `json:"latest_message,omitempty"`
}

// GetMessageStatistics 获取消息统计
func (s *SystemMessageService) GetMessageStatistics(
	ctx context.Context,
	conversationID string,
) (*MessageStatistics, error) {
	s.log.Infof("Getting message statistics for conversation: %s", conversationID)

	stats := &MessageStatistics{
		ConversationID: conversationID,
		MessagesByRole: make(map[string]int),
	}

	// 统计各角色消息数量
	roles := []domain.MessageRole{
		domain.RoleUser,
		domain.RoleAssistant,
		domain.RoleSystem,
		domain.RoleTool,
	}

	totalMessages := 0
	for _, role := range roles {
		count, err := s.messageRepo.CountMessagesByRole(ctx, conversationID, role)
		if err != nil {
			s.log.Warnf("Failed to count messages for role %s: %v", role, err)
			continue
		}
		stats.MessagesByRole[string(role)] = count
		totalMessages += count
	}

	stats.TotalMessages = totalMessages

	// 获取最新消息
	recent, err := s.messageRepo.GetRecentMessages(ctx, conversationID, 1)
	if err == nil && len(recent) > 0 {
		stats.LatestMessage = recent[0]
	}

	s.log.Infof("Message statistics: total=%d, by_role=%v", totalMessages, stats.MessagesByRole)
	return stats, nil
}

// SystemMessageSummary 系统消息摘要
type SystemMessageSummary struct {
	ConversationID      string          `json:"conversation_id"`
	SystemMessageCount  int             `json:"system_message_count"`
	FirstSystemMessage  *domain.Message `json:"first_system_message,omitempty"`
	LatestSystemMessage *domain.Message `json:"latest_system_message,omitempty"`
	SystemInstructions  []string        `json:"system_instructions"`
}

// GetSystemMessageSummary 获取系统消息摘要
func (s *SystemMessageService) GetSystemMessageSummary(
	ctx context.Context,
	conversationID string,
) (*SystemMessageSummary, error) {
	s.log.Infof("Getting system message summary for conversation: %s", conversationID)

	// 获取所有系统消息
	systemMessages, err := s.messageRepo.GetSystemMessages(ctx, conversationID)
	if err != nil {
		s.log.Errorf("Failed to get system messages: %v", err)
		return nil, err
	}

	summary := &SystemMessageSummary{
		ConversationID:     conversationID,
		SystemMessageCount: len(systemMessages),
		SystemInstructions: make([]string, 0),
	}

	if len(systemMessages) > 0 {
		summary.FirstSystemMessage = systemMessages[0]
		summary.LatestSystemMessage = systemMessages[len(systemMessages)-1]

		// 提取系统指令（content的前100个字符）
		for _, msg := range systemMessages {
			instruction := msg.Content
			if len(instruction) > 100 {
				instruction = instruction[:100] + "..."
			}
			summary.SystemInstructions = append(summary.SystemInstructions, instruction)
		}
	}

	s.log.Infof("System message summary: count=%d", summary.SystemMessageCount)
	return summary, nil
}

// FilterMessages 过滤消息
type FilterOptions struct {
	Role        *domain.MessageRole
	ContentType *domain.ContentType
	Model       string
	Provider    string
	MinTokens   int
	MaxTokens   int
	StartTime   *string // ISO 8601 format
	EndTime     *string // ISO 8601 format
}

// FilterMessages 根据条件过滤消息
func (s *SystemMessageService) FilterMessages(
	ctx context.Context,
	conversationID string,
	options *FilterOptions,
	limit, offset int,
) ([]*domain.Message, int, error) {
	s.log.Infof("Filtering messages for conversation: %s", conversationID)

	// 获取所有消息
	allMessages, total, err := s.messageRepo.ListMessages(ctx, conversationID, 10000, 0)
	if err != nil {
		return nil, 0, err
	}

	// 应用过滤器
	filtered := make([]*domain.Message, 0)
	for _, msg := range allMessages {
		if !s.matchesFilter(msg, options) {
			continue
		}
		filtered = append(filtered, msg)
	}

	// 分页
	start := offset
	end := offset + limit
	if start > len(filtered) {
		start = len(filtered)
	}
	if end > len(filtered) {
		end = len(filtered)
	}

	result := filtered[start:end]

	s.log.Infof("Filtered %d/%d messages", len(result), len(filtered))
	return result, len(filtered), nil
}

// matchesFilter 检查消息是否匹配过滤条件
func (s *SystemMessageService) matchesFilter(msg *domain.Message, options *FilterOptions) bool {
	if options.Role != nil && msg.Role != *options.Role {
		return false
	}

	if options.ContentType != nil && msg.ContentType != *options.ContentType {
		return false
	}

	if options.Model != "" && msg.Model != options.Model {
		return false
	}

	if options.Provider != "" && msg.Provider != options.Provider {
		return false
	}

	if options.MinTokens > 0 && msg.Tokens < options.MinTokens {
		return false
	}

	if options.MaxTokens > 0 && msg.Tokens > options.MaxTokens {
		return false
	}

	// 时间过滤（简化实现）
	// 实际应解析ISO 8601格式并比较

	return true
}

// ExportSystemMessages 导出系统消息（Markdown格式）
func (s *SystemMessageService) ExportSystemMessages(
	ctx context.Context,
	conversationID string,
) (string, error) {
	s.log.Infof("Exporting system messages for conversation: %s", conversationID)

	messages, err := s.messageRepo.GetSystemMessages(ctx, conversationID)
	if err != nil {
		return "", err
	}

	// 生成Markdown
	markdown := fmt.Sprintf("# System Messages - Conversation %s\n\n", conversationID)
	markdown += fmt.Sprintf("Total: %d messages\n\n", len(messages))
	markdown += "---\n\n"

	for i, msg := range messages {
		markdown += fmt.Sprintf("## Message %d\n\n", i+1)
		markdown += fmt.Sprintf("**ID**: %s\n\n", msg.ID)
		markdown += fmt.Sprintf("**Created At**: %s\n\n", msg.CreatedAt.Format("2006-01-02 15:04:05"))
		markdown += fmt.Sprintf("**Content**:\n\n```\n%s\n```\n\n", msg.Content)

		if msg.Model != "" {
			markdown += fmt.Sprintf("**Model**: %s (%s)\n\n", msg.Model, msg.Provider)
		}

		if len(msg.Metadata) > 0 {
			markdown += fmt.Sprintf("**Metadata**: %v\n\n", msg.Metadata)
		}

		markdown += "---\n\n"
	}

	s.log.Infof("Exported %d system messages to markdown", len(messages))
	return markdown, nil
}
