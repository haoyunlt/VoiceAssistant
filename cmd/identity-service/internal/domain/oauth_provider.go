package domain

import "time"

type OAuthProvider string

const (
	OAuthProviderWechat OAuthProvider = "wechat"
	OAuthProviderGitHub OAuthProvider = "github"
	OAuthProviderGoogle OAuthProvider = "google"
)

// OAuthAccount OAuth账号绑定
type OAuthAccount struct {
	ID           string
	UserID       string
	Provider     OAuthProvider
	ProviderID   string // 第三方用户ID
	AccessToken  string
	RefreshToken string
	ExpiresAt    time.Time
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// NewOAuthAccount 创建OAuth账号
func NewOAuthAccount(
	userID string,
	provider OAuthProvider,
	providerID string,
	accessToken string,
) *OAuthAccount {
	return &OAuthAccount{
		ID:          generateID(),
		UserID:      userID,
		Provider:    provider,
		ProviderID:  providerID,
		AccessToken: accessToken,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}
}

// OAuthUserInfo OAuth用户信息
type OAuthUserInfo struct {
	ID          string
	Name        string
	Email       string
	AvatarURL   string
	AccessToken string
	ExpiresIn   int
}

// OAuthRepository OAuth仓储接口
type OAuthRepository interface {
	Create(account *OAuthAccount) error
	GetByProviderID(provider OAuthProvider, providerID string) (*OAuthAccount, error)
	GetByUserID(userID string) ([]*OAuthAccount, error)
	Delete(id string) error
}
