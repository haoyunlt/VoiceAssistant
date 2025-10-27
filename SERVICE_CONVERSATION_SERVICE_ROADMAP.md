# Conversation Service 服务功能清单与迭代计划

## 服务概述

Conversation Service 是对话管理服务，提供对话和消息管理、上下文管理、多模态支持等功能。

**技术栈**: Kratos + Gin + PostgreSQL + GORM + Wire

**端口**: 8080

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. 核心功能
- ✅ 对话 CRUD 操作
- ✅ 消息 CRUD 操作
- ✅ 用户权限检查
- ✅ 多租户支持
- ✅ DDD 分层架构

#### 2. API 接口
- ✅ `/api/v1/conversations` - 对话管理
- ✅ `/api/v1/conversations/:id/messages` - 消息管理
- ✅ `/api/v1/messages/:id` - 单条消息

---

## 二、待完成功能清单

### 🔄 P0 - 核心功能（迭代1：2周）

#### 1. 上下文压缩
**当前状态**: 已创建文件，需完善

**位置**: `cmd/conversation-service/internal/biz/context_compression.go`

**待实现**:

```go
// 文件: cmd/conversation-service/internal/biz/context_compression.go

package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	
	"github.com/sashabaranov/go-openai"
)

type ContextCompressionService struct {
	llmClient  *openai.Client
	maxTokens  int
	targetRatio float64 // 压缩目标比例
}

func NewContextCompressionService(apiKey string, maxTokens int) *ContextCompressionService {
	return &ContextCompressionService{
		llmClient:   openai.NewClient(apiKey),
		maxTokens:   maxTokens,
		targetRatio: 0.5, // 压缩到 50%
	}
}

// CompressContext 压缩对话上下文
func (s *ContextCompressionService) CompressContext(
	ctx context.Context,
	messages []*domain.Message,
	targetTokens int,
) ([]*domain.Message, error) {
	// 1. 计算当前 token 数
	currentTokens := s.estimateTokens(messages)
	
	if currentTokens <= targetTokens {
		return messages, nil // 无需压缩
	}
	
	// 2. 确定压缩策略
	strategy := s.determineStrategy(messages, currentTokens, targetTokens)
	
	// 3. 执行压缩
	switch strategy {
	case "summary":
		return s.compressBySummary(ctx, messages, targetTokens)
	case "selective":
		return s.compressBySelection(messages, targetTokens)
	case "sliding_window":
		return s.compressBySlidingWindow(messages, targetTokens)
	default:
		return messages, nil
	}
}

// compressBySummary 通过总结压缩
func (s *ContextCompressionService) compressBySummary(
	ctx context.Context,
	messages []*domain.Message,
	targetTokens int,
) ([]*domain.Message, error) {
	// 保留最新的几条消息
	keepCount := 5
	recentMessages := messages
	if len(messages) > keepCount {
		recentMessages = messages[len(messages)-keepCount:]
	}
	
	// 将较老的消息总结
	oldMessages := messages[:len(messages)-keepCount]
	if len(oldMessages) == 0 {
		return recentMessages, nil
	}
	
	// 构建总结 prompt
	conversationText := s.messagesToText(oldMessages)
	
	prompt := fmt.Sprintf(`
请总结以下对话的关键信息和上下文，保留重要的细节和决策点:

%s

