package biz

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// CategoryUsecase 分类用例
type CategoryUsecase struct {
	categoryRepo domain.CategoryRepository
	convRepo     domain.ConversationRepository
	log          *log.Helper
}

// NewCategoryUsecase 创建分类用例
func NewCategoryUsecase(
	categoryRepo domain.CategoryRepository,
	convRepo domain.ConversationRepository,
	logger log.Logger,
) *CategoryUsecase {
	return &CategoryUsecase{
		categoryRepo: categoryRepo,
		convRepo:     convRepo,
		log:          log.NewHelper(logger),
	}
}

// CreateCategory 创建分类
func (uc *CategoryUsecase) CreateCategory(ctx context.Context, tenantID, name, description string, parentID *string, sort int, createdBy string) (*domain.Category, error) {
	level := 1
	
	// 如果有父分类，计算层级
	if parentID != nil {
		parent, err := uc.categoryRepo.GetByID(ctx, *parentID)
		if err != nil {
			return nil, fmt.Errorf("父分类不存在: %w", err)
		}
		level = parent.Level + 1
		
		// 限制层级深度
		if level > 3 {
			return nil, fmt.Errorf("分类层级不能超过3层")
		}
	}

	category := &domain.Category{
		ID:          generateCategoryID(),
		TenantID:    tenantID,
		Name:        name,
		Description: description,
		ParentID:    parentID,
		Level:       level,
		Sort:        sort,
		CreatedBy:   createdBy,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	if err := uc.categoryRepo.Create(ctx, category); err != nil {
		return nil, fmt.Errorf("创建分类失败: %w", err)
	}

	return category, nil
}

// UpdateCategory 更新分类
func (uc *CategoryUsecase) UpdateCategory(ctx context.Context, categoryID, name, description string, sort int) error {
	category, err := uc.categoryRepo.GetByID(ctx, categoryID)
	if err != nil {
		return fmt.Errorf("分类不存在: %w", err)
	}

	category.Name = name
	category.Description = description
	category.Sort = sort
	category.UpdatedAt = time.Now()

	if err := uc.categoryRepo.Update(ctx, category); err != nil {
		return fmt.Errorf("更新分类失败: %w", err)
	}

	return nil
}

// DeleteCategory 删除分类
func (uc *CategoryUsecase) DeleteCategory(ctx context.Context, categoryID string) error {
	// 检查是否有子分类
	children, err := uc.categoryRepo.ListByTenant(ctx, "", &categoryID)
	if err != nil {
		return fmt.Errorf("检查子分类失败: %w", err)
	}

	if len(children) > 0 {
		return fmt.Errorf("无法删除含有子分类的分类")
	}

	// 检查是否有对话使用该分类
	conversations, _, err := uc.categoryRepo.GetConversationsByCategory(ctx, categoryID, 1, 0)
	if err != nil {
		return fmt.Errorf("检查对话失败: %w", err)
	}

	if len(conversations) > 0 {
		return fmt.Errorf("无法删除已被使用的分类")
	}

	if err := uc.categoryRepo.Delete(ctx, categoryID); err != nil {
		return fmt.Errorf("删除分类失败: %w", err)
	}

	return nil
}

// ListCategories 列出分类（树形结构）
func (uc *CategoryUsecase) ListCategories(ctx context.Context, tenantID string, parentID *string) ([]*domain.Category, error) {
	categories, err := uc.categoryRepo.ListByTenant(ctx, tenantID, parentID)
	if err != nil {
		return nil, fmt.Errorf("获取分类列表失败: %w", err)
	}

	return categories, nil
}

// ListAllCategories 列出所有分类（扁平列表）
func (uc *CategoryUsecase) ListAllCategories(ctx context.Context, tenantID string) ([]*domain.Category, error) {
	categories, err := uc.categoryRepo.ListAll(ctx, tenantID)
	if err != nil {
		return nil, fmt.Errorf("获取所有分类失败: %w", err)
	}

	return categories, nil
}

// SetConversationCategory 设置对话分类
func (uc *CategoryUsecase) SetConversationCategory(ctx context.Context, conversationID, categoryID, userID string) error {
	// 检查对话是否存在
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return fmt.Errorf("对话不存在: %w", err)
	}

	// 检查权限
	if conv.UserID != userID {
		return fmt.Errorf("无权操作该对话")
	}

	// 检查分类是否存在
	_, err = uc.categoryRepo.GetByID(ctx, categoryID)
	if err != nil {
		return fmt.Errorf("分类不存在: %w", err)
	}

	// 设置分类关联
	if err := uc.categoryRepo.SetConversationCategory(ctx, conversationID, categoryID); err != nil {
		return fmt.Errorf("设置对话分类失败: %w", err)
	}

	return nil
}

// RemoveConversationCategory 移除对话分类
func (uc *CategoryUsecase) RemoveConversationCategory(ctx context.Context, conversationID, userID string) error {
	// 检查对话是否存在
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return fmt.Errorf("对话不存在: %w", err)
	}

	// 检查权限
	if conv.UserID != userID {
		return fmt.Errorf("无权操作该对话")
	}

	// 移除分类关联
	if err := uc.categoryRepo.RemoveConversationCategory(ctx, conversationID); err != nil {
		return fmt.Errorf("移除对话分类失败: %w", err)
	}

	return nil
}

// GetConversationCategory 获取对话分类
func (uc *CategoryUsecase) GetConversationCategory(ctx context.Context, conversationID, userID string) (*domain.Category, error) {
	// 检查对话是否存在
	conv, err := uc.convRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, fmt.Errorf("对话不存在: %w", err)
	}

	// 检查权限
	if conv.UserID != userID {
		return nil, fmt.Errorf("无权访问该对话")
	}

	category, err := uc.categoryRepo.GetConversationCategory(ctx, conversationID)
	if err != nil {
		return nil, fmt.Errorf("获取对话分类失败: %w", err)
	}

	return category, nil
}

// GetConversationsByCategory 根据分类获取对话列表
func (uc *CategoryUsecase) GetConversationsByCategory(ctx context.Context, categoryID, userID string, limit, offset int) ([]string, int, error) {
	// TODO: 添加权限检查，确保只返回用户有权访问的对话

	conversationIDs, total, err := uc.categoryRepo.GetConversationsByCategory(ctx, categoryID, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("获取分类对话列表失败: %w", err)
	}

	return conversationIDs, total, nil
}

// generateCategoryID 生成分类ID
func generateCategoryID() string {
	return "cat_" + time.Now().Format("20060102150405") + "_" + generateRandomStr(8)
}
