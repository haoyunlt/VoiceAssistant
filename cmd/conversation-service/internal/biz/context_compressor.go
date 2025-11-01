package biz

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/conversation-service/internal/domain"
	"voicehelper/cmd/conversation-service/internal/infra"
)

// ContextCompressor 上下文压缩器
type ContextCompressor struct {
	aiClient *infra.AIClient
	logger   *log.Helper
	config   *CompressorConfig
}

// CompressorConfig 压缩器配置
type CompressorConfig struct {
	EnableCompression    bool    // 是否启用压缩
	CompressThreshold    int     // 压缩阈值（消息数）
	KeepRecentCount      int     // 保留最近消息数
	SummaryModel         string  // 摘要模型
	SummaryTemperature   float32 // 摘要温度
	SummaryMaxTokens     int32   // 摘要最大 tokens
	CompressionRatio     float64 // 压缩比目标（0.0-1.0）
}

// NewContextCompressor 创建上下文压缩器
func NewContextCompressor(aiClient *infra.AIClient, config *CompressorConfig, logger log.Logger) *ContextCompressor {
	if config == nil {
		config = &CompressorConfig{
			EnableCompression:  true,
			CompressThreshold:  20,
			KeepRecentCount:    5,
			SummaryModel:       "gpt-3.5-turbo",
			SummaryTemperature: 0.3,
			SummaryMaxTokens:   500,
			CompressionRatio:   0.3,
		}
	}

	return &ContextCompressor{
		aiClient: aiClient,
		logger:   log.NewHelper(log.With(logger, "module", "context-compressor")),
		config:   config,
	}
}

// CompressContext 压缩上下文
func (c *ContextCompressor) CompressContext(
	ctx context.Context,
	conversationID string,
	messages []*domain.Message,
) (*domain.CompressedContext, error) {
	if !c.config.EnableCompression {
		c.logger.Debug("Compression disabled")
		return nil, fmt.Errorf("compression disabled")
	}

	if len(messages) < c.config.CompressThreshold {
		c.logger.Debugf("Message count (%d) below threshold (%d), skipping compression",
			len(messages), c.config.CompressThreshold)
		return nil, nil
	}

	c.logger.Infof("Starting context compression for conversation=%s, message_count=%d",
		conversationID, len(messages))

	// 1. 分离需要压缩的消息和保留的消息
	var toCompress []*domain.Message
	var toKeep []*domain.Message

	if len(messages) > c.config.KeepRecentCount {
		toCompress = messages[:len(messages)-c.config.KeepRecentCount]
		toKeep = messages[len(messages)-c.config.KeepRecentCount:]
	} else {
		toKeep = messages
	}

	if len(toCompress) == 0 {
		c.logger.Debug("No messages to compress")
		return nil, nil
	}

	// 2. 调用 LLM 生成摘要
	summary, err := c.generateSummary(ctx, toCompress)
	if err != nil {
		c.logger.Errorf("Failed to generate summary: %v", err)
		return nil, err
	}

	// 3. 构建压缩上下文
	compressed := &domain.CompressedContext{
		ConversationID:       conversationID,
		Summary:              summary,
		OriginalMessageCount: len(toCompress),
		CompressedAt:         time.Now(),
		KeptMessages:         toKeep,
		CompressionRatio:     c.calculateCompressionRatio(toCompress, summary),
	}

	c.logger.Infof("Context compressed: original=%d messages, kept=%d messages, ratio=%.2f",
		len(toCompress), len(toKeep), compressed.CompressionRatio)

	return compressed, nil
}

// generateSummary 生成对话摘要
func (c *ContextCompressor) generateSummary(ctx context.Context, messages []*domain.Message) (string, error) {
	// 构建提示词
	prompt := c.buildSummaryPrompt(messages)

	c.logger.Debugf("Generating summary with prompt length: %d", len(prompt))

	// 调用 AI 服务
	resp, err := c.aiClient.Generate(ctx, prompt, int(c.config.SummaryMaxTokens))
	if err != nil {
		return "", fmt.Errorf("failed to call AI service: %w", err)
	}

	summary := strings.TrimSpace(resp)

	if summary == "" {
		return "", fmt.Errorf("received empty summary from AI service")
	}

	return summary, nil
}

// buildSummaryPrompt 构建摘要提示词
func (c *ContextCompressor) buildSummaryPrompt(messages []*domain.Message) string {
	var sb strings.Builder

	// 系统提示
	sb.WriteString("请对以下对话进行简洁的摘要，保留关键信息和上下文：\n\n")

	// 对话历史
	sb.WriteString("## 对话历史\n\n")
	for i, msg := range messages {
		role := c.translateRole(msg.Role)
		content := msg.Content

		// 限制每条消息的长度
		if len(content) > 300 {
			content = content[:300] + "..."
		}

		sb.WriteString(fmt.Sprintf("%d. **%s**: %s\n", i+1, role, content))
	}

	// 摘要要求
	sb.WriteString("\n## 摘要要求\n\n")
	sb.WriteString("1. 提取对话的主要话题和关键信息\n")
	sb.WriteString("2. 保留用户的核心需求和问题\n")
	sb.WriteString("3. 记录助手提供的关键建议和答案\n")
	sb.WriteString("4. 使用简洁的语言，控制在 200 字以内\n")
	sb.WriteString("5. 使用第三人称叙述\n\n")
	sb.WriteString("请直接输出摘要，不要包含其他说明：")

	return sb.String()
}

