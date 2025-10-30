package biz

import (
	"regexp"
	"strings"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// RuleBasedRecognizer 基于规则的意图识别器
type RuleBasedRecognizer struct {
	rules  []*IntentRule
	logger *log.Helper
}

// IntentRule 意图识别规则
type IntentRule struct {
	Name        string               // 规则名称
	IntentType  domain.IntentType    // 目标意图
	Confidence  domain.IntentConfidence // 匹配时的置信度
	Keywords    []string             // 关键词列表
	Patterns    []*regexp.Regexp     // 正则模式
	Priority    int                  // 优先级（越小越优先）
	Validator   func(*domain.IntentInput) bool // 额外验证函数
}

// NewRuleBasedRecognizer 创建基于规则的识别器
func NewRuleBasedRecognizer(logger log.Logger) *RuleBasedRecognizer {
	r := &RuleBasedRecognizer{
		rules:  make([]*IntentRule, 0),
		logger: log.NewHelper(logger),
	}

	// 初始化默认规则
	r.initDefaultRules()

	return r
}

// initDefaultRules 初始化默认规则
func (r *RuleBasedRecognizer) initDefaultRules() {
	// RAG 知识检索规则
	r.AddRule(&IntentRule{
		Name:       "knowledge_query",
		IntentType: domain.IntentTypeRAG,
		Confidence: domain.ConfidenceHigh,
		Keywords: []string{
			"什么是", "怎么", "如何", "为什么", "哪里",
			"告诉我", "查询", "查找", "搜索", "检索",
			"帮我找", "查一下", "资料", "文档",
			"知识库", "相关文档", "有关",
		},
		Patterns: []*regexp.Regexp{
			regexp.MustCompile(`(?i)(what|how|why|where|when)\s+(is|are|do|does)`),
			regexp.MustCompile(`(?i)(tell me|show me|find|search|look up)`),
			regexp.MustCompile(`(?i)(查询|查找|搜索|检索|告诉我)`),
		},
		Priority: 10,
	})

	// Agent 任务执行规则
	r.AddRule(&IntentRule{
		Name:       "task_execution",
		IntentType: domain.IntentTypeAgent,
		Confidence: domain.ConfidenceHigh,
		Keywords: []string{
			"帮我", "请", "执行", "运行", "计算",
			"创建", "生成", "发送", "提交",
			"订单", "预订", "购买", "支付",
			"分析", "统计", "汇总", "报表",
			"工具", "调用", "API",
		},
		Patterns: []*regexp.Regexp{
			regexp.MustCompile(`(?i)(help me|please|execute|run|calculate)`),
			regexp.MustCompile(`(?i)(create|generate|send|submit)`),
			regexp.MustCompile(`(?i)(帮我|请|执行|运行|计算)`),
			regexp.MustCompile(`(?i)(创建|生成|发送|提交|购买|支付)`),
		},
		Priority: 20,
	})

	// 语音处理规则（必须有audio参数才匹配）
	r.AddRule(&IntentRule{
		Name:       "voice_processing",
		IntentType: domain.IntentTypeVoice,
		Confidence: domain.ConfidenceVeryHigh,
		Keywords: []string{
			"语音", "音频", "录音", "播放",
			"转文字", "语音识别", "TTS", "朗读",
		},
		Patterns: []*regexp.Regexp{
			regexp.MustCompile(`(?i)(voice|audio|speech|sound)`),
			regexp.MustCompile(`(?i)(语音|音频|录音|播放)`),
		},
		Priority: 15, // 降低优先级
		Validator: func(input *domain.IntentInput) bool {
			// 必须有语音相关参数
			if input.Params != nil {
				if _, ok := input.Params["audio_url"]; ok {
					return true
				}
				if _, ok := input.Params["voice_mode"]; ok {
					return true
				}
			}
			// 没有音频参数时不匹配
			return false
		},
	})

	// 多模态处理规则（必须有image/file参数才匹配）
	r.AddRule(&IntentRule{
		Name:       "multimodal_processing",
		IntentType: domain.IntentTypeMultimodal,
		Confidence: domain.ConfidenceHigh,
		Keywords: []string{
			"图片", "图像", "照片", "截图",
			"视频", "文件", "附件",
			"看看这个", "分析图片", "识别",
		},
		Patterns: []*regexp.Regexp{
			regexp.MustCompile(`(?i)(image|picture|photo|video|file)`),
			regexp.MustCompile(`(?i)(图片|图像|照片|视频|文件)`),
		},
		Priority: 15, // 降低优先级
		Validator: func(input *domain.IntentInput) bool {
			// 必须有多模态输入参数
			if input.Params != nil {
				if _, ok := input.Params["image_url"]; ok {
					return true
				}
				if _, ok := input.Params["file_url"]; ok {
					return true
				}
			}
			// 没有多模态参数时不匹配
			return false
		},
	})

	// 普通对话规则（默认兜底）
	r.AddRule(&IntentRule{
		Name:       "general_chat",
		IntentType: domain.IntentTypeChat,
		Confidence: domain.ConfidenceMedium,
		Keywords: []string{
			"你好", "谢谢", "再见", "对话", "聊天",
			"hello", "hi", "thanks", "bye",
		},
		Priority: 100, // 最低优先级
	})
}

// AddRule 添加规则
func (r *RuleBasedRecognizer) AddRule(rule *IntentRule) {
	r.rules = append(r.rules, rule)
}

// ruleMatch 规则匹配结果
type ruleMatch struct {
	rule  *IntentRule
	score float64
}

// Recognize 识别意图
func (r *RuleBasedRecognizer) Recognize(input *domain.IntentInput) (*domain.Intent, error) {
	message := strings.ToLower(strings.TrimSpace(input.Message))

	if message == "" {
		return domain.NewIntent(domain.IntentTypeUnknown, domain.ConfidenceVeryLow), nil
	}

	// 收集所有匹配的规则及其得分
	matches := make([]*ruleMatch, 0)

	// 遍历所有规则
	for _, rule := range r.rules {
		score := r.calculateRuleScore(message, input, rule)

		if score > 0 {
			matches = append(matches, &ruleMatch{
				rule:  rule,
				score: score,
			})
		}
	}

	// 如果没有匹配，返回未知意图
	if len(matches) == 0 {
		r.logger.Debugf("No rule matched for message: %s", input.Message)
		return domain.NewIntent(domain.IntentTypeUnknown, domain.ConfidenceVeryLow), nil
	}

	// 按优先级和得分排序
	sortMatches(matches)

	// 选择最佳匹配
	best := matches[0]
	intent := domain.NewIntent(best.rule.IntentType, best.rule.Confidence)
	intent.Reason = best.rule.Name
	intent.Metadata["rule_score"] = best.score
	intent.Metadata["recognizer"] = r.Name()

	// 添加备选意图
	for i := 1; i < len(matches) && i < 3; i++ {
		match := matches[i]
		intent.AddAlternative(
			match.rule.IntentType,
			match.rule.Confidence,
			match.rule.Name,
		)
	}

	r.logger.Infof("Intent recognized: type=%s, confidence=%.2f, rule=%s",
		intent.Type, intent.Confidence, best.rule.Name)

	return intent, nil
}

// calculateRuleScore 计算规则得分
func (r *RuleBasedRecognizer) calculateRuleScore(message string, input *domain.IntentInput, rule *IntentRule) float64 {
	// 0. 如果有Validator且不通过，直接返回0
	if rule.Validator != nil && !rule.Validator(input) {
		return 0
	}

	score := 0.0

	// 1. 关键词匹配（每个关键词 +0.2）
	keywordMatches := 0
	for _, keyword := range rule.Keywords {
		if strings.Contains(message, strings.ToLower(keyword)) {
			keywordMatches++
		}
	}
	if keywordMatches > 0 {
		score += float64(keywordMatches) * 0.2
	}

	// 2. 正则模式匹配（每个模式 +0.3）
	patternMatches := 0
	for _, pattern := range rule.Patterns {
		if pattern.MatchString(message) {
			patternMatches++
		}
	}
	if patternMatches > 0 {
		score += float64(patternMatches) * 0.3
	}

	// 3. Validator通过加分（+0.5）
	if rule.Validator != nil {
		score += 0.5
	}

	// 4. 优先级调整（优先级越高，基础分越高）
	priorityBonus := 1.0 / float64(rule.Priority+1)
	score += priorityBonus

	return score
}

// sortMatches 对匹配结果排序
func sortMatches(matches []*ruleMatch) {
	// 简单的冒泡排序（实际应用中可以用更高效的排序算法）
	for i := 0; i < len(matches); i++ {
		for j := i + 1; j < len(matches); j++ {
			// 先按优先级，再按得分
			if matches[i].rule.Priority > matches[j].rule.Priority ||
				(matches[i].rule.Priority == matches[j].rule.Priority && matches[i].score < matches[j].score) {
				matches[i], matches[j] = matches[j], matches[i]
			}
		}
	}
}

// Name 识别器名称
func (r *RuleBasedRecognizer) Name() string {
	return "rule_based"
}

// Priority 优先级
func (r *RuleBasedRecognizer) Priority() int {
	return 1 // 规则识别器优先级较高
}
