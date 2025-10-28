package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/identity-service/internal/domain"
	"gorm.io/gorm"
)

// UserModel is the user database model.
type UserModel struct {
	ID           string    `gorm:"primaryKey;type:varchar(64)"`
	Email        string    `gorm:"uniqueIndex;type:varchar(255);not null"`
	Username     string    `gorm:"type:varchar(255);not null"`
	DisplayName  string    `gorm:"type:varchar(255)"`
	AvatarURL    string    `gorm:"type:text"`
	PasswordHash string    `gorm:"type:varchar(255);not null"`
	TenantID     string    `gorm:"index;type:varchar(64);not null"`
	Roles        string    `gorm:"type:text"` // JSON array
	Status       string    `gorm:"type:varchar(32);not null"`
	CreatedAt    time.Time `gorm:"not null"`
	UpdatedAt    time.Time `gorm:"not null"`
	LastLoginAt  *time.Time
	DeletedAt    gorm.DeletedAt `gorm:"index"`
}

// TableName returns the table name for UserModel.
func (UserModel) TableName() string {
	return "identity.users"
}

// ToEntity converts UserModel to domain.User
func (m *UserModel) ToEntity() (*domain.User, error) {
	var roles []string
	if m.Roles != "" {
		if err := json.Unmarshal([]byte(m.Roles), &roles); err != nil {
			return nil, err
		}
	}

	return &domain.User{
		ID:           m.ID,
		Email:        m.Email,
		Username:     m.Username,
		DisplayName:  m.DisplayName,
		AvatarURL:    m.AvatarURL,
		PasswordHash: m.PasswordHash,
		TenantID:     m.TenantID,
		Roles:        roles,
		Status:       domain.UserStatus(m.Status),
		CreatedAt:    m.CreatedAt,
		UpdatedAt:    m.UpdatedAt,
		LastLoginAt:  m.LastLoginAt,
	}, nil
}

// FromUserEntity converts domain.User to UserModel
func FromUserEntity(user *domain.User) (*UserModel, error) {
	rolesJSON, err := json.Marshal(user.Roles)
	if err != nil {
		return nil, err
	}

	return &UserModel{
		ID:           user.ID,
		Email:        user.Email,
		Username:     user.Username,
		DisplayName:  user.DisplayName,
		AvatarURL:    user.AvatarURL,
		PasswordHash: user.PasswordHash,
		TenantID:     user.TenantID,
		Roles:        string(rolesJSON),
		Status:       string(user.Status),
		CreatedAt:    user.CreatedAt,
		UpdatedAt:    user.UpdatedAt,
		LastLoginAt:  user.LastLoginAt,
	}, nil
}

// userRepo is the user repository implementation.
type userRepo struct {
	data *Data
	log  *log.Helper
}

// NewUserRepo creates a new user repository.
func NewUserRepo(data *Data, logger log.Logger) domain.UserRepository {
	return &userRepo{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create implements domain.UserRepository
func (r *userRepo) Create(ctx context.Context, user *domain.User) error {
	model, err := FromUserEntity(user)
	if err != nil {
		return err
	}

	return r.data.db.WithContext(ctx).Create(model).Error
}

// GetByID implements domain.UserRepository
func (r *userRepo) GetByID(ctx context.Context, id string) (*domain.User, error) {
	var model UserModel
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&model).Error; err != nil {
		return nil, err
	}

	return model.ToEntity()
}

// GetByEmail implements domain.UserRepository
func (r *userRepo) GetByEmail(ctx context.Context, email string) (*domain.User, error) {
	var model UserModel
	if err := r.data.db.WithContext(ctx).Where("email = ?", email).First(&model).Error; err != nil {
		return nil, err
	}

	return model.ToEntity()
}

// GetByTenantID implements domain.UserRepository
func (r *userRepo) GetByTenantID(ctx context.Context, tenantID string, offset, limit int) ([]*domain.User, error) {
	var models []UserModel
	if err := r.data.db.WithContext(ctx).
		Where("tenant_id = ?", tenantID).
		Offset(offset).
		Limit(limit).
		Find(&models).Error; err != nil {
		return nil, err
	}

	users := make([]*domain.User, 0, len(models))
	for _, model := range models {
		user, err := model.ToEntity()
		if err != nil {
			return nil, err
		}
		users = append(users, user)
	}

	return users, nil
}

// Update implements domain.UserRepository
func (r *userRepo) Update(ctx context.Context, user *domain.User) error {
	model, err := FromUserEntity(user)
	if err != nil {
		return err
	}

	return r.data.db.WithContext(ctx).Save(model).Error
}

// Delete implements domain.UserRepository (soft delete)
func (r *userRepo) Delete(ctx context.Context, id string) error {
	return r.data.db.WithContext(ctx).Delete(&UserModel{}, "id = ?", id).Error
}

// CountByTenantID implements domain.UserRepository
func (r *userRepo) CountByTenantID(ctx context.Context, tenantID string) (int, error) {
	var count int64
	if err := r.data.db.WithContext(ctx).
		Model(&UserModel{}).
		Where("tenant_id = ?", tenantID).
		Count(&count).Error; err != nil {
		return 0, err
	}

	return int(count), nil
}
