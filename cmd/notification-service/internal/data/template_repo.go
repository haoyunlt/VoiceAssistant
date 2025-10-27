package data

import (
	"context"
	"time"
	"voiceassistant/cmd/notification-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

type templateRepo struct {
	db  *gorm.DB
	log *log.Helper
}

// NewTemplateRepository creates a new template repository
func NewTemplateRepository(data *Data, logger log.Logger) domain.TemplateRepository {
	return &templateRepo{
		db:  data.db,
		log: log.NewHelper(logger),
	}
}

// Create creates a new template
func (r *templateRepo) Create(ctx context.Context, template *domain.Template) error {
	template.CreatedAt = time.Now()
	template.UpdatedAt = time.Now()

	if err := r.db.WithContext(ctx).Create(template).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to create template: %v", err)
		return err
	}
	return nil
}

// Update updates a template
func (r *templateRepo) Update(ctx context.Context, template *domain.Template) error {
	template.UpdatedAt = time.Now()

	if err := r.db.WithContext(ctx).Save(template).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to update template: %v", err)
		return err
	}
	return nil
}

// GetByID gets a template by ID
func (r *templateRepo) GetByID(ctx context.Context, id string) (*domain.Template, error) {
	var template domain.Template

	err := r.db.WithContext(ctx).Where("id = ?", id).First(&template).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		r.log.WithContext(ctx).Errorf("failed to get template by ID: %v", err)
		return nil, err
	}
	return &template, nil
}

// GetByTenantID gets templates by tenant ID
func (r *templateRepo) GetByTenantID(ctx context.Context, tenantID string) ([]*domain.Template, error) {
	var templates []*domain.Template

	err := r.db.WithContext(ctx).
		Where("tenant_id = ?", tenantID).
		Order("updated_at DESC").
		Find(&templates).Error
	if err != nil {
		r.log.WithContext(ctx).Errorf("failed to get templates by tenant ID: %v", err)
		return nil, err
	}
	return templates, nil
}

// ListByTenant lists templates by tenant with pagination
func (r *templateRepo) ListByTenant(
	ctx context.Context,
	tenantID string,
	offset, limit int,
) ([]*domain.Template, int64, error) {
	var templates []*domain.Template
	var total int64

	query := r.db.WithContext(ctx).Model(&domain.Template{}).
		Where("tenant_id = ?", tenantID)

	// Count total
	if err := query.Count(&total).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to count templates: %v", err)
		return nil, 0, err
	}

	// Pagination
	if err := query.
		Offset(offset).
		Limit(limit).
		Order("updated_at DESC").
		Find(&templates).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to list templates: %v", err)
		return nil, 0, err
	}

	return templates, total, nil
}

// Delete deletes a template
func (r *templateRepo) Delete(ctx context.Context, id string) error {
	err := r.db.WithContext(ctx).Delete(&domain.Template{}, "id = ?", id).Error
	if err != nil {
		r.log.WithContext(ctx).Errorf("failed to delete template: %v", err)
		return err
	}
	return nil
}
