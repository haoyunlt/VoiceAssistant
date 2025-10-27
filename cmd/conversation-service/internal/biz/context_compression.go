package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"voiceassistant/cmd/conversation-service/internal/domain"
)

// CompressionStrategy 压缩策略
type CompressionStrategy string

const (
	StrategyLLMLingua  CompressionStrategy = "llmlingua"
	StrategyTokenPrune CompressionStrategy = "token_prune"
	StrategySummarize  CompressionStrategy = "summarize"
	StrategyHybrid     CompressionStrategy = "hybrid"
)

// CompressionConfig 压缩配置
type CompressionConfig struct {
	Strategy              CompressionStrategy
	TargetCompressionRatio float64
	MinRetainedTokens     int
	PreserveStructure     bool
	PreserveKeywords      []string
}

// CompressionStats 压缩统计
type CompressionStats struct {
	OriginalTokens   int
	CompressedTokens int
	CompressionRatio float64
	Strategy         string
	DurationMs       int64
}

// ContextCompressor 上下文压缩器
type ContextCompressor struct {
	aiClient *AIClient
	config   CompressionConfig
}

// NewContextCompressor 创建压缩器
func NewContextCompressor(aiClient *AIClient, config CompressionConfig) *ContextCompressor {
	return &ContextCompressor{
		aiClient: aiClient,
		config:   config,
	}
}

// Compress 压缩对话上下文
func (c *ContextCompressor) Compress(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, *CompressionStats, error) {
	startTime := time.Now()

	// 1. 计算当前Token数
	originalTokens := c.countTokens(messages)

	// 2. 判断是否需要压缩
	if originalTokens < c.config.MinRetainedTokens {
		return messages, &CompressionStats{
			OriginalTokens:   originalTokens,
			CompressedTokens: originalTokens,
			CompressionRatio: 1.0,
			Strategy:         string(c.config.Strategy),
			DurationMs:       time.Since(startTime).Milliseconds(),
		}, nil
	}

	// 3. 根据策略压缩
	var compressed []*domain.Message
	var err error

	switch c.config.Strategy {
	case StrategyLLMLingua:
		compressed, err = c.compressWithLLMLingua(ctx, messages)
	case StrategyTokenPrune:
		compressed, err = c.compressWithTokenPrune(ctx, messages)
	case StrategySummarize:
		compressed, err = c.compressWithSummarize(ctx, messages)
	case StrategyHybrid:
		compressed, err = c.compressWithHybrid(ctx, messages)
	default:
		return nil, nil, fmt.Errorf("unknown strategy: %s", c.config.Strategy)
	}

	if err != nil {
		return nil, nil, fmt.Errorf("compression failed: %w", err)
	}

	// 4. 计算压缩后Token数
	compressedTokens := c.countTokens(compressed)

	// 5. 生成统计信息
	stats := &CompressionStats{
		OriginalTokens:   originalTokens,
		CompressedTokens: compressedTokens,
		CompressionRatio: float64(compressedTokens) / float64(originalTokens),
		Strategy:         string(c.config.Strategy),
		DurationMs:       time.Since(startTime).Milliseconds(),
	}

	return compressed, stats, nil
}

// compressWithTokenPrune Token剪枝压缩
func (c *ContextCompressor) compressWithTokenPrune(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	targetTokens := int(float64(c.countTokens(messages)) * c.config.TargetCompressionRatio)

	// 保留最近的消息(优先级高)
	var compressed []*domain.Message
	currentTokens := 0

	for i := len(messages) - 1; i >= 0; i-- {
		msg := messages[i]
		tokens := c.countMessageTokens(msg)

		if currentTokens+tokens <= targetTokens {
			compressed = append([]*domain.Message{msg}, compressed...)
			currentTokens += tokens
		} else {
			break
		}
	}

	return compressed, nil
}

// compressWithSummarize 摘要压缩
func (c *ContextCompressor) compressWithSummarize(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	// 1. 将历史消息分段
	segments := c.segmentMessages(messages, 10)

	// 2. 对每段生成摘要
	var compressed []*domain.Message

	for _, segment := range segments {
		summary, err := c.summarizeSegment(ctx, segment)
		if err != nil {
			return nil, err
		}

		// 创建摘要消息
		summaryMsg := &domain.Message{
			Role:        "system",
			Content:     fmt.Sprintf("[历史摘要] %s", summary),
			ContentType: "text",
		}
		compressed = append(compressed, summaryMsg)
	}

	// 3. 保留最近几条原始消息
	recentCount := 5
	if len(messages) < recentCount {
		recentCount = len(messages)
	}
	compressed = append(compressed, messages[len(messages)-recentCount:]...)

	return compressed, nil
}

