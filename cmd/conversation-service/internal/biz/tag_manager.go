package biz

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/conversation-service/internal/domain"
)

// TagManager 标签管理器
type TagManager struct {
	conversationRepo domain.ConversationRepository
	logger           *log.Helper
}

// ConversationTag 对话标签
type ConversationTag struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Color       string    `json:"color"`
	Description string    `json:"description"`
	Count       int       `json:"count"`        // 使用该标签的对话数
	CreatedAt   time.Time `json:"created_at"`
}

// ConversationCategory 对话分类
type ConversationCategory struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	ParentID    string    `json:"parent_id,omitempty"` // 父分类ID（支持层级）
	Description string    `json:"description"`
	Count       int       `json:"count"`        // 该分类的对话数
	Order       int       `json:"order"`        // 排序
	CreatedAt   time.Time `json:"created_at"`
}

// NewTagManager 创建标签管理器
func NewTagManager(
	conversationRepo domain.ConversationRepository,
	logger log.Logger,
) *TagManager {
	return &TagManager{
		conversationRepo: conversationRepo,
		logger:           log.NewHelper(log.With(logger, "module", "tag-manager")),
	}
}

// AddTags 添加标签到对话
func (tm *TagManager) AddTags(
	ctx context.Context,
	conversationID, userID string,
	tags []string,
) error {
	// 获取对话
	conversation, err := tm.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return err
	}

	// 权限检查
	if conversation.UserID != userID {
		return domain.ErrPermissionDenied
	}

	// 初始化标签列表
	if conversation.Metadata == nil {
		conversation.Metadata = make(map[string]string)
	}

	// 获取现有标签
	existingTags := tm.getTagsFromMetadata(conversation.Metadata)

	// 合并标签（去重）
	tagSet := make(map[string]bool)
	for _, tag := range existingTags {
		tagSet[strings.ToLower(strings.TrimSpace(tag))] = true
	}
	for _, tag := range tags {
		tag = strings.ToLower(strings.TrimSpace(tag))
		if tag != "" {
			tagSet[tag] = true
		}
	}

	// 转换回切片
	newTags := make([]string, 0, len(tagSet))
	for tag := range tagSet {
		newTags = append(newTags, tag)
	}

	// 保存标签
	conversation.Metadata["tags"] = strings.Join(newTags, ",")
	conversation.UpdatedAt = time.Now()

	// 更新数据库
	if err := tm.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return fmt.Errorf("failed to update conversation: %w", err)
	}

	tm.logger.Infof("Tags added: conversation=%s, tags=%v", conversationID, newTags)

	return nil
}

// RemoveTags 从对话移除标签
func (tm *TagManager) RemoveTags(
	ctx context.Context,
	conversationID, userID string,
	tags []string,
) error {
	// 获取对话
	conversation, err := tm.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return err
	}

	// 权限检查
	if conversation.UserID != userID {
		return domain.ErrPermissionDenied
	}

	// 获取现有标签
	existingTags := tm.getTagsFromMetadata(conversation.Metadata)

	// 创建移除集合
	toRemove := make(map[string]bool)
	for _, tag := range tags {
		toRemove[strings.ToLower(strings.TrimSpace(tag))] = true
	}

	// 过滤标签
	newTags := make([]string, 0)
	for _, tag := range existingTags {
		if !toRemove[strings.ToLower(strings.TrimSpace(tag))] {
			newTags = append(newTags, tag)
		}
	}

	// 保存标签
	conversation.Metadata["tags"] = strings.Join(newTags, ",")
	conversation.UpdatedAt = time.Now()

	// 更新数据库
	if err := tm.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return fmt.Errorf("failed to update conversation: %w", err)
	}

	tm.logger.Infof("Tags removed: conversation=%s, remaining_tags=%v", conversationID, newTags)

	return nil
}

// SetCategory 设置对话分类
func (tm *TagManager) SetCategory(
	ctx context.Context,
	conversationID, userID string,
	categoryID string,
) error {
	// 获取对话
	conversation, err := tm.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return err
	}

	// 权限检查
	if conversation.UserID != userID {
		return domain.ErrPermissionDenied
	}

	// 设置分类
	if conversation.Metadata == nil {
		conversation.Metadata = make(map[string]string)
	}

	conversation.Metadata["category_id"] = categoryID
	conversation.UpdatedAt = time.Now()

	// 更新数据库
	if err := tm.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return fmt.Errorf("failed to update conversation: %w", err)
	}

	tm.logger.Infof("Category set: conversation=%s, category=%s", conversationID, categoryID)

	return nil
}

