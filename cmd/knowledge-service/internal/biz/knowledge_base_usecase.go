package biz

import (
	"context"
	"fmt"

	"voiceassistant/cmd/knowledge-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// KnowledgeBaseUsecase 知识库用例
type KnowledgeBaseUsecase struct {
	kbRepo  domain.KnowledgeBaseRepository
	docRepo domain.DocumentRepository
	log     *log.Helper
}

// NewKnowledgeBaseUsecase 创建知识库用例
func NewKnowledgeBaseUsecase(
	kbRepo domain.KnowledgeBaseRepository,
	docRepo domain.DocumentRepository,
	logger log.Logger,
) *KnowledgeBaseUsecase {
	return &KnowledgeBaseUsecase{
		kbRepo:  kbRepo,
		docRepo: docRepo,
		log:     log.NewHelper(logger),
	}
}

// CreateKnowledgeBase 创建知识库
func (uc *KnowledgeBaseUsecase) CreateKnowledgeBase(
	ctx context.Context,
	name, description string,
	kbType domain.KnowledgeBaseType,
	tenantID, createdBy string,
	embeddingModel domain.EmbeddingModel,
) (*domain.KnowledgeBase, error) {
	// 创建知识库
	kb := domain.NewKnowledgeBase(
		name,
		description,
		kbType,
		tenantID,
		createdBy,
		embeddingModel,
	)

	// 验证
	if err := kb.Validate(); err != nil {
		uc.log.WithContext(ctx).Errorf("invalid knowledge base: %v", err)
		return nil, err
	}

	// 持久化
	if err := uc.kbRepo.Create(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create knowledge base: %v", err)
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("created knowledge base: %s, name: %s", kb.ID, kb.Name)
	return kb, nil
}

// GetKnowledgeBase 获取知识库
func (uc *KnowledgeBaseUsecase) GetKnowledgeBase(ctx context.Context, id string) (*domain.KnowledgeBase, error) {
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get knowledge base %s: %v", id, err)
		return nil, err
	}
	return kb, nil
}

// UpdateKnowledgeBase 更新知识库
func (uc *KnowledgeBaseUsecase) UpdateKnowledgeBase(
	ctx context.Context,
	id, name, description string,
) (*domain.KnowledgeBase, error) {
	// 获取知识库
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	// 检查是否可以修改
	if !kb.CanModify() {
		return nil, domain.ErrKnowledgeBaseArchived
	}

	// 更新
	kb.Update(name, description)

	// 持久化
	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update knowledge base: %v", err)
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("updated knowledge base: %s", kb.ID)
	return kb, nil
}

// DeleteKnowledgeBase 删除知识库
func (uc *KnowledgeBaseUsecase) DeleteKnowledgeBase(ctx context.Context, id string) error {
	// 获取知识库
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	// 检查是否有文档
	docCount, err := uc.docRepo.CountByKnowledgeBase(ctx, id)
	if err != nil {
		return err
	}
	if docCount > 0 {
		return fmt.Errorf("cannot delete knowledge base with documents")
	}

	// 删除
	if err := uc.kbRepo.Delete(ctx, id); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to delete knowledge base: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("deleted knowledge base: %s", kb.ID)
	return nil
}

// ListKnowledgeBases 列出租户的知识库
func (uc *KnowledgeBaseUsecase) ListKnowledgeBases(
	ctx context.Context,
	tenantID string,
	offset, limit int,
) ([]*domain.KnowledgeBase, int64, error) {
	kbs, total, err := uc.kbRepo.ListByTenant(ctx, tenantID, offset, limit)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to list knowledge bases: %v", err)
		return nil, 0, err
	}
	return kbs, total, nil
}

// ActivateKnowledgeBase 激活知识库
func (uc *KnowledgeBaseUsecase) ActivateKnowledgeBase(ctx context.Context, id string) error {
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	kb.Activate()

	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to activate knowledge base: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("activated knowledge base: %s", kb.ID)
	return nil
}

// DeactivateKnowledgeBase 停用知识库
func (uc *KnowledgeBaseUsecase) DeactivateKnowledgeBase(ctx context.Context, id string) error {
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	kb.Deactivate()

	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to deactivate knowledge base: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("deactivated knowledge base: %s", kb.ID)
	return nil
}

// ArchiveKnowledgeBase 归档知识库
func (uc *KnowledgeBaseUsecase) ArchiveKnowledgeBase(ctx context.Context, id string) error {
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	kb.Archive()

	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to archive knowledge base: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("archived knowledge base: %s", kb.ID)
	return nil
}

// UpdateChunkConfig 更新分块配置
func (uc *KnowledgeBaseUsecase) UpdateChunkConfig(
	ctx context.Context,
	id string,
	chunkSize, chunkOverlap int,
) error {
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	if err := kb.SetChunkConfig(chunkSize, chunkOverlap); err != nil {
		return err
	}

	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update chunk config: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("updated chunk config for knowledge base: %s", kb.ID)
	return nil
}

// UpdateSettings 更新设置
func (uc *KnowledgeBaseUsecase) UpdateSettings(
	ctx context.Context,
	id string,
	settings map[string]interface{},
) error {
	kb, err := uc.kbRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	kb.UpdateSettings(settings)

	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update settings: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("updated settings for knowledge base: %s", kb.ID)
	return nil
}