// compressWithHybrid 混合策略
func (c *ContextCompressor) compressWithHybrid(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	// 1. 对旧消息使用摘要
	midPoint := len(messages) / 2
	oldMessages := messages[:midPoint]
	summarized, err := c.compressWithSummarize(ctx, oldMessages)
	if err != nil {
		return nil, err
	}

	// 2. 对较新的消息使用Token剪枝
	recentMessages := messages[midPoint:]
	pruned, err := c.compressWithTokenPrune(ctx, recentMessages)
	if err != nil {
		return nil, err
	}

	// 3. 合并
	result := append(summarized, pruned...)
	return result, nil
}

// compressWithLLMLingua 使用LLMLingua压缩
func (c *ContextCompressor) compressWithLLMLingua(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	// 调用外部LLMLingua服务或API
	conversationText := c.messagesToText(messages)

	request := map[string]interface{}{
		"text":              conversationText,
		"compression_ratio": c.config.TargetCompressionRatio,
		"preserve_keywords": c.config.PreserveKeywords,
	}

	response, err := c.aiClient.CallLLMLingua(ctx, request)
	if err != nil {
		return nil, fmt.Errorf("llmlingua call failed: %w", err)
	}

	compressedText := response["compressed_text"].(string)

	// 转换回消息格式
	compressed := c.textToMessages(compressedText, messages)

	return compressed, nil
}

func (c *ContextCompressor) countTokens(messages []*domain.Message) int {
	total := 0
	for _, msg := range messages {
		total += c.countMessageTokens(msg)
	}
	return total
}

func (c *ContextCompressor) countMessageTokens(msg *domain.Message) int {
	// 简化的token计数，实际应使用tiktoken等
	return len([]rune(msg.Content)) / 4
}

func (c *ContextCompressor) messagesToText(messages []*domain.Message) string {
	result := ""
	for _, msg := range messages {
		result += fmt.Sprintf("%s: %s\n", msg.Role, msg.Content)
	}
	return result
}

func (c *ContextCompressor) textToMessages(text string, original []*domain.Message) []*domain.Message {
	// 简化实现：创建单个压缩消息
	return []*domain.Message{
		{
			Role:        "system",
			Content:     text,
			ContentType: "text",
		},
	}
}

func (c *ContextCompressor) segmentMessages(messages []*domain.Message, segmentSize int) [][]*domain.Message {
	var segments [][]*domain.Message
	for i := 0; i < len(messages); i += segmentSize {
		end := i + segmentSize
		if end > len(messages) {
			end = len(messages)
		}
		segments = append(segments, messages[i:end])
	}
	return segments
}

func (c *ContextCompressor) summarizeSegment(ctx context.Context, segment []*domain.Message) (string, error) {
	// 使用AI客户端生成摘要
	text := c.messagesToText(segment)

	prompt := fmt.Sprintf("Summarize this conversation segment concisely:\n\n%s\n\nSummary:", text)

	response, err := c.aiClient.Chat(ctx, []map[string]string{
		{"role": "user", "content": prompt},
	})
	if err != nil {
		return "", err
	}

	return response["content"].(string), nil
}

// AutoCompressor 自动压缩管理器
type AutoCompressor struct {
	compressor *ContextCompressor
	thresholds *CompressionThresholds
}

// CompressionThresholds 压缩阈值
type CompressionThresholds struct {
	TokenLimit     int
	MessageLimit   int
	TimeLimitHours int
}

// NewAutoCompressor 创建自动压缩器
func NewAutoCompressor(
	compressor *ContextCompressor,
	thresholds *CompressionThresholds,
) *AutoCompressor {
	return &AutoCompressor{
		compressor: compressor,
		thresholds: thresholds,
	}
}

// ShouldCompress 判断是否应该压缩
func (a *AutoCompressor) ShouldCompress(
	ctx context.Context,
	conversation *domain.Conversation,
) bool {
	// 1. 检查Token数
	if conversation.Context.CurrentTokens >= a.thresholds.TokenLimit {
		return true
	}

	// 2. 检查消息数
	if conversation.Context.CurrentMessages >= a.thresholds.MessageLimit {
		return true
	}

	// 3. 检查时间
	hours := time.Since(conversation.CreatedAt).Hours()
	if int(hours) >= a.thresholds.TimeLimitHours {
		return true
	}

	return false
}

// CompressIfNeeded 按需压缩
func (a *AutoCompressor) CompressIfNeeded(
	ctx context.Context,
	conversation *domain.Conversation,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	if !a.ShouldCompress(ctx, conversation) {
		return messages, nil
	}

	compressed, stats, err := a.compressor.Compress(ctx, messages)
	if err != nil {
		return nil, err
	}

	// 更新对话上下文统计
	conversation.Context.CurrentTokens = stats.CompressedTokens
	conversation.Context.CompressionCount++

	return compressed, nil
}