总结(尽量简洁):`, conversationText)
	
	// 调用 LLM 生成总结
	resp, err := s.llmClient.CreateChatCompletion(
		ctx,
		openai.ChatCompletionRequest{
			Model: openai.GPT3Dot5Turbo,
			Messages: []openai.ChatCompletionMessage{
				{
					Role:    openai.ChatMessageRoleUser,
					Content: prompt,
				},
			},
			MaxTokens:   targetTokens / 2, // 总结占一半
			Temperature: 0.3,
		},
	)
	
	if err != nil {
		return nil, fmt.Errorf("failed to generate summary: %w", err)
	}
	
	summary := resp.Choices[0].Message.Content
	
	// 创建总结消息
	summaryMessage := &domain.Message{
		Role:        "system",
		Content:     fmt.Sprintf("[历史对话总结] %s", summary),
		ContentType: "text",
	}
	
	// 返回：总结 + 最近消息
	result := append([]*domain.Message{summaryMessage}, recentMessages...)
	
	return result, nil
}

// compressBySelection 通过选择重要消息压缩
func (s *ContextCompressionService) compressBySelection(
	messages []*domain.Message,
	targetTokens int,
) ([]*domain.Message, error) {
	// 计算每条消息的重要性分数
	scores := make([]float64, len(messages))
	
	for i, msg := range messages {
		scores[i] = s.calculateImportance(msg, i, len(messages))
	}
	
	// 贪心选择：从高分到低分选择，直到达到 token 限制
	selected := make([]*domain.Message, 0)
	currentTokens := 0
	
	// 按分数排序索引
	indices := s.sortIndicesByScore(scores)
	
	for _, idx := range indices {
		msgTokens := s.estimateTokens([]*domain.Message{messages[idx]})
		
		if currentTokens+msgTokens <= targetTokens {
			selected = append(selected, messages[idx])
			currentTokens += msgTokens
		}
	}
	
	// 按原始顺序排序
	s.sortMessagesByTime(selected)
	
	return selected, nil
}

// compressBySlidingWindow 滑动窗口压缩
func (s *ContextCompressionService) compressBySlidingWindow(
	messages []*domain.Message,
	targetTokens int,
) ([]*domain.Message, error) {
	// 从最新消息开始，保留固定窗口大小
	result := make([]*domain.Message, 0)
	currentTokens := 0
	
	// 从后往前遍历
	for i := len(messages) - 1; i >= 0; i-- {
		msgTokens := s.estimateTokens([]*domain.Message{messages[i]})
		
		if currentTokens+msgTokens > targetTokens {
			break
		}
		
		result = append([]*domain.Message{messages[i]}, result...)
		currentTokens += msgTokens
	}
	
	return result, nil
}

// calculateImportance 计算消息重要性
func (s *ContextCompressionService) calculateImportance(
	msg *domain.Message,
	index int,
	total int,
) float64 {
	score := 0.0
	
	// 1. 位置因素（越新越重要）
	positionScore := float64(index) / float64(total)
	score += positionScore * 0.3
	
	// 2. 长度因素（更长可能更重要）
	lengthScore := float64(len(msg.Content)) / 1000.0
	if lengthScore > 1.0 {
		lengthScore = 1.0
	}
	score += lengthScore * 0.2
	
	// 3. 角色因素
	if msg.Role == "assistant" {
		score += 0.3 // AI 回复更重要
	} else if msg.Role == "system" {
		score += 0.5 // 系统消息最重要
	}
	
	// 4. 关键词因素
	keywords := []string{"重要", "关键", "必须", "注意", "决定", "结论"}
	for _, kw := range keywords {
		if strings.Contains(msg.Content, kw) {
			score += 0.1
		}
	}
	
	return score
}

// estimateTokens 估算 token 数量
func (s *ContextCompressionService) estimateTokens(messages []*domain.Message) int {
	// 简单估算：中文 1 字约 1.5 tokens，英文 1 词约 1.3 tokens
	// 这里简化为：字符数 / 2
	total := 0
	for _, msg := range messages {
		total += len(msg.Content) / 2
	}
	return total
}

// determineStrategy 确定压缩策略
func (s *ContextCompressionService) determineStrategy(
	messages []*domain.Message,
	currentTokens int,
	targetTokens int,
) string {
	ratio := float64(targetTokens) / float64(currentTokens)
	
	if ratio > 0.7 {
		// 只需轻微压缩，使用滑动窗口
		return "sliding_window"
	} else if ratio > 0.4 {
		// 中等压缩，选择重要消息
		return "selective"
	} else {
		// 大幅压缩，使用总结
		return "summary"
	}
}

func (s *ContextCompressionService) messagesToText(messages []*domain.Message) string {
	var sb strings.Builder
	for _, msg := range messages {
		sb.WriteString(fmt.Sprintf("%s: %s\n", msg.Role, msg.Content))
	}
	return sb.String()
}

func (s *ContextCompressionService) sortIndicesByScore(scores []float64) []int {
	indices := make([]int, len(scores))
	for i := range indices {
		indices[i] = i
	}
	
	// 简单冒泡排序
	for i := 0; i < len(indices)-1; i++ {
		for j := i + 1; j < len(indices); j++ {
			if scores[indices[j]] > scores[indices[i]] {
				indices[i], indices[j] = indices[j], indices[i]
			}
		}
	}
	
	return indices
}

func (s *ContextCompressionService) sortMessagesByTime(messages []*domain.Message) {
	// 按创建时间排序
	for i := 0; i < len(messages)-1; i++ {
		for j := i + 1; j < len(messages); j++ {
			if messages[j].CreatedAt.Before(messages[i].CreatedAt) {
				messages[i], messages[j] = messages[j], messages[i]
			}
		}
	}
}
```