// translateRole 翻译角色
func (c *ContextCompressor) translateRole(role domain.MessageRole) string {
	switch role {
	case "user":
		return "用户"
	case "assistant":
		return "助手"
	case "system":
		return "系统"
	default:
		return string(role)
	}
}

// calculateCompressionRatio 计算压缩比
func (c *ContextCompressor) calculateCompressionRatio(messages []*domain.Message, summary string) float64 {
	originalLength := 0
	for _, msg := range messages {
		originalLength += len(msg.Content)
	}

	if originalLength == 0 {
		return 0.0
	}

	compressedLength := len(summary)
	return float64(compressedLength) / float64(originalLength)
}

// GenerateConversationSummary 生成完整对话摘要（用于对话结束或归档）
func (c *ContextCompressor) GenerateConversationSummary(
	ctx context.Context,
	conversationID string,
	messages []*domain.Message,
) (*domain.ConversationSummary, error) {
	c.logger.Infof("Generating conversation summary for conversation=%s, message_count=%d",
		conversationID, len(messages))

	if len(messages) == 0 {
		return nil, fmt.Errorf("no messages to summarize")
	}

	// 构建详细摘要提示词
	prompt := c.buildDetailedSummaryPrompt(messages)

	// 调用 AI 服务
	resp, err := c.aiClient.Generate(ctx, prompt, 1000) // 允许更长的摘要
	if err != nil {
		return nil, fmt.Errorf("failed to generate summary: %w", err)
	}

	summary := strings.TrimSpace(resp)

	// 构建摘要对象
	conversationSummary := &domain.ConversationSummary{
		ConversationID: conversationID,
		Summary:        summary,
		MessageCount:   len(messages),
		GeneratedAt:    time.Now(),
		Topics:         c.extractTopics(summary),
		KeyPoints:      c.extractKeyPoints(summary),
	}

	c.logger.Infof("Conversation summary generated: %d characters, %d topics",
		len(summary), len(conversationSummary.Topics))

	return conversationSummary, nil
}

// buildDetailedSummaryPrompt 构建详细摘要提示词
func (c *ContextCompressor) buildDetailedSummaryPrompt(messages []*domain.Message) string {
	var sb strings.Builder

	sb.WriteString("请对以下完整对话进行详细的结构化摘要：\n\n")

	// 对话历史
	sb.WriteString("## 完整对话\n\n")
	for i, msg := range messages {
		role := c.translateRole(msg.Role)
		sb.WriteString(fmt.Sprintf("%d. **%s**: %s\n\n", i+1, role, msg.Content))
	}

	// 摘要要求
	sb.WriteString("\n## 摘要格式\n\n")
	sb.WriteString("请按以下结构输出摘要：\n\n")
	sb.WriteString("**主题**: [对话的核心主题]\n\n")
	sb.WriteString("**背景**: [对话发起的原因和背景]\n\n")
	sb.WriteString("**关键讨论点**:\n")
	sb.WriteString("1. [要点1]\n")
	sb.WriteString("2. [要点2]\n")
	sb.WriteString("3. [要点3]\n\n")
	sb.WriteString("**解决方案/建议**: [助手提供的主要建议或解决方案]\n\n")
	sb.WriteString("**结论**: [对话的最终结论或后续行动]\n\n")
	sb.WriteString("请直接输出摘要：")

	return sb.String()
}

// extractTopics 提取话题（简单实现）
func (c *ContextCompressor) extractTopics(summary string) []string {
	// TODO: 使用更智能的方法提取话题（NLP、关键词提取等）
	// 简单实现：查找"主题"标记
	topics := make([]string, 0)

	lines := strings.Split(summary, "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "**主题**:") {
			topic := strings.TrimPrefix(line, "**主题**:")
			topic = strings.TrimSpace(topic)
			if topic != "" {
				topics = append(topics, topic)
			}
		}
	}

	if len(topics) == 0 {
		topics = append(topics, "对话摘要")
	}

	return topics
}

// extractKeyPoints 提取关键点
func (c *ContextCompressor) extractKeyPoints(summary string) []string {
	keyPoints := make([]string, 0)

	lines := strings.Split(summary, "\n")
	inKeyPoints := false

	for _, line := range lines {
		line = strings.TrimSpace(line)

		if strings.Contains(line, "**关键讨论点**") || strings.Contains(line, "**关键点**") {
			inKeyPoints = true
			continue
		}

		if inKeyPoints {
			// 如果是列表项
			if strings.HasPrefix(line, "-") || strings.HasPrefix(line, "*") || (len(line) > 0 && line[0] >= '1' && line[0] <= '9') {
				// 清理列表标记
				point := strings.TrimLeft(line, "-*0123456789. ")
				if point != "" {
					keyPoints = append(keyPoints, point)
				}
			} else if strings.HasPrefix(line, "**") {
				// 遇到下一个标题，停止
				break
			}
		}
	}

	return keyPoints
}

// ShouldCompress 判断是否应该压缩
func (c *ContextCompressor) ShouldCompress(messageCount int) bool {
	return c.config.EnableCompression && messageCount >= c.config.CompressThreshold
}
