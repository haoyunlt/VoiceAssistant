package application

import (
	"context"
	"fmt"
	"voicehelper/cmd/ai-orchestrator/internal/biz"
	"voicehelper/cmd/ai-orchestrator/internal/domain"
)

// IntentRecognitionHandler 意图识别处理器
type IntentRecognitionHandler struct {
	BaseChatHandler
	intentService *biz.IntentService
}

// NewIntentRecognitionHandler 创建意图识别处理器
func NewIntentRecognitionHandler(intentService *biz.IntentService) *IntentRecognitionHandler {
	return &IntentRecognitionHandler{
		intentService: intentService,
	}
}

// Handle 处理请求
func (h *IntentRecognitionHandler) Handle(ctx context.Context, req *ChatRequest, stream *ChatStream) error {
	// 1. 如果已经明确指定了模式，跳过意图识别
	if req.Mode != "" && req.Mode != "auto" {
		fmt.Printf("[INTENT] Using explicit mode: %s\n", req.Mode)

		// 传递给下一个处理器
		if h.next != nil {
			return h.next.Handle(ctx, req, stream)
		}
		return nil
	}

	// 2. 构建意图识别输入
	intentInput := &domain.IntentInput{
		Message:        req.Message,
		ConversationID: req.ConversationID,
		UserID:         req.UserID,
		TenantID:       req.TenantID,
		Context:        make(map[string]interface{}),
		Params:         req.Params,
	}

	// 添加上下文信息
	if req.Context != nil {
		intentInput.Context["model_id"] = req.Context.ModelID
		intentInput.Context["model_provider"] = req.Context.ModelProvider
		if req.Context.Metadata != nil {
			for k, v := range req.Context.Metadata {
				intentInput.Context[k] = v
			}
		}
	}

	// 添加对话历史
	if req.Params != nil {
		if history, ok := req.Params["history"].([]interface{}); ok {
			messages := make([]domain.Message, 0, len(history))
			for _, h := range history {
				if msg, ok := h.(map[string]interface{}); ok {
					role, _ := msg["role"].(string)
					content, _ := msg["content"].(string)
					messages = append(messages, domain.Message{
						Role:    role,
						Content: content,
					})
				}
			}
			intentInput.History = messages
		}
	}

	// 3. 识别意图
	stream.SendSafe(&ChatResponse{
		TaskID:  req.TaskID,
		Type:    "intent_recognizing",
		Content: "Recognizing intent...",
	})

	intent, err := h.intentService.RecognizeIntent(ctx, intentInput)
	if err != nil {
		return fmt.Errorf("intent recognition failed: %w", err)
	}

	// 4. 发送意图识别结果
	stream.SendSafe(&ChatResponse{
		TaskID:  req.TaskID,
		Type:    "intent_recognized",
		Content: fmt.Sprintf("Intent: %s (confidence: %.2f)", intent.Type, intent.Confidence),
		Metadata: map[string]interface{}{
			"intent_type":       string(intent.Type),
			"confidence":        intent.Confidence,
			"reason":            intent.Reason,
			"entities":          intent.Entities,
			"alternative_intents": intent.AlternativeIntents,
		},
	})

	// 5. 根据意图设置请求模式
	req.Mode = mapIntentToMode(intent.Type)

	// 将意图信息添加到上下文
	if req.Context == nil {
		req.Context = &RequestContext{
			Metadata: make(map[string]interface{}),
		}
	}
	if req.Context.Metadata == nil {
		req.Context.Metadata = make(map[string]interface{})
	}
	req.Context.Metadata["intent"] = intent
	req.Context.Metadata["intent_type"] = string(intent.Type)
	req.Context.Metadata["intent_confidence"] = intent.Confidence

	fmt.Printf("[INTENT] Recognized intent: type=%s, confidence=%.2f, mode=%s\n",
		intent.Type, intent.Confidence, req.Mode)

	// 6. 处理低置信度情况
	if intent.IsLowConfidence() {
		stream.SendSafe(&ChatResponse{
			TaskID:  req.TaskID,
			Type:    "warning",
			Content: "Intent confidence is low, results may not be optimal",
			Metadata: map[string]interface{}{
				"confidence": intent.Confidence,
			},
		})
	}

	// 7. 传递给下一个处理器
	if h.next != nil {
		return h.next.Handle(ctx, req, stream)
	}

	return nil
}

// mapIntentToMode 将意图类型映射到执行模式
func mapIntentToMode(intentType domain.IntentType) string {
	switch intentType {
	case domain.IntentTypeChat:
		return "direct"
	case domain.IntentTypeRAG:
		return "rag"
	case domain.IntentTypeAgent:
		return "agent"
	case domain.IntentTypeVoice:
		return "voice"
	case domain.IntentTypeMultimodal:
		return "multimodal"
	default:
		return "direct" // 默认使用直接对话
	}
}

// BuildChatPipelineWithIntent 构建带意图识别的聊天处理管道
func BuildChatPipelineWithIntent(
	intentService *biz.IntentService,
	executionHandler ChatHandler,
) ChatHandler {
	// 构建责任链：Logging -> Validation -> Intent -> Metrics -> Execution
	loggingHandler := NewLoggingHandler()
	validationHandler := NewValidationHandler()
	intentHandler := NewIntentRecognitionHandler(intentService)
	metricsHandler := NewMetricsHandler()

	// 链接处理器
	loggingHandler.SetNext(validationHandler)
	validationHandler.SetNext(intentHandler)
	intentHandler.SetNext(metricsHandler)
	metricsHandler.SetNext(executionHandler)

	// 返回头部处理器
	return loggingHandler
}
