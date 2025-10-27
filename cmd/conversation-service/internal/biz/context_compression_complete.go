package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// ContextCompressor 上下文压缩器接口
type ContextCompressor interface {
	Compress(ctx context.Context, messages []Message, targetLength int) ([]Message, error)
}

// TruncationCompressor 截断压缩器
type TruncationCompressor struct {
	strategy string // "keep_recent", "keep_first_last", "sliding_window"
}

func NewTruncationCompressor(strategy string) *TruncationCompressor {
	return &TruncationCompressor{
		strategy: strategy,
	}
}

func (c *TruncationCompressor) Compress(ctx context.Context, messages []Message, targetLength int) ([]Message, error) {
	if len(messages) <= targetLength {
		return messages, nil
	}

	switch c.strategy {
	case "keep_recent":
		// 保留最近的消息
		return messages[len(messages)-targetLength:], nil

	case "keep_first_last":
		// 保留首尾消息
		halfTarget := targetLength / 2
		firstPart := messages[:halfTarget]
		lastPart := messages[len(messages)-halfTarget:]

		result := make([]Message, 0, targetLength)
		result = append(result, firstPart...)

		// 添加省略标记
		result = append(result, Message{
			Role:    "system",
			Content: fmt.Sprintf("[省略了 %d 条消息]", len(messages)-targetLength),
		})

		result = append(result, lastPart...)
		return result, nil

	case "sliding_window":
		// 滑动窗口：保留最近的 targetLength 条消息
		return messages[len(messages)-targetLength:], nil

	default:
		return messages[len(messages)-targetLength:], nil
	}
}

// SummaryCompressor 摘要压缩器
type SummaryCompressor struct {
	llmServiceURL string
	httpClient    *http.Client
}

func NewSummaryCompressor(llmServiceURL string) *SummaryCompressor {
	return &SummaryCompressor{
		llmServiceURL: llmServiceURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *SummaryCompressor) Compress(ctx context.Context, messages []Message, targetLength int) ([]Message, error) {
	if len(messages) <= targetLength {
		return messages, nil
	}

	// 将需要压缩的消息分组
	toCompress := messages[:len(messages)-targetLength]
	toKeep := messages[len(messages)-targetLength:]

	// 生成摘要
	summary, err := c.generateSummary(ctx, toCompress)
	if err != nil {
		// 降级：使用截断策略
		return toKeep, nil
	}

	// 创建摘要消息
	summaryMsg := Message{
		Role:    "system",
		Content: fmt.Sprintf("对话摘要：%s", summary),
	}

	// 合并结果
	result := make([]Message, 0, targetLength+1)
	result = append(result, summaryMsg)
	result = append(result, toKeep...)

	return result, nil
}

func (c *SummaryCompressor) generateSummary(ctx context.Context, messages []Message) (string, error) {
	// 构建对话历史文本
	var builder strings.Builder
	for _, msg := range messages {
		builder.WriteString(fmt.Sprintf("%s: %s\n", msg.Role, msg.Content))
	}

	// 调用 LLM 生成摘要
	prompt := fmt.Sprintf(`请简要总结以下对话的关键信息和上下文：

%s

请用简洁的语言总结对话的主要内容、关键信息和当前状态。`, builder.String())

	reqBody := map[string]interface{}{
		"model": "gpt-3.5-turbo",
		"messages": []map[string]string{
			{
				"role":    "system",
				"content": "你是一个对话摘要助手，擅长提取对话中的关键信息。",
			},
			{
				"role":    "user",
				"content": prompt,
			},
		},
		"temperature": 0.3,
		"max_tokens":  500,
	}

	reqJSON, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.llmServiceURL+"/api/v1/chat/completions", strings.NewReader(string(reqJSON)))
	if err != nil {
		return "", fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("call LLM: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("LLM returned status %d: %s", resp.StatusCode, string(body))
	}

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("decode response: %w", err)
	}

	if len(result.Choices) == 0 {
		return "", fmt.Errorf("no response from LLM")
	}

	return result.Choices[0].Message.Content, nil
}

// SemanticCompressor 语义压缩器
type SemanticCompressor struct {
	llmServiceURL string
	httpClient    *http.Client
}

