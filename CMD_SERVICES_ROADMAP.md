# 业务服务迭代计划 (Business Services Roadmap)

> **版本**: v2.0  
> **更新时间**: 2025-10-27  
> **服务类型**: Go业务服务  
> **技术栈**: Go 1.21+, Kratos, Gin, GORM, Wire

## 📋 目录

- [1. Conversation Service - 对话管理服务](#1-conversation-service)
- [2. Identity Service - 身份认证服务](#2-identity-service)
- [3. Model Router - 模型路由服务](#3-model-router)
- [4. Knowledge Service - 知识库管理](#4-knowledge-service)
- [5. AI Orchestrator - AI编排服务](#5-ai-orchestrator)
- [6. Analytics Service - 分析服务](#6-analytics-service)
- [7. Notification Service - 通知服务](#7-notification-service)

---

## 1. Conversation Service

### 1.1 当前功能清单

#### ✅ 已实现功能

| 功能模块 | 功能描述 | 完成度 | 代码位置 |
|---------|---------|--------|----------|
| **对话CRUD** | 创建、读取、更新、删除对话 | 100% | `internal/biz/conversation_usecase.go` |
| **消息管理** | 发送、获取、列表消息 | 100% | `internal/biz/message_usecase.go` |
| **上下文管理** | 对话上下文存储 | 80% | `internal/domain/context.go` |
| **权限控制** | 用户级权限检查 | 100% | `internal/biz/conversation_usecase.go` |
| **多租户** | 租户隔离 | 100% | `internal/domain/conversation.go` |
| **对话状态** | active/paused/archived/deleted | 100% | `internal/domain/conversation.go` |

#### 🔄 部分完成功能

| 功能 | 当前状态 | 缺失部分 | 优先级 |
|------|---------|----------|--------|
| **上下文压缩** | 60% | LLMLingua集成、自动触发 | P0 |
| **对话分类** | 50% | 自动分类、标签推荐 | P1 |
| **对话导出** | 40% | Markdown/PDF/JSON格式 | P1 |
| **意图追踪** | 30% | 多轮意图识别 | P1 |
| **消息搜索** | 20% | 全文检索、向量检索 | P2 |

### 1.2 业界对标分析

#### 对标项目: ChatGPT, Claude, Poe

| 功能特性 | ChatGPT | Claude | Poe | **Conversation Service** | 差距分析 |
|---------|---------|--------|-----|--------------------------|---------|
| 对话管理 | ✅ | ✅ | ✅ | ✅ | 对标一致 |
| 上下文压缩 | ✅ | ✅ (100K) | ❌ | 🔄 60% | 需要LLMLingua |
| 对话分类 | ✅ 自动 | ✅ 自动 | ❌ | 🔄 50% | 需要自动分类 |
| 对话导出 | ✅ | ✅ | ❌ | 🔄 40% | 需要多格式 |
| 对话搜索 | ✅ | ✅ | ✅ | 🔄 20% | 需要语义搜索 |
| 对话分享 | ✅ | ✅ | ✅ | ❌ | 未规划 |
| 多模态消息 | ✅ | ✅ | ✅ | ❌ | 未规划 |

#### 核心差距

1. **上下文压缩不足**: 缺少智能压缩算法,长对话性能差
2. **对话搜索缺失**: 无法快速定位历史对话
3. **导出功能弱**: 仅支持简单导出

### 1.3 详细迭代计划

#### 🎯 P0 任务 (Q2 2025)

##### 1.3.1 上下文智能压缩

**功能描述**: 基于LLMLingua的对话上下文压缩,保持语义同时减少Token

**设计方案**:

```go
// internal/biz/context_compression.go

package biz

import (
	"context"
	"encoding/json"
	"fmt"

	"voiceassistant/conversation-service/internal/domain"
)

// CompressionStrategy 压缩策略
type CompressionStrategy string

const (
	StrategyLLMLingua   CompressionStrategy = "llmlingua"      // LLMLingua压缩
	StrategyTokenPrune  CompressionStrategy = "token_prune"    // Token剪枝
	StrategySummarize   CompressionStrategy = "summarize"      // 摘要压缩
	StrategyHybrid      CompressionStrategy = "hybrid"         // 混合策略
)

// CompressionConfig 压缩配置
type CompressionConfig struct {
	Strategy           CompressionStrategy
	TargetCompressionRatio float64  // 目标压缩比 (0.5 = 压缩50%)
	MinRetainedTokens      int      // 最小保留Token数
	PreserveStructure      bool     // 是否保留对话结构
	PreserveKeywords       []string // 必须保留的关键词
}

// ContextCompressor 上下文压缩器
type ContextCompressor struct {
	aiClient    *AIClient
	config      CompressionConfig
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
	// 1. 计算当前Token数
	originalTokens := c.countTokens(messages)
	
	// 2. 判断是否需要压缩
	if originalTokens < c.config.MinRetainedTokens {
		return messages, &CompressionStats{
			OriginalTokens: originalTokens,
			CompressedTokens: originalTokens,
			CompressionRatio: 1.0,
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
	}
	
	return compressed, stats, nil
}

// compressWithLLMLingua 使用LLMLingua压缩
func (c *ContextCompressor) compressWithLLMLingua(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	// 1. 构建压缩请求
	conversationText := c.messagesToText(messages)
	
	request := map[string]interface{}{
		"text": conversationText,
		"compression_ratio": c.config.TargetCompressionRatio,
		"preserve_keywords": c.config.PreserveKeywords,
	}
	
	// 2. 调用LLMLingua服务
	response, err := c.aiClient.CallLLMLingua(ctx, request)
	if err != nil {
		return nil, fmt.Errorf("llmlingua call failed: %w", err)
	}
	
	compressedText := response["compressed_text"].(string)
	
	// 3. 转换回消息格式
	compressed := c.textToMessages(compressedText, messages)
	
	return compressed, nil
}

// compressWithTokenPrune Token剪枝压缩
func (c *ContextCompressor) compressWithTokenPrune(
	ctx context.Context,
	messages []*domain.Message,
) ([]*domain.Message, error) {
	targetTokens := int(float64(c.countTokens(messages)) * c.config.TargetCompressionRatio)
	
	// 1. 保留最近的消息(优先级高)
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
	segments := c.segmentMessages(messages, 10) // 每10条一段
	
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
	oldMessages := messages[:len(messages)/2]
	summarized, err := c.compressWithSummarize(ctx, oldMessages)
	if err != nil {
		return nil, err
	}
	
	// 2. 对较新的消息使用Token剪枝
	recentMessages := messages[len(messages)/2:]
	pruned, err := c.compressWithTokenPrune(ctx, recentMessages)
	if err != nil {
		return nil, err
	}
	
	// 3. 合并
	result := append(summarized, pruned...)
	return result, nil
}

// AutoCompressor 自动压缩管理器
type AutoCompressor struct {
	compressor *ContextCompressor
	thresholds *CompressionThresholds
}

// CompressionThresholds 压缩阈值
type CompressionThresholds struct {
	TokenLimit     int     // Token数超过此值触发压缩
	MessageLimit   int     // 消息数超过此值触发压缩
	TimeLimitHours int     // 时间超过此值触发压缩
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

// CompressionStats 压缩统计
type CompressionStats struct {
	OriginalTokens   int
	CompressedTokens int
	CompressionRatio float64
	Strategy         string
	DurationMs       int64
}
```

**使用示例**:

```go
// 示例1: 手动压缩
compressor := NewContextCompressor(aiClient, CompressionConfig{
	Strategy:           StrategyLLMLingua,
	TargetCompressionRatio: 0.5,
	MinRetainedTokens:      1000,
	PreserveKeywords:       []string{"重要", "关键"},
})

compressed, stats, err := compressor.Compress(ctx, messages)
if err != nil {
	return err
}

log.Printf("压缩比: %.2f, 原始: %d tokens, 压缩后: %d tokens",
	stats.CompressionRatio,
	stats.OriginalTokens,
	stats.CompressedTokens,
)

// 示例2: 自动压缩
autoCompressor := NewAutoCompressor(compressor, &CompressionThresholds{
	TokenLimit:     4000,
	MessageLimit:   50,
	TimeLimitHours: 24,
})

if autoCompressor.ShouldCompress(ctx, conversation) {
	compressed, err := autoCompressor.CompressIfNeeded(ctx, conversation, messages)
	// ... 使用压缩后的消息
}
```

**实现步骤**:

1. **Week 1-2**: 实现Token剪枝和摘要压缩
2. **Week 3-4**: 集成LLMLingua服务
3. **Week 5-6**: 实现自动压缩触发机制
4. **Week 7-8**: 测试与性能优化

**验收标准**:

- [ ] 压缩比达到50%同时保留90%+语义
- [ ] 压缩延迟<500ms
- [ ] 自动压缩准确触发率>95%
- [ ] 长对话(100+轮)响应延迟降低50%+

##### 1.3.2 对话分类与标签

**功能描述**: 自动分类对话,打标签,支持智能搜索

**设计方案**:

```go
// internal/biz/category_usecase.go

package biz

import (
	"context"
	"encoding/json"

	"voiceassistant/conversation-service/internal/domain"
)

// Category 对话分类
type Category string

const (
	CategoryGeneral      Category = "general"      // 通用对话
	CategorySupport      Category = "support"      // 客服支持
	CategorySales        Category = "sales"        // 销售咨询
	CategoryTechnical    Category = "technical"    // 技术问题
	CategoryComplaint    Category = "complaint"    // 投诉建议
	CategoryOther        Category = "other"        // 其他
)

// Tag 对话标签
type Tag struct {
	ID          string
	Name        string
	Description string
	Color       string  // 标签颜色
	Count       int     // 使用次数
	CreatedAt   time.Time
}

// CategoryUsecase 分类用例
type CategoryUsecase struct {
	conversationRepo domain.ConversationRepository
	aiClient         *AIClient
	tagRepo          TagRepository
}

// NewCategoryUsecase 创建分类用例
func NewCategoryUsecase(
	conversationRepo domain.ConversationRepository,
	aiClient *AIClient,
	tagRepo TagRepository,
) *CategoryUsecase {
	return &CategoryUsecase{
		conversationRepo: conversationRepo,
		aiClient:         aiClient,
		tagRepo:          tagRepo,
	}
}

// ClassifyConversation 分类对话
func (uc *CategoryUsecase) ClassifyConversation(
	ctx context.Context,
	conversationID string,
) (*ClassificationResult, error) {
	// 1. 获取对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}
	
	// 2. 获取对话消息
	messages, err := uc.conversationRepo.GetMessages(ctx, conversationID)
	if err != nil {
		return nil, err
	}
	
	// 3. 提取对话摘要
	summary := uc.summarizeConversation(messages)
	
	// 4. 调用AI分类
	category, confidence, err := uc.classifyWithAI(ctx, summary)
	if err != nil {
		return nil, err
	}
	
	// 5. 生成标签
	tags, err := uc.generateTags(ctx, summary, category)
	if err != nil {
		return nil, err
	}
	
	// 6. 保存分类结果
	conversation.Category = string(category)
	conversation.Tags = tags
	
	err = uc.conversationRepo.UpdateConversation(ctx, conversation)
	if err != nil {
		return nil, err
	}
	
	return &ClassificationResult{
		Category:   category,
		Confidence: confidence,
		Tags:       tags,
	}, nil
}

// classifyWithAI AI分类
func (uc *CategoryUsecase) classifyWithAI(
	ctx context.Context,
	summary string,
) (Category, float64, error) {
	prompt := fmt.Sprintf(`
Classify the following conversation into one category:
- general: General conversation
- support: Customer support
- sales: Sales inquiry
- technical: Technical question
- complaint: Complaint or suggestion
- other: Other

Conversation: %s

Return JSON:
{
  "category": "...",
  "confidence": 0.95
}
`, summary)

	response, err := uc.aiClient.Chat(ctx, []Message{
		{Role: "user", Content: prompt},
	})
	if err != nil {
		return CategoryGeneral, 0, err
	}
	
	var result struct {
		Category   string  `json:"category"`
		Confidence float64 `json:"confidence"`
	}
	
	err = json.Unmarshal([]byte(response.Content), &result)
	if err != nil {
		return CategoryGeneral, 0, err
	}
	
	return Category(result.Category), result.Confidence, nil
}

// generateTags 生成标签
func (uc *CategoryUsecase) generateTags(
	ctx context.Context,
	summary string,
	category Category,
) ([]string, error) {
	prompt := fmt.Sprintf(`
Generate 3-5 relevant tags for this conversation:

Category: %s
Summary: %s

Return JSON array:
["tag1", "tag2", "tag3"]
`, category, summary)

	response, err := uc.aiClient.Chat(ctx, []Message{
		{Role: "user", Content: prompt},
	})
	if err != nil {
		return nil, err
	}
	
	var tags []string
	err = json.Unmarshal([]byte(response.Content), &tags)
	if err != nil {
		return nil, err
	}
	
	// 保存标签到数据库
	for _, tagName := range tags {
		_, err := uc.tagRepo.GetOrCreateTag(ctx, tagName)
		if err != nil {
			return nil, err
		}
	}
	
	return tags, nil
}

// SuggestTags 推荐标签
func (uc *CategoryUsecase) SuggestTags(
	ctx context.Context,
	conversationID string,
) ([]Tag, error) {
	// 1. 获取对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}
	
	// 2. 基于分类推荐热门标签
	popularTags, err := uc.tagRepo.GetPopularTagsByCategory(
		ctx,
		conversation.Category,
		10,
	)
	if err != nil {
		return nil, err
	}
	
	return popularTags, nil
}

// SearchConversationsByTag 按标签搜索
func (uc *CategoryUsecase) SearchConversationsByTag(
	ctx context.Context,
	tenantID string,
	userID string,
	tags []string,
	limit int,
	offset int,
) ([]*domain.Conversation, int, error) {
	return uc.conversationRepo.SearchByTags(
		ctx,
		tenantID,
		userID,
		tags,
		limit,
		offset,
	)
}

// ClassificationResult 分类结果
type ClassificationResult struct {
	Category   Category
	Confidence float64
	Tags       []string
}
```

**数据库表设计**:

```sql
-- 对话表添加分类字段
ALTER TABLE conversations 
ADD COLUMN category VARCHAR(50),
ADD COLUMN tags TEXT[]; -- PostgreSQL数组

CREATE INDEX idx_conversations_category ON conversations(category);
CREATE INDEX idx_conversations_tags ON conversations USING GIN(tags);

-- 标签表
CREATE TABLE tags (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    color VARCHAR(20),
    category VARCHAR(50),
    count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tags_category ON tags(category);
CREATE INDEX idx_tags_count ON tags(count DESC);
```

**实现优先级**: P1  
**预计工作量**: 4周  
**负责人**: 后端工程师

##### 1.3.3 对话导出

**功能描述**: 导出对话为Markdown/PDF/JSON格式

**设计方案**:

```go
// internal/biz/export_usecase.go

package biz

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"text/template"
	"time"

	"github.com/go-pdf/fpdf"
	"voiceassistant/conversation-service/internal/domain"
)

// ExportFormat 导出格式
type ExportFormat string

const (
	FormatMarkdown ExportFormat = "markdown"
	FormatPDF      ExportFormat = "pdf"
	FormatJSON     ExportFormat = "json"
	FormatHTML     ExportFormat = "html"
)

// ExportUsecase 导出用例
type ExportUsecase struct {
	conversationRepo domain.ConversationRepository
	messageRepo      domain.MessageRepository
}

// NewExportUsecase 创建导出用例
func NewExportUsecase(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
) *ExportUsecase {
	return &ExportUsecase{
		conversationRepo: conversationRepo,
		messageRepo:      messageRepo,
	}
}

// ExportConversation 导出对话
func (uc *ExportUsecase) ExportConversation(
	ctx context.Context,
	conversationID string,
	userID string,
	format ExportFormat,
) ([]byte, error) {
	// 1. 权限检查
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}
	
	if conversation.UserID != userID {
		return nil, domain.ErrUnauthorized
	}
	
	// 2. 获取消息
	messages, err := uc.messageRepo.ListMessages(ctx, conversationID, 1000, 0)
	if err != nil {
		return nil, err
	}
	
	// 3. 根据格式导出
	switch format {
	case FormatMarkdown:
		return uc.exportAsMarkdown(conversation, messages)
	case FormatPDF:
		return uc.exportAsPDF(conversation, messages)
	case FormatJSON:
		return uc.exportAsJSON(conversation, messages)
	case FormatHTML:
		return uc.exportAsHTML(conversation, messages)
	default:
		return nil, fmt.Errorf("unsupported format: %s", format)
	}
}

// exportAsMarkdown 导出为Markdown
func (uc *ExportUsecase) exportAsMarkdown(
	conversation *domain.Conversation,
	messages []*domain.Message,
) ([]byte, error) {
	var buf bytes.Buffer
	
	// 标题
	buf.WriteString(fmt.Sprintf("# %s\n\n", conversation.Title))
	
	// 元信息
	buf.WriteString(fmt.Sprintf("**创建时间**: %s\n", conversation.CreatedAt.Format("2006-01-02 15:04:05")))
	buf.WriteString(fmt.Sprintf("**对话模式**: %s\n", conversation.Mode))
	if conversation.Category != "" {
		buf.WriteString(fmt.Sprintf("**分类**: %s\n", conversation.Category))
	}
	if len(conversation.Tags) > 0 {
		buf.WriteString(fmt.Sprintf("**标签**: %s\n", strings.Join(conversation.Tags, ", ")))
	}
	buf.WriteString("\n---\n\n")
	
	// 消息
	for _, msg := range messages {
		roleIcon := "👤"
		if msg.Role == "assistant" {
			roleIcon = "🤖"
		} else if msg.Role == "system" {
			roleIcon = "⚙️"
		}
		
		buf.WriteString(fmt.Sprintf("### %s %s\n\n", roleIcon, strings.Title(msg.Role)))
		buf.WriteString(fmt.Sprintf("%s\n\n", msg.Content))
		buf.WriteString(fmt.Sprintf("*%s*\n\n", msg.CreatedAt.Format("15:04:05")))
		buf.WriteString("---\n\n")
	}
	
	// 页脚
	buf.WriteString(fmt.Sprintf("\n\n*导出时间: %s*\n", time.Now().Format("2006-01-02 15:04:05")))
	
	return buf.Bytes(), nil
}

// exportAsPDF 导出为PDF
func (uc *ExportUsecase) exportAsPDF(
	conversation *domain.Conversation,
	messages []*domain.Message,
) ([]byte, error) {
	pdf := fpdf.New("P", "mm", "A4", "")
	pdf.AddPage()
	
	// 设置中文字体(需要安装ttf字体)
	pdf.AddUTF8Font("NotoSansSC", "", "fonts/NotoSansSC-Regular.ttf")
	pdf.SetFont("NotoSansSC", "", 16)
	
	// 标题
	pdf.Cell(190, 10, conversation.Title)
	pdf.Ln(15)
	
	// 元信息
	pdf.SetFont("NotoSansSC", "", 10)
	pdf.Cell(190, 6, fmt.Sprintf("创建时间: %s", conversation.CreatedAt.Format("2006-01-02 15:04:05")))
	pdf.Ln(6)
	pdf.Cell(190, 6, fmt.Sprintf("对话模式: %s", conversation.Mode))
	pdf.Ln(10)
	
	// 消息
	pdf.SetFont("NotoSansSC", "", 12)
	for _, msg := range messages {
		// 角色
		roleText := ""
		switch msg.Role {
		case "user":
			roleText = "👤 用户"
		case "assistant":
			roleText = "🤖 助手"
		case "system":
			roleText = "⚙️ 系统"
		}
		
		pdf.SetFont("NotoSansSC", "B", 11)
		pdf.Cell(190, 6, roleText)
		pdf.Ln(6)
		
		// 内容
		pdf.SetFont("NotoSansSC", "", 10)
		pdf.MultiCell(190, 5, msg.Content, "", "", false)
		pdf.Ln(3)
		
		// 时间
		pdf.SetFont("NotoSansSC", "I", 9)
		pdf.Cell(190, 5, msg.CreatedAt.Format("15:04:05"))
		pdf.Ln(8)
	}
	
	// 生成PDF
	var buf bytes.Buffer
	err := pdf.Output(&buf)
	if err != nil {
		return nil, err
	}
	
	return buf.Bytes(), nil
}

// exportAsJSON 导出为JSON
func (uc *ExportUsecase) exportAsJSON(
	conversation *domain.Conversation,
	messages []*domain.Message,
) ([]byte, error) {
	export := struct {
		Conversation *domain.Conversation `json:"conversation"`
		Messages     []*domain.Message    `json:"messages"`
		ExportedAt   time.Time            `json:"exported_at"`
	}{
		Conversation: conversation,
		Messages:     messages,
		ExportedAt:   time.Now(),
	}
	
	return json.MarshalIndent(export, "", "  ")
}

// exportAsHTML 导出为HTML
func (uc *ExportUsecase) exportAsHTML(
	conversation *domain.Conversation,
	messages []*domain.Message,
) ([]byte, error) {
	tmpl := `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{.Conversation.Title}}</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { border-bottom: 2px solid #333; margin-bottom: 20px; }
        .message { margin-bottom: 20px; padding: 10px; border-radius: 5px; }
        .user { background-color: #e3f2fd; }
        .assistant { background-color: #f3e5f5; }
        .role { font-weight: bold; }
        .time { font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{.Conversation.Title}}</h1>
        <p>创建时间: {{.Conversation.CreatedAt}}</p>
        <p>对话模式: {{.Conversation.Mode}}</p>
    </div>
    
    {{range .Messages}}
    <div class="message {{.Role}}">
        <div class="role">{{.Role}}</div>
        <div class="content">{{.Content}}</div>
        <div class="time">{{.CreatedAt}}</div>
    </div>
    {{end}}
    
    <div class="footer">
        <p>导出时间: {{.ExportedAt}}</p>
    </div>
</body>
</html>
`

	t, err := template.New("html").Parse(tmpl)
	if err != nil {
		return nil, err
	}
	
	var buf bytes.Buffer
	data := struct {
		Conversation *domain.Conversation
		Messages     []*domain.Message
		ExportedAt   string
	}{
		Conversation: conversation,
		Messages:     messages,
		ExportedAt:   time.Now().Format("2006-01-02 15:04:05"),
	}
	
	err = t.Execute(&buf, data)
	if err != nil {
		return nil, err
	}
	
	return buf.Bytes(), nil
}
```

**API接口**:

```go
// internal/server/http.go

// ExportConversation 导出对话
func (s *Server) ExportConversation(c *gin.Context) {
	conversationID := c.Param("id")
	userID := c.Query("user_id")
	format := ExportFormat(c.Query("format"))
	
	if format == "" {
		format = FormatMarkdown
	}
	
	data, err := s.exportUsecase.ExportConversation(
		c.Request.Context(),
		conversationID,
		userID,
		format,
	)
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}
	
	// 设置响应头
	filename := fmt.Sprintf("conversation_%s.%s", conversationID, format)
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=%s", filename))
	
	switch format {
	case FormatMarkdown:
		c.Data(200, "text/markdown", data)
	case FormatPDF:
		c.Data(200, "application/pdf", data)
	case FormatJSON:
		c.Data(200, "application/json", data)
	case FormatHTML:
		c.Data(200, "text/html", data)
	}
}
```

**实现优先级**: P1  
**预计工作量**: 3周  
**负责人**: 后端工程师

---

## 2. Identity Service

### 2.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 |
|------|------|--------|
| **用户注册** | 邮箱/手机注册 | 100% |
| **用户登录** | JWT认证 | 100% |
| **密码加密** | bcrypt加密 | 100% |
| **租户管理** | 多租户隔离 | 100% |
| **角色管理** | RBAC基础框架 | 90% |
| **Token刷新** | Refresh Token | 100% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **审计日志** | 详细操作审计 | P0 |
| **SSO单点登录** | OAuth2/SAML | P1 |
| **MFA多因素认证** | TOTP/SMS | P1 |
| **权限细粒度控制** | 资源级权限 | P1 |

### 2.2 详细迭代计划

#### 🎯 P0 任务 (Q2 2025)

##### 2.2.1 审计日志完整性

**功能描述**: 记录所有敏感操作,支持审计查询

**设计方案**:

```go
// internal/biz/audit_log.go

package biz

import (
	"context"
	"encoding/json"
	"time"

	"voiceassistant/identity-service/internal/domain"
)

// AuditAction 审计动作
type AuditAction string

const (
	ActionLogin          AuditAction = "login"
	ActionLogout         AuditAction = "logout"
	ActionRegister       AuditAction = "register"
	ActionPasswordChange AuditAction = "password_change"
	ActionRoleAssign     AuditAction = "role_assign"
	ActionPermissionGrant AuditAction = "permission_grant"
	ActionUserDelete     AuditAction = "user_delete"
	ActionDataExport     AuditAction = "data_export"
)

// AuditLog 审计日志
type AuditLog struct {
	ID            string
	TenantID      string
	UserID        string
	Action        AuditAction
	Resource      string      // 操作的资源
	ResourceID    string      // 资源ID
	Details       interface{} // 详细信息
	IPAddress     string
	UserAgent     string
	Status        string      // success/failure
	ErrorMessage  string
	CreatedAt     time.Time
}

// AuditLogRepository 审计日志仓储
type AuditLogRepository interface {
	Create(ctx context.Context, log *AuditLog) error
	Query(ctx context.Context, query *AuditQuery) ([]*AuditLog, int, error)
}

// AuditQuery 审计查询
type AuditQuery struct {
	TenantID   string
	UserID     string
	Actions    []AuditAction
	Resource   string
	StartTime  time.Time
	EndTime    time.Time
	Status     string
	Limit      int
	Offset     int
}

// AuditLogUsecase 审计日志用例
type AuditLogUsecase struct {
	auditRepo AuditLogRepository
}

// NewAuditLogUsecase 创建审计日志用例
func NewAuditLogUsecase(auditRepo AuditLogRepository) *AuditLogUsecase {
	return &AuditLogUsecase{
		auditRepo: auditRepo,
	}
}

// LogAction 记录审计日志
func (uc *AuditLogUsecase) LogAction(
	ctx context.Context,
	tenantID string,
	userID string,
	action AuditAction,
	resource string,
	resourceID string,
	details interface{},
	status string,
	errorMessage string,
) error {
	// 从context获取请求信息
	ipAddress := getIPFromContext(ctx)
	userAgent := getUserAgentFromContext(ctx)
	
	log := &AuditLog{
		ID:           generateID(),
		TenantID:     tenantID,
		UserID:       userID,
		Action:       action,
		Resource:     resource,
		ResourceID:   resourceID,
		Details:      details,
		IPAddress:    ipAddress,
		UserAgent:    userAgent,
		Status:       status,
		ErrorMessage: errorMessage,
		CreatedAt:    time.Now(),
	}
	
	return uc.auditRepo.Create(ctx, log)
}

// QueryLogs 查询审计日志
func (uc *AuditLogUsecase) QueryLogs(
	ctx context.Context,
	query *AuditQuery,
) ([]*AuditLog, int, error) {
	return uc.auditRepo.Query(ctx, query)
}

// ExportLogs 导出审计日志
func (uc *AuditLogUsecase) ExportLogs(
	ctx context.Context,
	query *AuditQuery,
) ([]byte, error) {
	logs, _, err := uc.auditRepo.Query(ctx, query)
	if err != nil {
		return nil, err
	}
	
	return json.MarshalIndent(logs, "", "  ")
}
```

**数据库表设计**:

```sql
CREATE TABLE audit_logs (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource VARCHAR(100),
    resource_id VARCHAR(64),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_audit_logs_tenant ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource, resource_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- 分区表(按月分区)
CREATE TABLE audit_logs_202501 PARTITION OF audit_logs
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

**实现优先级**: P0  
**预计工作量**: 2周  
**负责人**: 后端工程师

---

## 3. Model Router

### 3.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 |
|------|------|--------|
| **智能路由** | 成本/性能/平衡模式 | 100% |
| **负载均衡** | 多种策略 | 100% |
| **A/B测试** | 模型对比测试 | 100% |
| **降级策略** | 自动降级 | 90% |
| **成本追踪** | Token计费 | 100% |
| **健康检查** | 模型可用性 | 100% |
| **PostHog集成** | 事件追踪 | 100% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **实时A/B分析** | 实时报表 | P1 |
| **自适应路由** | 机器学习优化 | P1 |
| **预算告警** | 成本超限告警 | P1 |

### 3.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 3.2.1 实时A/B测试分析

**功能描述**: 实时展示A/B测试效果,自动判断最优变体

**设计方案**:

```go
// internal/application/ab_testing_analysis.go

package application

import (
	"context"
	"math"
	"time"
)

// ABTestingAnalyzer A/B测试分析器
type ABTestingAnalyzer struct {
	testingService *ABTestingService
	statsCalculator *StatisticsCalculator
}

// NewABTestingAnalyzer 创建分析器
func NewABTestingAnalyzer(
	testingService *ABTestingService,
	statsCalculator *StatisticsCalculator,
) *ABTestingAnalyzer {
	return &ABTestingAnalyzer{
		testingService:  testingService,
		statsCalculator: statsCalculator,
	}
}

// AnalyzeInRealtime 实时分析
func (a *ABTestingAnalyzer) AnalyzeInRealtime(
	ctx context.Context,
	testID string,
) (*RealtimeAnalysis, error) {
	// 1. 获取测试结果
	results, err := a.testingService.GetTestResults(ctx, testID)
	if err != nil {
		return nil, err
	}
	
	// 2. 统计显著性检验
	significance := a.calculateStatisticalSignificance(results)
	
	// 3. 计算置信区间
	confidenceIntervals := a.calculateConfidenceIntervals(results)
	
	// 4. 判断是否可以得出结论
	conclusion := a.drawConclusion(results, significance, confidenceIntervals)
	
	// 5. 生成建议
	recommendation := a.generateRecommendation(conclusion)
	
	return &RealtimeAnalysis{
		TestID:              testID,
		Variants:            results,
		Significance:        significance,
		ConfidenceIntervals: confidenceIntervals,
		Conclusion:          conclusion,
		Recommendation:      recommendation,
		UpdatedAt:           time.Now(),
	}, nil
}

// calculateStatisticalSignificance 计算统计显著性
func (a *ABTestingAnalyzer) calculateStatisticalSignificance(
	results map[string]*ABTestResult,
) *SignificanceTest {
	// 使用卡方检验或t检验
	// 这里简化实现
	
	variants := make([]*ABTestResult, 0, len(results))
	for _, result := range results {
		variants = append(variants, result)
	}
	
	if len(variants) < 2 {
		return &SignificanceTest{
			PValue:      1.0,
			IsSignificant: false,
		}
	}
	
	// 比较前两个变体
	v1, v2 := variants[0], variants[1]
	
	// 计算成功率差异
	rate1 := float64(v1.SuccessCount) / float64(v1.RequestCount)
	rate2 := float64(v2.SuccessCount) / float64(v2.RequestCount)
	
	// 计算标准误差
	se1 := math.Sqrt(rate1 * (1 - rate1) / float64(v1.RequestCount))
	se2 := math.Sqrt(rate2 * (1 - rate2) / float64(v2.RequestCount))
	seDiff := math.Sqrt(se1*se1 + se2*se2)
	
	// 计算z分数
	zScore := (rate1 - rate2) / seDiff
	
	// 计算p值(双尾检验)
	pValue := 2 * (1 - normalCDF(math.Abs(zScore)))
	
	return &SignificanceTest{
		PValue:        pValue,
		ZScore:        zScore,
		IsSignificant: pValue < 0.05, // 95%置信度
	}
}

// calculateConfidenceIntervals 计算置信区间
func (a *ABTestingAnalyzer) calculateConfidenceIntervals(
	results map[string]*ABTestResult,
) map[string]*ConfidenceInterval {
	intervals := make(map[string]*ConfidenceInterval)
	
	for variantID, result := range results {
		if result.RequestCount == 0 {
			continue
		}
		
		// 计算成功率
		successRate := float64(result.SuccessCount) / float64(result.RequestCount)
		
		// 计算标准误差
		se := math.Sqrt(successRate * (1 - successRate) / float64(result.RequestCount))
		
		// 95%置信区间 (z=1.96)
		margin := 1.96 * se
		
		intervals[variantID] = &ConfidenceInterval{
			Lower: successRate - margin,
			Upper: successRate + margin,
			Mean:  successRate,
		}
	}
	
	return intervals
}

// drawConclusion 得出结论
func (a *ABTestingAnalyzer) drawConclusion(
	results map[string]*ABTestResult,
	significance *SignificanceTest,
	intervals map[string]*ConfidenceInterval,
) *TestConclusion {
	// 1. 检查样本量是否足够
	minSampleSize := 100
	totalSamples := 0
	for _, result := range results {
		totalSamples += int(result.RequestCount)
	}
	
	if totalSamples < minSampleSize {
		return &TestConclusion{
			Status:  "insufficient_data",
			Message: fmt.Sprintf("需要至少%d个样本,当前只有%d个", minSampleSize, totalSamples),
		}
	}
	
	// 2. 检查统计显著性
	if !significance.IsSignificant {
		return &TestConclusion{
			Status:  "no_significant_difference",
			Message: "变体间无统计学显著差异",
			PValue:  significance.PValue,
		}
	}
	
	// 3. 找出最优变体
	var bestVariant string
	bestScore := -1.0
	
	for variantID, result := range results {
		score := float64(result.SuccessCount) / float64(result.RequestCount)
		if score > bestScore {
			bestScore = score
			bestVariant = variantID
		}
	}
	
	return &TestConclusion{
		Status:       "significant_winner",
		Message:      fmt.Sprintf("变体%s显著优于其他变体", bestVariant),
		Winner:       bestVariant,
		PValue:       significance.PValue,
		Confidence:   1 - significance.PValue,
	}
}

// generateRecommendation 生成建议
func (a *ABTestingAnalyzer) generateRecommendation(
	conclusion *TestConclusion,
) string {
	switch conclusion.Status {
	case "insufficient_data":
		return "建议继续收集数据,至少达到100个样本后再评估"
		
	case "no_significant_difference":
		return "变体间无显著差异,可以选择成本最低的变体,或继续测试"
		
	case "significant_winner":
		return fmt.Sprintf("建议采用变体%s,置信度%.2f%%", conclusion.Winner, conclusion.Confidence*100)
		
	default:
		return "无法提供建议,请检查测试配置"
	}
}

// RealtimeAnalysis 实时分析结果
type RealtimeAnalysis struct {
	TestID              string
	Variants            map[string]*ABTestResult
	Significance        *SignificanceTest
	ConfidenceIntervals map[string]*ConfidenceInterval
	Conclusion          *TestConclusion
	Recommendation      string
	UpdatedAt           time.Time
}

// SignificanceTest 显著性检验
type SignificanceTest struct {
	PValue        float64
	ZScore        float64
	IsSignificant bool
}

// ConfidenceInterval 置信区间
type ConfidenceInterval struct {
	Lower float64
	Upper float64
	Mean  float64
}

// TestConclusion 测试结论
type TestConclusion struct {
	Status     string
	Message    string
	Winner     string
	PValue     float64
	Confidence float64
}

// normalCDF 标准正态分布累积分布函数
func normalCDF(x float64) float64 {
	return 0.5 * (1 + math.Erf(x/math.Sqrt2))
}
```

**实现优先级**: P1  
**预计工作量**: 4周  
**负责人**: 后端工程师

---

## 4. Knowledge Service (Go)

### 4.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 |
|------|------|--------|
| **知识库CRUD** | 创建、读取、更新、删除知识库 | 100% |
| **文档管理** | 上传、解析、存储文档 | 100% |
| **分块管理** | 文本分块、去重 | 100% |
| **元数据** | 自定义元数据 | 100% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **文档版本管理** | 版本控制、回滚 | P1 |
| **知识库统计** | 详细统计报表 | P1 |
| **批量导入** | CSV/Excel批量导入 | P1 |

### 4.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 4.2.1 文档版本管理

**功能描述**: 文档版本控制,支持版本对比和回滚

**设计方案**:

```go
// internal/domain/document_version.go

package domain

import (
	"time"
)

// DocumentVersion 文档版本
type DocumentVersion struct {
	ID              string
	DocumentID      string
	VersionNumber   int
	Content         string
	ChangeLog       string
	ModifiedBy      string
	ModifiedAt      time.Time
	ContentHash     string
	Size            int64
}

// DocumentVersionRepository 文档版本仓储
type DocumentVersionRepository interface {
	CreateVersion(ctx context.Context, version *DocumentVersion) error
	GetVersion(ctx context.Context, documentID string, versionNumber int) (*DocumentVersion, error)
	ListVersions(ctx context.Context, documentID string) ([]*DocumentVersion, error)
	GetLatestVersion(ctx context.Context, documentID string) (*DocumentVersion, error)
	CompareVersions(ctx context.Context, documentID string, v1, v2 int) (*VersionDiff, error)
}

// VersionDiff 版本差异
type VersionDiff struct {
	Version1       int
	Version2       int
	AddedLines     []string
	DeletedLines   []string
	ModifiedLines  []DiffLine
}

// DiffLine 差异行
type DiffLine struct {
	LineNumber int
	OldContent string
	NewContent string
}
```

**实现优先级**: P1  
**预计工作量**: 3周

---

## 5. AI Orchestrator

### 5.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 |
|------|------|--------|
| **Pipeline编排** | 任务流程编排 | 80% |
| **任务管理** | 任务状态追踪 | 100% |
| **服务调用** | gRPC服务调用 | 100% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **可视化编排** | 图形化编排界面 | P1 |
| **条件分支** | 复杂条件逻辑 | P1 |
| **错误重试** | 智能重试策略 | P1 |

### 5.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 5.2.1 可视化工作流编排

**功能描述**: 提供图形化界面编排AI工作流

**设计方案**:

- 前端使用React Flow实现拖拽式工作流编辑器
- 后端提供工作流定义API
- 支持导入/导出工作流JSON
- 实时预览执行效果

**实现优先级**: P1  
**预计工作量**: 6周  
**负责人**: 前端+后端工程师

---

## 6. Analytics Service

### 6.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 |
|------|------|--------|
| **指标收集** | ClickHouse存储 | 100% |
| **基础报表** | 简单统计 | 70% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **智能分析** | AI驱动的分析 | P1 |
| **自定义报表** | 用户自定义报表 | P1 |
| **实时大屏** | 实时数据大屏 | P2 |

### 6.2 详细迭代计划

#### 🎯 P1 任务 (Q3 2025)

##### 6.2.1 智能对话分析

**功能描述**: 使用AI分析对话质量、用户满意度、问题分类

**设计方案**:

```go
// internal/biz/intelligent_analysis.go

package biz

// IntelligentAnalysisUsecase 智能分析用例
type IntelligentAnalysisUsecase struct {
	aiClient      *AIClient
	analyticsRepo AnalyticsRepository
}

// AnalyzeConversationQuality 分析对话质量
func (uc *IntelligentAnalysisUsecase) AnalyzeConversationQuality(
	ctx context.Context,
	conversationID string,
) (*QualityAnalysis, error) {
	// 1. 获取对话数据
	conversation := uc.getConversation(ctx, conversationID)
	
	// 2. AI分析
	prompt := fmt.Sprintf(`
Analyze the quality of this conversation:

Conversation: %s

Rate on:
1. Satisfaction (0-10)
2. Problem Resolution (yes/no)
3. Tone (positive/neutral/negative)
4. Key Issues

Return JSON:
{
  "satisfaction": 8,
  "resolved": true,
  "tone": "positive",
  "issues": ["billing", "technical"]
}
`, conversation)

	response, err := uc.aiClient.Analyze(ctx, prompt)
	if err != nil {
		return nil, err
	}
	
	// 3. 解析结果
	var analysis QualityAnalysis
	json.Unmarshal([]byte(response), &analysis)
	
	return &analysis, nil
}

// QualityAnalysis 质量分析
type QualityAnalysis struct {
	Satisfaction float64
	Resolved     bool
	Tone         string
	Issues       []string
}
```

**实现优先级**: P1  
**预计工作量**: 4周

---

## 7. Notification Service

### 7.1 当前功能清单

#### ✅ 已实现功能

| 功能 | 描述 | 完成度 |
|------|------|--------|
| **邮件通知** | SMTP邮件发送 | 100% |
| **模板管理** | 通知模板 | 80% |

#### 🔄 待完善功能

| 功能 | 缺失部分 | 优先级 |
|------|----------|--------|
| **多渠道** | 短信/Push/Webhook | P2 |
| **通知偏好** | 用户偏好设置 | P2 |

### 7.2 详细迭代计划

#### 🎯 P2 任务 (Q4 2025)

##### 7.2.1 多渠道通知

**功能描述**: 支持短信、Push、Webhook等多种通知渠道

**实现优先级**: P2  
**预计工作量**: 4周

---

## 📈 总体进度追踪

### 时间线

```
Q2 2025 (Apr-Jun)
├── Conversation: 上下文压缩 + 对话分类
├── Identity: 审计日志完善
└── Model Router: 实时A/B分析

Q3 2025 (Jul-Sep)
├── Conversation: 对话导出 + 意图追踪
├── Knowledge: 文档版本管理
├── AI Orchestrator: 可视化编排
└── Analytics: 智能分析

Q4 2025 (Oct-Dec)
├── Notification: 多渠道通知
├── 性能优化
└── 文档完善
```

### 资源需求

| 角色 | 人数 | Q2工作量 | Q3工作量 | Q4工作量 |
|------|------|---------|---------|---------|
| 后端工程师(Go) | 2 | 100% | 100% | 80% |
| 前端工程师 | 1 | 50% | 80% | 60% |
| 测试工程师 | 1 | 50% | 60% | 80% |
| DevOps工程师 | 1 | 30% | 40% | 60% |

### 里程碑

- **M1 (2025-06-30)**: P0核心功能完成
- **M2 (2025-09-30)**: P1功能完成
- **M3 (2025-12-31)**: 系统优化完成

---

## 📞 联系方式

**负责人**: 业务服务团队  
**邮箱**: backend-team@voiceassistant.com  
**文档更新**: 每月1号更新进度

---

**最后更新**: 2025-10-27  
**下次Review**: 2025-11-27