// GetTags 获取对话标签
func (tm *TagManager) GetTags(
	ctx context.Context,
	conversationID, userID string,
) ([]string, error) {
	// 获取对话
	conversation, err := tm.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	// 权限检查
	if conversation.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	return tm.getTagsFromMetadata(conversation.Metadata), nil
}

// GetCategory 获取对话分类
func (tm *TagManager) GetCategory(
	ctx context.Context,
	conversationID, userID string,
) (string, error) {
	// 获取对话
	conversation, err := tm.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return "", err
	}

	// 权限检查
	if conversation.UserID != userID {
		return "", domain.ErrPermissionDenied
	}

	if conversation.Metadata == nil {
		return "", nil
	}

	return conversation.Metadata["category_id"], nil
}

// GetPopularTags 获取热门标签
func (tm *TagManager) GetPopularTags(
	ctx context.Context,
	tenantID, userID string,
	limit int,
) ([]*ConversationTag, error) {
	// 获取用户的所有对话
	conversations, _, err := tm.conversationRepo.ListConversations(ctx, tenantID, userID, 1000, 0)
	if err != nil {
		return nil, err
	}

	// 统计标签使用频率
	tagCount := make(map[string]int)
	for _, conv := range conversations {
		tags := tm.getTagsFromMetadata(conv.Metadata)
		for _, tag := range tags {
			tagCount[tag]++
		}
	}

	// 转换为切片并排序
	tags := make([]*ConversationTag, 0, len(tagCount))
	for name, count := range tagCount {
		tags = append(tags, &ConversationTag{
			ID:    generateTagID(name),
			Name:  name,
			Count: count,
			Color: generateTagColor(name),
		})
	}

	// 按使用次数排序
	for i := 0; i < len(tags)-1; i++ {
		for j := i + 1; j < len(tags); j++ {
			if tags[j].Count > tags[i].Count {
				tags[i], tags[j] = tags[j], tags[i]
			}
		}
	}

	// 限制数量
	if len(tags) > limit {
		tags = tags[:limit]
	}

	return tags, nil
}

// SearchByTags 按标签搜索对话
func (tm *TagManager) SearchByTags(
	ctx context.Context,
	tenantID, userID string,
	tags []string,
	limit, offset int,
) ([]*domain.Conversation, int, error) {
	// 获取用户的所有对话
	conversations, total, err := tm.conversationRepo.ListConversations(ctx, tenantID, userID, 10000, 0)
	if err != nil {
		return nil, 0, err
	}

	// 创建标签集合（小写）
	searchTags := make(map[string]bool)
	for _, tag := range tags {
		searchTags[strings.ToLower(strings.TrimSpace(tag))] = true
	}

	// 过滤对话
	filtered := make([]*domain.Conversation, 0)
	for _, conv := range conversations {
		convTags := tm.getTagsFromMetadata(conv.Metadata)
		
		// 检查是否包含任意一个搜索标签
		hasTag := false
		for _, convTag := range convTags {
			if searchTags[strings.ToLower(convTag)] {
				hasTag = true
				break
			}
		}

		if hasTag {
			filtered = append(filtered, conv)
		}
	}

	// 分页
	start := offset
	end := offset + limit
	if start > len(filtered) {
		return []*domain.Conversation{}, len(filtered), nil
	}
	if end > len(filtered) {
		end = len(filtered)
	}

	return filtered[start:end], len(filtered), nil
}

// getTagsFromMetadata 从元数据中获取标签
func (tm *TagManager) getTagsFromMetadata(metadata map[string]string) []string {
	if metadata == nil {
		return []string{}
	}

	tagsStr := metadata["tags"]
	if tagsStr == "" {
		return []string{}
	}

	tags := strings.Split(tagsStr, ",")
	result := make([]string, 0, len(tags))
	for _, tag := range tags {
		tag = strings.TrimSpace(tag)
		if tag != "" {
			result = append(result, tag)
		}
	}

	return result
}

// generateTagID 生成标签 ID
func generateTagID(name string) string {
	return fmt.Sprintf("tag_%s", strings.ReplaceAll(strings.ToLower(name), " ", "_"))
}

// generateTagColor 生成标签颜色（基于标签名）
func generateTagColor(name string) string {
	colors := []string{
		"#3B82F6", // blue
		"#10B981", // green
		"#F59E0B", // yellow
		"#EF4444", // red
		"#8B5CF6", // purple
		"#EC4899", // pink
		"#14B8A6", // teal
		"#F97316", // orange
	}

	// 简单哈希
	hash := 0
	for _, c := range name {
		hash += int(c)
	}

	return colors[hash%len(colors)]
}