**验收标准**:
- [ ] 总结压缩实现
- [ ] 选择性压缩实现
- [ ] 滑动窗口实现
- [ ] 压缩率达标

#### 2. 分类和标签管理
**当前状态**: 已创建文件，需完善

**位置**: `cmd/conversation-service/internal/biz/category_usecase.go`, `tag_usecase.go`

**待实现**:

```go
// 文件: cmd/conversation-service/internal/biz/category_usecase.go

// CreateCategory 创建分类
func (uc *CategoryUsecase) CreateCategory(ctx context.Context, req *CreateCategoryRequest) (*Category, error) {
	category := &domain.Category{
		TenantID:    req.TenantID,
		UserID:      req.UserID,
		Name:        req.Name,
		Description: req.Description,
		ParentID:    req.ParentID,
		Color:       req.Color,
		Icon:        req.Icon,
	}
	
	if err := uc.repo.CreateCategory(ctx, category); err != nil {
		return nil, err
	}
	
	return category, nil
}

// ListCategoriesWithStats 列出分类（带统计）
func (uc *CategoryUsecase) ListCategoriesWithStats(
	ctx context.Context,
	tenantID, userID string,
) ([]*CategoryWithStats, error) {
	categories, err := uc.repo.ListCategories(ctx, tenantID, userID)
	if err != nil {
		return nil, err
	}
	
	// 统计每个分类的对话数
	result := make([]*CategoryWithStats, len(categories))
	for i, cat := range categories {
		count, err := uc.repo.CountConversationsByCategory(ctx, cat.ID)
		if err != nil {
			return nil, err
		}
		
		result[i] = &CategoryWithStats{
			Category:          cat,
			ConversationCount: count,
		}
	}
	
	return result, nil
}

// MoveConversationToCategory 移动对话到分类
func (uc *CategoryUsecase) MoveConversationToCategory(
	ctx context.Context,
	conversationID string,
	categoryID string,
	userID string,
) error {
	// 权限检查
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return err
	}
	
	if conv.UserID != userID {
		return errors.New("permission denied")
	}
	
	// 更新分类
	conv.CategoryID = &categoryID
	return uc.convRepo.UpdateConversation(ctx, conv)
}
```

**标签管理**:
```go
// 文件: cmd/conversation-service/internal/biz/tag_usecase.go

// AddTagToConversation 为对话添加标签
func (uc *TagUsecase) AddTagToConversation(
	ctx context.Context,
	conversationID string,
	tagName string,
	userID string,
) error {
	// 检查权限
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return err
	}
	
	if conv.UserID != userID {
		return errors.New("permission denied")
	}
	
	// 查找或创建标签
	tag, err := uc.repo.GetTagByName(ctx, conv.TenantID, userID, tagName)
	if err != nil {
		// 创建新标签
		tag = &domain.Tag{
			TenantID: conv.TenantID,
			UserID:   userID,
			Name:     tagName,
			Color:    s.generateRandomColor(),
		}
		
		if err := uc.repo.CreateTag(ctx, tag); err != nil {
			return err
		}
	}
	
	// 关联标签和对话
	return uc.repo.AddConversationTag(ctx, conversationID, tag.ID)
}

// GetPopularTags 获取热门标签
func (uc *TagUsecase) GetPopularTags(
	ctx context.Context,
	tenantID, userID string,
	limit int,
) ([]*TagWithCount, error) {
	return uc.repo.GetPopularTags(ctx, tenantID, userID, limit)
}

// SearchConversationsByTags 按标签搜索对话
func (uc *TagUsecase) SearchConversationsByTags(
	ctx context.Context,
	tenantID, userID string,
	tagIDs []string,
	matchAll bool, // true: AND, false: OR
) ([]*domain.Conversation, error) {
	return uc.repo.SearchConversationsByTags(ctx, tenantID, userID, tagIDs, matchAll)
}
```

**验收标准**:
- [ ] 分类 CRUD 完成
- [ ] 标签 CRUD 完成
- [ ] 对话分类/标签关联
- [ ] 统计和搜索功能

#### 3. 导出功能
**当前状态**: 已创建文件，需完善

**位置**: `cmd/conversation-service/internal/biz/export_usecase.go`

**待实现**:

