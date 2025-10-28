package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/identity-service/internal/domain"
	"gorm.io/gorm"
)

// TenantModel is the tenant database model.
type TenantModel struct {
	ID          string    `gorm:"primaryKey;type:varchar(64)"`
	Name        string    `gorm:"uniqueIndex;type:varchar(255);not null"`
	DisplayName string    `gorm:"type:varchar(255);not null"`
	Plan        string    `gorm:"type:varchar(32);not null"`
	Status      string    `gorm:"type:varchar(32);not null"`
	MaxUsers    int       `gorm:"not null"`
	Settings    string    `gorm:"type:jsonb"`
	CreatedAt   time.Time `gorm:"not null"`
	UpdatedAt   time.Time `gorm:"not null"`
	ExpiresAt   *time.Time
	DeletedAt   gorm.DeletedAt `gorm:"index"`
}

// TableName returns the table name for TenantModel.
func (TenantModel) TableName() string {
	return "identity.tenants"
}

// ToEntity converts TenantModel to domain.Tenant
func (m *TenantModel) ToEntity() (*domain.Tenant, error) {
	var settings map[string]interface{}
	if m.Settings != "" {
		if err := json.Unmarshal([]byte(m.Settings), &settings); err != nil {
			return nil, err
		}
	}

	return &domain.Tenant{
		ID:          m.ID,
		Name:        m.Name,
		DisplayName: m.DisplayName,
		Plan:        domain.TenantPlan(m.Plan),
		Status:      domain.TenantStatus(m.Status),
		MaxUsers:    m.MaxUsers,
		Settings:    settings,
		CreatedAt:   m.CreatedAt,
		UpdatedAt:   m.UpdatedAt,
		ExpiresAt:   m.ExpiresAt,
	}, nil
}

// FromTenantEntity converts domain.Tenant to TenantModel
func FromTenantEntity(tenant *domain.Tenant) (*TenantModel, error) {
	settingsJSON, err := json.Marshal(tenant.Settings)
	if err != nil {
		return nil, err
	}

	return &TenantModel{
		ID:          tenant.ID,
		Name:        tenant.Name,
		DisplayName: tenant.DisplayName,
		Plan:        string(tenant.Plan),
		Status:      string(tenant.Status),
		MaxUsers:    tenant.MaxUsers,
		Settings:    string(settingsJSON),
		CreatedAt:   tenant.CreatedAt,
		UpdatedAt:   tenant.UpdatedAt,
		ExpiresAt:   tenant.ExpiresAt,
	}, nil
}

// tenantRepo is the tenant repository implementation.
type tenantRepo struct {
	data *Data
	log  *log.Helper
}

// NewTenantRepo creates a new tenant repository.
func NewTenantRepo(data *Data, logger log.Logger) domain.TenantRepository {
	return &tenantRepo{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create implements domain.TenantRepository
func (r *tenantRepo) Create(ctx context.Context, tenant *domain.Tenant) error {
	model, err := FromTenantEntity(tenant)
	if err != nil {
		return err
	}

	return r.data.db.WithContext(ctx).Create(model).Error
}

// GetByID implements domain.TenantRepository
func (r *tenantRepo) GetByID(ctx context.Context, id string) (*domain.Tenant, error) {
	var model TenantModel
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&model).Error; err != nil {
		return nil, err
	}

	return model.ToEntity()
}

// GetByName implements domain.TenantRepository
func (r *tenantRepo) GetByName(ctx context.Context, name string) (*domain.Tenant, error) {
	var model TenantModel
	if err := r.data.db.WithContext(ctx).Where("name = ?", name).First(&model).Error; err != nil {
		return nil, err
	}

	return model.ToEntity()
}

// List implements domain.TenantRepository
func (r *tenantRepo) List(ctx context.Context, offset, limit int) ([]*domain.Tenant, error) {
	var models []TenantModel
	if err := r.data.db.WithContext(ctx).
		Offset(offset).
		Limit(limit).
		Find(&models).Error; err != nil {
		return nil, err
	}

	tenants := make([]*domain.Tenant, 0, len(models))
	for _, model := range models {
		tenant, err := model.ToEntity()
		if err != nil {
			return nil, err
		}
		tenants = append(tenants, tenant)
	}

	return tenants, nil
}

// Update implements domain.TenantRepository
func (r *tenantRepo) Update(ctx context.Context, tenant *domain.Tenant) error {
	model, err := FromTenantEntity(tenant)
	if err != nil {
		return err
	}

	return r.data.db.WithContext(ctx).Save(model).Error
}

// Delete implements domain.TenantRepository (soft delete)
func (r *tenantRepo) Delete(ctx context.Context, id string) error {
	return r.data.db.WithContext(ctx).Delete(&TenantModel{}, "id = ?", id).Error
}
