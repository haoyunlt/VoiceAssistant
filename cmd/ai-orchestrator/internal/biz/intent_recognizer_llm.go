package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// LLMBasedRecognizer 基于LLM的意图识别器
type LLMBasedRecognizer struct {
	modelClient ModelClient
	cache       domain.IntentCache
	logger      *log.Helper
	timeout     time.Duration
}

// ModelClient LLM客户端接口
type ModelClient interface {
	// Call 调用LLM模型
	Call(ctx context.Context, messages []ModelMessage, options map[string]interface{}) (string, error)
}

// ModelMessage LLM消息
type ModelMessage struct {
	Role    string
	Content string
}

// NewLLMBasedRecognizer 创建基于LLM的识别器
func NewLLMBasedRecognizer(
	modelClient ModelClient,
	cache domain.IntentCache,
	logger log.Logger,
) *LLMBasedRecognizer {
	return &LLMBasedRecognizer{
		modelClient: modelClient,
		cache:       cache,
		logger:      log.NewHelper(logger),
		timeout:     5 * time.Second,
	}
}

// Recognize 识别意图
func (r *LLMBasedRecognizer) Recognize(input *domain.IntentInput) (*domain.Intent, error) {
	ctx, cancel := context.WithTimeout(context.Background(), r.timeout)
	defer cancel()

	// 1. 检查缓存
	if r.cache != nil {
		cacheKey := r.buildCacheKey(input)
		if cachedIntent, found := r.cache.Get(cacheKey); found {
			r.logger.Debugf("Intent found in cache: %s", cachedIntent.Type)
			cachedIntent.Metadata["from_cache"] = true
			return cachedIntent, nil
		}
	}

	// 2. 构建提示词
	prompt := r.buildPrompt(input)

	// 3. 调用LLM
	messages := []ModelMessage{
		{
			Role:    "system",
			Content: r.getSystemPrompt(),
		},
		{
			Role:    "user",
			Content: prompt,
		},
	}

	options := map[string]interface{}{
		"temperature":   0.1, // 低温度，保证结果稳定
		"max_tokens":    200,
		"response_format": "json_object",
	}

	startTime := time.Now()
	response, err := r.modelClient.Call(ctx, messages, options)
	if err != nil {
		r.logger.Errorf("LLM call failed: %v", err)
		// 降级到未知意图
		return domain.NewIntent(domain.IntentTypeUnknown, domain.ConfidenceVeryLow), nil
	}

	latency := time.Since(startTime)
	r.logger.Debugf("LLM intent recognition took %v", latency)

	// 4. 解析响应
	intent, err := r.parseResponse(response)
	if err != nil {
		r.logger.Errorf("Failed to parse LLM response: %v", err)
		return domain.NewIntent(domain.IntentTypeUnknown, domain.ConfidenceVeryLow), nil
	}

	intent.Metadata["recognizer"] = r.Name()
	intent.Metadata["latency_ms"] = latency.Milliseconds()

	// 5. 缓存结果（仅缓存高置信度结果）
	if r.cache != nil && intent.IsHighConfidence() {
		cacheKey := r.buildCacheKey(input)
		r.cache.Set(cacheKey, intent, 10*time.Minute)
	}

	r.logger.Infof("LLM Intent recognized: type=%s, confidence=%.2f", intent.Type, intent.Confidence)

	return intent, nil
}

// getSystemPrompt 获取系统提示词
func (r *LLMBasedRecognizer) getSystemPrompt() string {
	return `你是一个专业的意图识别系统。你的任务是分析用户输入，识别用户的意图类型。

可用的意图类型：
- chat: 普通闲聊对话
- rag: 知识检索问答（需要从知识库中检索信息）
- agent: 任务执行（需要调用工具或执行具体操作）
- voice: 语音处理
- multimodal: 多模态处理（图片、视频等）

请以JSON格式返回识别结果：
{
  "intent_type": "意图类型",
  "confidence": 0.95,
  "reason": "识别理由",
  "entities": {},
  "alternatives": [
    {"type": "备选意图", "confidence": 0.7, "reason": "理由"}
  ]
}

注意：
1. confidence 范围是 0.0-1.0
2. 如果不确定，可以提供多个备选意图
3. 理由要简洁明了`
}