```go
// 文件: cmd/conversation-service/internal/biz/export_usecase.go

import (
	"archive/zip"
	"encoding/csv"
	"encoding/json"
	"fmt"
)

type ExportUsecase struct {
	convRepo domain.ConversationRepository
	msgRepo  domain.MessageRepository
}

// ExportToJSON 导出为 JSON
func (uc *ExportUsecase) ExportToJSON(
	ctx context.Context,
	conversationIDs []string,
	userID string,
) ([]byte, error) {
	// 获取对话和消息
	data := make([]*ExportData, 0)
	
	for _, convID := range conversationIDs {
		conv, err := uc.convRepo.GetConversation(ctx, convID)
		if err != nil {
			return nil, err
		}
		
		// 权限检查
		if conv.UserID != userID {
			continue
		}
		
		// 获取消息
		messages, err := uc.msgRepo.ListMessages(ctx, convID, 0, 10000)
		if err != nil {
			return nil, err
		}
		
		data = append(data, &ExportData{
			Conversation: conv,
			Messages:     messages,
		})
	}
	
	// 序列化为 JSON
	return json.MarshalIndent(data, "", "  ")
}

// ExportToMarkdown 导出为 Markdown
func (uc *ExportUsecase) ExportToMarkdown(
	ctx context.Context,
	conversationID string,
	userID string,
) (string, error) {
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return "", err
	}
	
	if conv.UserID != userID {
		return "", errors.New("permission denied")
	}
	
	messages, err := uc.msgRepo.ListMessages(ctx, conversationID, 0, 10000)
	if err != nil {
		return "", err
	}
	
	// 构建 Markdown
	var sb strings.Builder
	
	sb.WriteString(fmt.Sprintf("# %s\n\n", conv.Title))
	sb.WriteString(fmt.Sprintf("**创建时间**: %s\n\n", conv.CreatedAt.Format("2006-01-02 15:04:05")))
	sb.WriteString(fmt.Sprintf("**模式**: %s\n\n", conv.Mode))
	sb.WriteString("---\n\n")
	
	for _, msg := range messages {
		roleEmoji := map[string]string{
			"user":      "👤",
			"assistant": "🤖",
			"system":    "⚙️",
		}
		
		sb.WriteString(fmt.Sprintf("## %s %s\n\n", roleEmoji[msg.Role], msg.Role))
		sb.WriteString(fmt.Sprintf("%s\n\n", msg.Content))
		sb.WriteString(fmt.Sprintf("*%s*\n\n", msg.CreatedAt.Format("2006-01-02 15:04:05")))
		sb.WriteString("---\n\n")
	}
	
	return sb.String(), nil
}

// ExportToPDF 导出为 PDF
func (uc *ExportUsecase) ExportToPDF(
	ctx context.Context,
	conversationID string,
	userID string,
) ([]byte, error) {
	// 首先生成 Markdown
	markdown, err := uc.ExportToMarkdown(ctx, conversationID, userID)
	if err != nil {
		return nil, err
	}
	
	// TODO: 使用 wkhtmltopdf 或 pandoc 转换为 PDF
	// 这里返回 Markdown 的字节
	return []byte(markdown), nil
}

// ExportToCSV 导出为 CSV
func (uc *ExportUsecase) ExportToCSV(
	ctx context.Context,
	conversationIDs []string,
	userID string,
) ([]byte, error) {
	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)
	
	// 写入表头
	headers := []string{"Conversation ID", "Title", "Role", "Content", "Timestamp"}
	writer.Write(headers)
	
	// 写入数据
	for _, convID := range conversationIDs {
		conv, err := uc.convRepo.GetConversation(ctx, convID)
		if err != nil || conv.UserID != userID {
			continue
		}
		
		messages, err := uc.msgRepo.ListMessages(ctx, convID, 0, 10000)
		if err != nil {
			continue
		}
		
		for _, msg := range messages {
			row := []string{
				conv.ID,
				conv.Title,
				msg.Role,
				msg.Content,
				msg.CreatedAt.Format("2006-01-02 15:04:05"),
			}
			writer.Write(row)
		}
	}
	
	writer.Flush()
	return buf.Bytes(), nil
}
```

**验收标准**:
- [ ] JSON 导出完成
- [ ] Markdown 导出完成
- [ ] CSV 导出完成
- [ ] PDF 导出完成

---

### 🔄 P1 - 高级功能（迭代2：1周）

#### 1. 对话摘要生成

```go
// 文件: cmd/conversation-service/internal/biz/summary_service.go

type SummaryService struct {
	llmClient *openai.Client
}

// GenerateSummary 生成对话摘要
func (s *SummaryService) GenerateSummary(
	ctx context.Context,
	messages []*domain.Message,
) (string, error) {
	// 构建对话文本
	conversationText := s.messagesToText(messages)
	
	prompt := fmt.Sprintf(`
