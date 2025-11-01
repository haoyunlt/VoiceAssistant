package biz

import (
	"context"
	"fmt"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// IntentService 意图识别服务
type IntentService struct {
	recognizers   []domain.IntentRecognizer
	cache         domain.IntentCache
	mlRecognizer  *MLIntentRecognizer // ML识别器（可选）
	logger        *log.Helper

	// 策略配置
	useCache      bool
	useFallback   bool
	minConfidence domain.IntentConfidence
}

// IntentServiceConfig 意图服务配置
type IntentServiceConfig struct {
	UseCache      bool
	UseFallback   bool
	MinConfidence domain.IntentConfidence
}

// NewIntentService 创建意图识别服务
func NewIntentService(
	recognizers []domain.IntentRecognizer,
	cache domain.IntentCache,
	config *IntentServiceConfig,
	logger log.Logger,
) *IntentService {
	if config == nil {
		config = &IntentServiceConfig{
			UseCache:      true,
			UseFallback:   true,
			MinConfidence: domain.ConfidenceMedium,
		}
	}

	return &IntentService{
		recognizers:   recognizers,
		cache:         cache,
		useCache:      config.UseCache,
		useFallback:   config.UseFallback,
		minConfidence: config.MinConfidence,
		logger:        log.NewHelper(logger),
	}
}

// RecognizeIntent 识别意图（主入口）
func (s *IntentService) RecognizeIntent(ctx context.Context, input *domain.IntentInput) (*domain.Intent, error) {
	s.logger.Debugf("Recognizing intent for message: %s", input.Message)

	// 1. 检查是否手动指定模式
	if mode, ok := input.Params["mode"].(string); ok && mode != "" {
		return s.handleManualMode(mode, input)
	}

	// 2. 尝试使用缓存
	if s.useCache && s.cache != nil {
		cacheKey := s.buildCacheKey(input)
		if intent, found := s.cache.Get(cacheKey); found {
			s.logger.Debugf("Intent retrieved from cache: %s", intent.Type)
			return intent, nil
		}
	}

	// 3. 依次尝试各个识别器
	var bestIntent *domain.Intent
	var err error

	for _, recognizer := range s.recognizers {
		s.logger.Debugf("Trying recognizer: %s", recognizer.Name())

		intent, recognizeErr := recognizer.Recognize(input)
		if recognizeErr != nil {
			s.logger.Warnf("Recognizer %s failed: %v", recognizer.Name(), recognizeErr)
			err = recognizeErr
			continue
		}

		// 选择置信度最高的识别结果
		if bestIntent == nil || intent.Confidence > bestIntent.Confidence {
			bestIntent = intent
		}

		// 如果已经达到高置信度，直接返回
		if intent.IsHighConfidence() {
			s.logger.Infof("High confidence intent found: %s (%.2f)", intent.Type, intent.Confidence)
			break
		}
	}

	// 4. 检查识别结果
	if bestIntent == nil {
		s.logger.Errorf("All recognizers failed")
		return nil, fmt.Errorf("intent recognition failed: %w", err)
	}

	// 5. 置信度检查
	if bestIntent.Confidence < s.minConfidence {
		s.logger.Warnf("Intent confidence too low: %.2f < %.2f", bestIntent.Confidence, s.minConfidence)

		if s.useFallback {
			// 降级到普通对话
			bestIntent = domain.NewIntent(domain.IntentTypeChat, domain.ConfidenceMedium)
			bestIntent.Reason = "fallback_due_to_low_confidence"
			bestIntent.Metadata["original_intent"] = bestIntent.Type
			bestIntent.Metadata["original_confidence"] = bestIntent.Confidence
		}
	}

	// 6. 缓存结果
	if s.useCache && s.cache != nil && bestIntent.IsHighConfidence() {
		cacheKey := s.buildCacheKey(input)
		s.cache.Set(cacheKey, bestIntent, 0) // TTL由具体缓存实现决定
	}

	s.logger.Infof("Final intent: type=%s, confidence=%.2f, reason=%s",
		bestIntent.Type, bestIntent.Confidence, bestIntent.Reason)

	return bestIntent, nil
}

// handleManualMode 处理手动指定的模式
func (s *IntentService) handleManualMode(mode string, input *domain.IntentInput) (*domain.Intent, error) {
	var intentType domain.IntentType

	switch mode {
	case "direct", "chat":
		intentType = domain.IntentTypeChat
	case "rag", "knowledge":
		intentType = domain.IntentTypeRAG
	case "agent", "tool":
		intentType = domain.IntentTypeAgent
	case "voice", "audio":
		intentType = domain.IntentTypeVoice
	case "multimodal", "image":
		intentType = domain.IntentTypeMultimodal
	default:
		s.logger.Warnf("Unknown manual mode: %s", mode)
		intentType = domain.IntentTypeUnknown
	}

	intent := domain.NewIntent(intentType, domain.ConfidenceVeryHigh)
	intent.Reason = "manual_mode"
	intent.Metadata["manual_mode"] = mode

	s.logger.Infof("Using manual mode: %s -> %s", mode, intentType)

	return intent, nil
}

// buildCacheKey 构建缓存键
func (s *IntentService) buildCacheKey(input *domain.IntentInput) string {
	// 简化的缓存键生成
	return fmt.Sprintf("intent:%s:%s", input.TenantID, hashString(input.Message))
}

// RecognizeBatch 批量识别意图
func (s *IntentService) RecognizeBatch(ctx context.Context, inputs []*domain.IntentInput) ([]*domain.Intent, error) {
	results := make([]*domain.Intent, len(inputs))
	errors := make([]error, len(inputs))

	// 并发识别
	type result struct {
		index  int
		intent *domain.Intent
		err    error
	}

	resultChan := make(chan result, len(inputs))

	for i, input := range inputs {
		go func(idx int, inp *domain.IntentInput) {
			intent, err := s.RecognizeIntent(ctx, inp)
			resultChan <- result{
				index:  idx,
				intent: intent,
				err:    err,
			}
		}(i, input)
	}

	// 收集结果
	for i := 0; i < len(inputs); i++ {
		res := <-resultChan
		results[res.index] = res.intent
		errors[res.index] = res.err
	}

	// 检查是否有错误
	for _, err := range errors {
		if err != nil {
			return results, fmt.Errorf("batch recognition had errors")
		}
	}

	return results, nil
}

// GetCacheStats 获取缓存统计（如果使用内存缓存）
func (s *IntentService) GetCacheStats() *CacheStats {
	if memCache, ok := s.cache.(*MemoryIntentCache); ok {
		stats := memCache.GetStats()
		return &stats
	}
	return nil
}