func NewSemanticCompressor(llmServiceURL string) *SemanticCompressor {
	return &SemanticCompressor{
		llmServiceURL: llmServiceURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *SemanticCompressor) Compress(ctx context.Context, messages []Message, targetLength int) ([]Message, error) {
	if len(messages) <= targetLength {
		return messages, nil
	}

	// 计算每条消息的重要性分数
	scores, err := c.calculateImportanceScores(ctx, messages)
	if err != nil {
		// 降级：使用截断策略
		truncator := NewTruncationCompressor("keep_recent")
		return truncator.Compress(ctx, messages, targetLength)
	}

	// 按重要性排序并选择 top-k
	type scoredMessage struct {
		message Message
		score   float64
		index   int
	}

	scored := make([]scoredMessage, len(messages))
	for i, msg := range messages {
		scored[i] = scoredMessage{
			message: msg,
			score:   scores[i],
			index:   i,
		}
	}

	// 排序（按分数降序）
	// 这里简化处理，实际应使用 sort 包
	selected := make([]scoredMessage, 0, targetLength)
	for i := 0; i < len(scored) && len(selected) < targetLength; i++ {
		maxIdx := i
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[maxIdx].score {
				maxIdx = j
			}
		}
		// 交换
		scored[i], scored[maxIdx] = scored[maxIdx], scored[i]
		selected = append(selected, scored[i])
	}

	// 按原始顺序排序
	for i := 0; i < len(selected); i++ {
		for j := i + 1; j < len(selected); j++ {
			if selected[j].index < selected[i].index {
				selected[i], selected[j] = selected[j], selected[i]
			}
		}
	}

	// 提取消息
	result := make([]Message, len(selected))
	for i, sm := range selected {
		result[i] = sm.message
	}

	return result, nil
}

func (c *SemanticCompressor) calculateImportanceScores(ctx context.Context, messages []Message) ([]float64, error) {
	// 构建评分请求
	var builder strings.Builder
	for i, msg := range messages {
		builder.WriteString(fmt.Sprintf("[%d] %s: %s\n", i, msg.Role, msg.Content))
	}

	prompt := fmt.Sprintf(`请为以下对话中的每条消息评分（0-1），分数越高表示消息越重要。
评分标准：
1. 包含关键信息的消息得分高
2. 与当前话题直接相关的消息得分高
3. 简单的礼貌用语得分低

对话：
%s

请返回 JSON 格式的分数列表，例如：
[0.8, 0.3, 0.9, 0.5]`, builder.String())

	reqBody := map[string]interface{}{
		"model": "gpt-3.5-turbo",
		"messages": []map[string]string{
			{
				"role":    "user",
				"content": prompt,
			},
		},
		"temperature": 0.1,
	}

	reqJSON, err := json.Marshal(reqBody)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.llmServiceURL+"/api/v1/chat/completions", strings.NewReader(string(reqJSON)))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("LLM returned status %d", resp.StatusCode)
	}

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	if len(result.Choices) == 0 {
		return nil, fmt.Errorf("no response from LLM")
	}

	// 解析分数
	content := result.Choices[0].Message.Content
	// 简化处理：提取 JSON 数组
	content = strings.TrimSpace(content)
	if strings.HasPrefix(content, "```json") {
		content = strings.TrimPrefix(content, "```json")
	}
	if strings.HasPrefix(content, "```") {
		content = strings.TrimPrefix(content, "```")
	}
	if strings.HasSuffix(content, "```") {
		content = strings.TrimSuffix(content, "```")
	}
	content = strings.TrimSpace(content)

	var scores []float64
	if err := json.Unmarshal([]byte(content), &scores); err != nil {
		return nil, fmt.Errorf("parse scores: %w", err)
	}

	if len(scores) != len(messages) {
		return nil, fmt.Errorf("scores length mismatch: got %d, expected %d", len(scores), len(messages))
	}

	return scores, nil
}

// ContextCompressionService 上下文压缩服务
type ContextCompressionService struct {
	compressors map[string]ContextCompressor
}

func NewContextCompressionService(llmServiceURL string) *ContextCompressionService {
	return &ContextCompressionService{
		compressors: map[string]ContextCompressor{
			"truncation": NewTruncationCompressor("keep_recent"),
			"summary":    NewSummaryCompressor(llmServiceURL),
			"semantic":   NewSemanticCompressor(llmServiceURL),
		},
	}
}

func (s *ContextCompressionService) Compress(ctx context.Context, messages []Message, strategy string, targetLength int) ([]Message, error) {
	compressor, ok := s.compressors[strategy]
	if !ok {
		return nil, fmt.Errorf("unknown compression strategy: %s", strategy)
	}

	return compressor.Compress(ctx, messages, targetLength)
}