// buildPrompt 构建提示词
func (r *LLMBasedRecognizer) buildPrompt(input *domain.IntentInput) string {
	var sb strings.Builder

	sb.WriteString(fmt.Sprintf("用户输入: %s\n\n", input.Message))

	// 添加对话历史（最近3条）
	if len(input.History) > 0 {
		sb.WriteString("对话历史:\n")
		start := len(input.History) - 3
		if start < 0 {
			start = 0
		}
		for i := start; i < len(input.History); i++ {
			msg := input.History[i]
			sb.WriteString(fmt.Sprintf("- %s: %s\n", msg.Role, msg.Content))
		}
		sb.WriteString("\n")
	}

	// 添加上下文信息
	if len(input.Context) > 0 {
		sb.WriteString("上下文信息:\n")
		if lang, ok := input.Context["language"]; ok {
			sb.WriteString(fmt.Sprintf("- 语言: %v\n", lang))
		}
		if domain, ok := input.Context["domain"]; ok {
			sb.WriteString(fmt.Sprintf("- 领域: %v\n", domain))
		}
	}

	// 添加参数信息
	if len(input.Params) > 0 {
		sb.WriteString("\n附加信息:\n")
		if _, hasAudio := input.Params["audio_url"]; hasAudio {
			sb.WriteString("- 包含音频输入\n")
		}
		if _, hasImage := input.Params["image_url"]; hasImage {
			sb.WriteString("- 包含图片输入\n")
		}
		if mode, ok := input.Params["mode"]; ok {
			sb.WriteString(fmt.Sprintf("- 指定模式: %v\n", mode))
		}
	}

	sb.WriteString("\n请识别用户意图并返回JSON格式结果。")

	return sb.String()
}

// parseResponse 解析LLM响应
func (r *LLMBasedRecognizer) parseResponse(response string) (*domain.Intent, error) {
	// 清理响应（移除可能的markdown代码块标记）
	response = strings.TrimSpace(response)
	response = strings.TrimPrefix(response, "```json")
	response = strings.TrimPrefix(response, "```")
	response = strings.TrimSuffix(response, "```")
	response = strings.TrimSpace(response)

	// 解析JSON
	var result struct {
		IntentType   string                 `json:"intent_type"`
		Confidence   float64                `json:"confidence"`
		Reason       string                 `json:"reason"`
		Entities     map[string]interface{} `json:"entities"`
		Alternatives []struct {
			Type       string  `json:"type"`
			Confidence float64 `json:"confidence"`
			Reason     string  `json:"reason"`
		} `json:"alternatives"`
	}

	if err := json.Unmarshal([]byte(response), &result); err != nil {
		return nil, fmt.Errorf("parse json: %w", err)
	}

	// 验证意图类型
	intentType := r.parseIntentType(result.IntentType)
	if intentType == domain.IntentTypeUnknown && result.IntentType != "unknown" {
		r.logger.Warnf("Unknown intent type from LLM: %s", result.IntentType)
	}

	// 创建意图对象
	intent := domain.NewIntent(intentType, domain.IntentConfidence(result.Confidence))
	intent.Reason = result.Reason

	// 设置实体
	if result.Entities != nil {
		intent.Entities = result.Entities
	}

	// 添加备选意图
	for _, alt := range result.Alternatives {
		altType := r.parseIntentType(alt.Type)
		intent.AddAlternative(altType, domain.IntentConfidence(alt.Confidence), alt.Reason)
	}

	return intent, nil
}

// parseIntentType 解析意图类型
func (r *LLMBasedRecognizer) parseIntentType(typeStr string) domain.IntentType {
	typeStr = strings.ToLower(strings.TrimSpace(typeStr))

	switch typeStr {
	case "chat":
		return domain.IntentTypeChat
	case "rag", "knowledge", "retrieval":
		return domain.IntentTypeRAG
	case "agent", "task", "tool":
		return domain.IntentTypeAgent
	case "voice", "audio", "speech":
		return domain.IntentTypeVoice
	case "multimodal", "image", "video":
		return domain.IntentTypeMultimodal
	default:
		return domain.IntentTypeUnknown
	}
}

// buildCacheKey 构建缓存键
func (r *LLMBasedRecognizer) buildCacheKey(input *domain.IntentInput) string {
	// 使用消息内容 + 租户ID作为缓存键
	// 实际应用中可以使用更复杂的键生成策略
	return fmt.Sprintf("intent:llm:%s:%s", input.TenantID, hashString(input.Message))
}

// hashString 简单哈希函数
func hashString(s string) string {
	// 实际应用中应该使用更好的哈希算法（如MD5、SHA256）
	h := 0
	for _, c := range s {
		h = h*31 + int(c)
	}
	return fmt.Sprintf("%x", h)
}

// Name 识别器名称
func (r *LLMBasedRecognizer) Name() string {
	return "llm_based"
}

// Priority 优先级
func (r *LLMBasedRecognizer) Priority() int {
	return 2 // LLM识别器优先级略低于规则
}