请为以下对话生成一个简洁的摘要（不超过100字）:

%s

摘要:`, conversationText)
	
	resp, err := s.llmClient.CreateChatCompletion(
		ctx,
		openai.ChatCompletionRequest{
			Model: openai.GPT3Dot5Turbo,
			Messages: []openai.ChatCompletionMessage{
				{Role: openai.ChatMessageRoleUser, Content: prompt},
			},
			MaxTokens:   150,
			Temperature: 0.5,
		},
	)
	
	if err != nil {
		return "", err
	}
	
	return resp.Choices[0].Message.Content, nil
}

// GenerateTitle 生成对话标题
func (s *SummaryService) GenerateTitle(
	ctx context.Context,
	firstMessage string,
) (string, error) {
	prompt := fmt.Sprintf(`
根据以下对话的第一条消息，生成一个简短的标题（不超过20字）:

消息: %s

标题:`, firstMessage)
	
	resp, err := s.llmClient.CreateChatCompletion(
		ctx,
		openai.ChatCompletionRequest{
			Model:       openai.GPT3Dot5Turbo,
			Messages:    []openai.ChatCompletionMessage{{Role: "user", Content: prompt}},
			MaxTokens:   30,
			Temperature: 0.7,
		},
	)
	
	if err != nil {
		return "", err
	}
	
	return strings.TrimSpace(resp.Choices[0].Message.Content), nil
}
```

**验收标准**:
- [ ] 自动生成摘要
- [ ] 自动生成标题
- [ ] 摘要质量好

#### 2. 对话搜索

```go
// 文件: cmd/conversation-service/internal/biz/search_service.go

type SearchService struct {
	esClient *elasticsearch.Client
}

// SearchConversations 全文搜索对话
func (s *SearchService) SearchConversations(
	ctx context.Context,
	tenantID, userID string,
	query string,
	filters map[string]interface{},
	limit, offset int,
) ([]*domain.Conversation, int64, error) {
	// 构建 ES 查询
	searchQuery := map[string]interface{}{
		"query": map[string]interface{}{
			"bool": map[string]interface{}{
				"must": []map[string]interface{}{
					{
						"match": map[string]interface{}{
							"content": query,
						},
					},
					{
						"term": map[string]interface{}{
							"tenant_id": tenantID,
						},
					},
					{
						"term": map[string]interface{}{
							"user_id": userID,
						},
					},
				},
			},
		},
		"from": offset,
		"size": limit,
		"highlight": map[string]interface{}{
			"fields": map[string]interface{}{
				"content": map[string]interface{}{},
			},
		},
	}
	
	// 执行搜索
	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("conversations"),
		s.esClient.Search.WithBody(strings.NewReader(jsonQuery)),
	)
	
	if err != nil {
		return nil, 0, err
	}
	
	// 解析结果
	// ...
	
	return conversations, total, nil
}
```

**验收标准**:
- [ ] 全文搜索实现
- [ ] 高亮显示
- [ ] 过滤和排序

---

## 三、实施方案

### 阶段1：核心功能（Week 1-2）

#### Day 1-7: 上下文压缩
1. 实现三种压缩策略
2. 测试压缩效果
3. 集成到对话流程

#### Day 8-10: 分类和标签
1. 分类管理
2. 标签管理
3. 搜索和统计

#### Day 11-14: 导出功能
1. 多格式导出
2. 批量导出
3. 测试

### 阶段2：高级功能（Week 3）

#### Day 15-17: 摘要和搜索
1. 对话摘要
2. 标题生成
3. 全文搜索

#### Day 18-21: 优化和测试
1. 性能优化
2. 集成测试
3. 文档

---

## 四、验收标准

### 功能验收
- [ ] 上下文压缩正常
- [ ] 分类标签完整
- [ ] 导出功能正常
- [ ] 摘要生成准确
- [ ] 搜索功能正常

### 性能验收
- [ ] API 响应 < 200ms
- [ ] 支持 100 并发
- [ ] 数据库查询优化

### 质量验收
- [ ] 单元测试覆盖率 > 70%
- [ ] 所有 TODO 清理
- [ ] API 文档完整

---

## 总结

Conversation Service 的主要待完成功能：

1. **上下文压缩**: 智能压缩对话历史
2. **分类标签**: 组织管理对话
3. **导出功能**: 多格式导出
4. **摘要生成**: 自动摘要和标题
5. **全文搜索**: ES 全文检索

完成后将提供完整的对话管理能力。


