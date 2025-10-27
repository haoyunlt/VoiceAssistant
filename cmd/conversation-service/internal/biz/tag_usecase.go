package biz

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// TagUsecase 标签用例
type TagUsecase struct {
	tagRepo domain.TagRepository
	convRepo domain.ConversationRepository
	log     *log.Helper
}

// NewTagUsecase 创建标签用例
func NewTagUsecase(
	tagRepo domain.TagRepository,
	convRepo domain.ConversationRepository,
	logger log.Logger,
) *TagUsecase {
	return &TagUsecase{
		tagRepo:  tagRepo,
		convRepo: convRepo,
		log:      log.NewHelper(logger),
	}
}

// CreateTag 创建标签
func (uc *TagUsecase) CreateTag(ctx context.Context, tenantID, name, color, description, createdBy string) (*domain.Tag, error) {
	// 检查标签名称是否已存在
	existing, err := uc.tagRepo.GetByName(ctx, tenantID, name)
	if err == nil && existing != nil {
		return nil, fmt.Errorf("标签名称已存在")
	}

	tag := &domain.Tag{
		ID:          generateTagID(),
		TenantID:    tenantID,
		Name:        name,
		Color:       color,
		Description: description,
		UsageCount:  0,
		CreatedBy:   createdBy,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	if err := uc.tagRepo.Create(ctx, tag); err != nil {
		return nil, fmt.Errorf("创建标签失败: %w", err)
	}

	return tag, nil
}

// UpdateTag 更新标签
func (uc *TagUsecase) UpdateTag(ctx context.Context, tagID, name, color, description string) error {
	tag, err := uc.tagRepo.GetByID(ctx, tagID)
	if err != nil {
		return fmt.Errorf("标签不存在: %w", err)
	}

	tag.Name = name
	tag.Color = color
	tag.Description = description
	tag.UpdatedAt = time.Now()

	if err := uc.tagRepo.Update(ctx, tag); err != nil {
		return fmt.Errorf("更新标签失败: %w", err)
	}

	return nil
}

// DeleteTag 删除标签
func (uc *TagUsecase) DeleteTag(ctx context.Context, tagID string) error {
	if err := uc.tagRepo.Delete(ctx, tagID); err != nil {
		return fmt.Errorf("删除标签失败: %w", err)
	}

	return nil
}

// ListTags 列出标签
func (uc *TagUsecase) ListTags(ctx context.Context, tenantID string, limit, offset int) ([]*domain.Tag, int, error) {
	tags, total, err := uc.tagRepo.ListByTenant(ctx, tenantID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("获取标签列表失败: %w", err)
	}

	return tags, total, nil
}

// AddTagToConversation 为对话添加标签
func (uc *TagUsecase) AddTagToConversation(ctx context.Context, conversationID, tagID, userID string) error {
	// 检查对话是否存在
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return fmt.Errorf("对话不存在: %w", err)
	}

	// 检查权限
	if conv.UserID != userID {
		return fmt.Errorf("无权操作该对话")
	}

	// 检查标签是否存在
	tag, err := uc.tagRepo.GetByID(ctx, tagID)
	if err != nil {
		return fmt.Errorf("标签不存在: %w", err)
	}

	// 添加标签关联
	if err := uc.tagRepo.AddTagToConversation(ctx, conversationID, tagID); err != nil {
		return fmt.Errorf("添加标签失败: %w", err)
	}

	// 更新标签使用次数
	tag.UsageCount++
	tag.UpdatedAt = time.Now()
	if err := uc.tagRepo.Update(ctx, tag); err != nil {
		uc.log.Warnf("更新标签使用次数失败: %v", err)
	}

	return nil
}

// RemoveTagFromConversation 从对话移除标签
func (uc *TagUsecase) RemoveTagFromConversation(ctx context.Context, conversationID, tagID, userID string) error {
	// 检查对话是否存在
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return fmt.Errorf("对话不存在: %w", err)
	}

	// 检查权限
	if conv.UserID != userID {
		return fmt.Errorf("无权操作该对话")
	}

	// 移除标签关联
	if err := uc.tagRepo.RemoveTagFromConversation(ctx, conversationID, tagID); err != nil {
		return fmt.Errorf("移除标签失败: %w", err)
	}

	// 更新标签使用次数
	tag, err := uc.tagRepo.GetByID(ctx, tagID)
	if err == nil {
		if tag.UsageCount > 0 {
			tag.UsageCount--
		}
		tag.UpdatedAt = time.Now()
		if err := uc.tagRepo.Update(ctx, tag); err != nil {
			uc.log.Warnf("更新标签使用次数失败: %v", err)
		}
	}

	return nil
}

// GetConversationTags 获取对话的所有标签
func (uc *TagUsecase) GetConversationTags(ctx context.Context, conversationID, userID string) ([]*domain.Tag, error) {
	// 检查对话是否存在
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, fmt.Errorf("对话不存在: %w", err)
	}

	// 检查权限
	if conv.UserID != userID {
		return nil, fmt.Errorf("无权访问该对话")
	}

	tags, err := uc.tagRepo.GetConversationTags(ctx, conversationID)
	if err != nil {
		return nil, fmt.Errorf("获取对话标签失败: %w", err)
	}

	return tags, nil
}

// GetConversationsByTag 根据标签获取对话列表
func (uc *TagUsecase) GetConversationsByTag(ctx context.Context, tagID, userID string, limit, offset int) ([]string, int, error) {
	// TODO: 添加权限检查，确保只返回用户有权访问的对话

	conversationIDs, total, err := uc.tagRepo.GetConversationsByTag(ctx, tagID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("获取标签对话列表失败: %w", err)
	}

	return conversationIDs, total, nil
}

// generateTagID 生成标签ID
func generateTagID() string {
	return "tag_" + time.Now().Format("20060102150405") + "_" + generateRandomStr(8)
}

// generateRandomStr 生成随机字符串
func generateRandomStr(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyz0123456789"
	b := make([]byte, length)
	for i := range b {
		b[i] = charset[time.Now().UnixNano()%int64(len(charset))]
	}
	return string(b)
}
