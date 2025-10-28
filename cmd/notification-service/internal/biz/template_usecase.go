package biz

import (
	"context"

	"voicehelper/cmd/notification-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// TemplateUsecase 模板用例
type TemplateUsecase struct {
	repo domain.TemplateRepository
	log  *log.Helper
}

// NewTemplateUsecase 创建模板用例
func NewTemplateUsecase(
	repo domain.TemplateRepository,
	logger log.Logger,
) *TemplateUsecase {
	return &TemplateUsecase{
		repo: repo,
		log:  log.NewHelper(logger),
	}
}

// CreateTemplate 创建模板
func (uc *TemplateUsecase) CreateTemplate(
	ctx context.Context,
	name string,
	templateType domain.TemplateType,
	tenantID string,
	subject, content string,
) (*domain.Template, error) {
	template := domain.NewTemplate(name, templateType, tenantID, subject, content)

	if err := template.Validate(); err != nil {
		return nil, err
	}

	if err := uc.repo.Create(ctx, template); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create template: %v", err)
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("created template: %s", template.ID)
	return template, nil
}

// GetTemplate 获取模板
func (uc *TemplateUsecase) GetTemplate(ctx context.Context, id string) (*domain.Template, error) {
	return uc.repo.GetByID(ctx, id)
}

// UpdateTemplate 更新模板
func (uc *TemplateUsecase) UpdateTemplate(
	ctx context.Context,
	id, subject, content, description string,
) (*domain.Template, error) {
	template, err := uc.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	template.Update(subject, content, description)

	if err := uc.repo.Update(ctx, template); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update template: %v", err)
		return nil, err
	}

	return template, nil
}

// DeleteTemplate 删除模板
func (uc *TemplateUsecase) DeleteTemplate(ctx context.Context, id string) error {
	return uc.repo.Delete(ctx, id)
}

// ListTemplates 列出租户模板
func (uc *TemplateUsecase) ListTemplates(
	ctx context.Context,
	tenantID string,
	offset, limit int,
) ([]*domain.Template, int64, error) {
	return uc.repo.ListByTenant(ctx, tenantID, offset, limit)
}
