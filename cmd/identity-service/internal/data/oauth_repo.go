package data

import (
	"voiceassistant/cmd/identity-service/internal/biz"
	"voiceassistant/cmd/identity-service/internal/domain"
	"gorm.io/gorm"
)

// OAuthAccountDO OAuth账号数据对象
type OAuthAccountDO struct {
	ID           string `gorm:"primaryKey"`
	UserID       string `gorm:"index:idx_user_id"`
	Provider     string `gorm:"index:idx_provider_id"`
	ProviderID   string `gorm:"index:idx_provider_id"`
	AccessToken  string
	RefreshToken string
	ExpiresAt    int64
	CreatedAt    int64
	UpdatedAt    int64
}

func (OAuthAccountDO) TableName() string {
	return "oauth_accounts"
}

// OAuthRepo OAuth仓储实现
type OAuthRepo struct {
	db *gorm.DB
}

// NewOAuthRepo 创建OAuth仓储
func NewOAuthRepo(db *gorm.DB) domain.OAuthRepository {
	return &OAuthRepo{db: db}
}

// Create 创建OAuth账号
func (r *OAuthRepo) Create(account *domain.OAuthAccount) error {
	do := &OAuthAccountDO{
		ID:           account.ID,
		UserID:       account.UserID,
		Provider:     string(account.Provider),
		ProviderID:   account.ProviderID,
		AccessToken:  account.AccessToken,
		RefreshToken: account.RefreshToken,
		ExpiresAt:    account.ExpiresAt.Unix(),
		CreatedAt:    account.CreatedAt.Unix(),
		UpdatedAt:    account.UpdatedAt.Unix(),
	}

	return r.db.Create(do).Error
}

// GetByProviderID 根据Provider和ProviderID获取
func (r *OAuthRepo) GetByProviderID(provider domain.OAuthProvider, providerID string) (*domain.OAuthAccount, error) {
	var do OAuthAccountDO
	err := r.db.Where("provider = ? AND provider_id = ?", string(provider), providerID).First(&do).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, biz.ErrOAuthAccountNotFound
		}
		return nil, err
	}

	return r.toDomain(&do), nil
}

// GetByUserID 根据UserID获取所有OAuth账号
func (r *OAuthRepo) GetByUserID(userID string) ([]*domain.OAuthAccount, error) {
	var dos []OAuthAccountDO
	err := r.db.Where("user_id = ?", userID).Find(&dos).Error
	if err != nil {
		return nil, err
	}

	accounts := make([]*domain.OAuthAccount, len(dos))
	for i, do := range dos {
		accounts[i] = r.toDomain(&do)
	}

	return accounts, nil
}

// Delete 删除OAuth账号
func (r *OAuthRepo) Delete(id string) error {
	return r.db.Delete(&OAuthAccountDO{}, "id = ?", id).Error
}

// toDomain 转换为领域对象
func (r *OAuthRepo) toDomain(do *OAuthAccountDO) *domain.OAuthAccount {
	return &domain.OAuthAccount{
		ID:           do.ID,
		UserID:       do.UserID,
		Provider:     domain.OAuthProvider(do.Provider),
		ProviderID:   do.ProviderID,
		AccessToken:  do.AccessToken,
		RefreshToken: do.RefreshToken,
		ExpiresAt:    timeFromUnix(do.ExpiresAt),
		CreatedAt:    timeFromUnix(do.CreatedAt),
		UpdatedAt:    timeFromUnix(do.UpdatedAt),
	}
}
