package data

import (
	"time"

	"gorm.io/gorm"

	"voiceassistant/cmd/notification-service/internal/domain"
)

type templateRepo struct {
	db *gorm.DB
}

func NewTemplateRepository(db *gorm.DB) domain.TemplateRepository {
	return &templateRepo{db: db}
}

func (r *templateRepo) GetByName(tenantID, name string) (*domain.Template, error) {
	var template domain.Template
	err := r.db.Where("tenant_id = ? AND name = ? AND enabled = ?", tenantID, name, true).
		First(&template).Error
	if err != nil {
		return nil, err
	}
	return &template, nil
}

func (r *templateRepo) GetByID(id string) (*domain.Template, error) {
	var template domain.Template
	err := r.db.Where("id = ?", id).First(&template).Error
	if err != nil {
		return nil, err
	}
	return &template, nil
}

func (r *templateRepo) Create(template *domain.Template) error {
	template.CreatedAt = time.Now()
	template.UpdatedAt = time.Now()
	return r.db.Create(template).Error
}

func (r *templateRepo) Update(template *domain.Template) error {
	template.UpdatedAt = time.Now()
	return r.db.Save(template).Error
}

func (r *templateRepo) GetByTenantID(tenantID string) ([]*domain.Template, error) {
	var templates []*domain.Template
	err := r.db.Where("tenant_id = ?", tenantID).Find(&templates).Error
	return templates, err
}

func (r *templateRepo) Delete(id string) error {
	return r.db.Delete(&domain.Template{}, "id = ?", id).Error
}

func (r *templateRepo) List(tenantID string, notificationType *string, page, pageSize int) ([]*domain.Template, int64, error) {
	var templates []*domain.Template
	var total int64

	query := r.db.Model(&domain.Template{})

	if tenantID != "" {
		query = query.Where("tenant_id = ?", tenantID)
	}
	if notificationType != nil {
		query = query.Where("type = ?", *notificationType)
	}

	// Count total
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// Pagination
	offset := (page - 1) * pageSize
	if err := query.Offset(offset).Limit(pageSize).
		Order("updated_at DESC").
		Find(&templates).Error; err != nil {
		return nil, 0, err
	}

	return templates, total, nil
}
