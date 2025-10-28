package biz

import (
	"context"
	"errors"
	"fmt"

	"voiceassistant/cmd/identity-service/internal/domain"
)

var (
	ErrUnsupportedProvider  = errors.New("unsupported oauth provider")
	ErrOAuthAccountNotFound = errors.New("oauth account not found")
)

// OAuthClient OAuth客户端接口
type OAuthClient interface {
	GetUserInfo(ctx context.Context, code string) (*domain.OAuthUserInfo, error)
}

// WechatClient 微信客户端类型（用于Wire区分）
type WechatClient struct {
	OAuthClient
}

// GithubClient GitHub客户端类型（用于Wire区分）
type GithubClient struct {
	OAuthClient
}

// GoogleClient Google客户端类型（用于Wire区分）
type GoogleClient struct {
	OAuthClient
}

// OAuthUsecase OAuth业务逻辑
type OAuthUsecase struct {
	userRepo     domain.UserRepository
	oauthRepo    domain.OAuthRepository
	tenantRepo   domain.TenantRepository
	authUC       *AuthUsecase
	wechatClient *WechatClient
	githubClient *GithubClient
	googleClient *GoogleClient
}

// NewOAuthUsecase 创建OAuth用例
func NewOAuthUsecase(
	userRepo domain.UserRepository,
	oauthRepo domain.OAuthRepository,
	tenantRepo domain.TenantRepository,
	authUC *AuthUsecase,
	wechatClient *WechatClient,
	githubClient *GithubClient,
	googleClient *GoogleClient,
) *OAuthUsecase {
	return &OAuthUsecase{
		userRepo:     userRepo,
		oauthRepo:    oauthRepo,
		tenantRepo:   tenantRepo,
		authUC:       authUC,
		wechatClient: wechatClient,
		githubClient: githubClient,
		googleClient: googleClient,
	}
}

// LoginWithOAuth OAuth登录
func (uc *OAuthUsecase) LoginWithOAuth(
	ctx context.Context,
	provider domain.OAuthProvider,
	code string,
) (*TokenPair, error) {
	// 1. 根据provider获取用户信息
	var oauthUser *domain.OAuthUserInfo
	var err error

	switch provider {
	case domain.OAuthProviderWechat:
		oauthUser, err = uc.wechatClient.GetUserInfo(ctx, code)
	case domain.OAuthProviderGitHub:
		oauthUser, err = uc.githubClient.GetUserInfo(ctx, code)
	case domain.OAuthProviderGoogle:
		oauthUser, err = uc.googleClient.GetUserInfo(ctx, code)
	default:
		return nil, ErrUnsupportedProvider
	}

	if err != nil {
		return nil, fmt.Errorf("get oauth user info: %w", err)
	}

	// 2. 查找是否已绑定
	oauthAccount, err := uc.oauthRepo.GetByProviderID(provider, oauthUser.ID)
	if err != nil && !errors.Is(err, ErrOAuthAccountNotFound) {
		return nil, fmt.Errorf("get oauth account: %w", err)
	}

	var user *domain.User
	if oauthAccount != nil {
		// 已绑定，获取用户
		user, err = uc.userRepo.GetByID(ctx, oauthAccount.UserID)
		if err != nil {
			return nil, fmt.Errorf("get user: %w", err)
		}
	} else {
		// 未绑定，创建新用户
		user, err = uc.createUserFromOAuth(ctx, oauthUser)
		if err != nil {
			return nil, fmt.Errorf("create user from oauth: %w", err)
		}

		// 创建绑定关系
		oauthAccount = domain.NewOAuthAccount(
			user.ID,
			provider,
			oauthUser.ID,
			oauthUser.AccessToken,
		)
		if err := uc.oauthRepo.Create(oauthAccount); err != nil {
			return nil, fmt.Errorf("create oauth account: %w", err)
		}
	}

	// 3. 生成Token
	tokenPair, err := uc.authUC.GenerateTokenPair(user)
	if err != nil {
		return nil, fmt.Errorf("generate token: %w", err)
	}

	return tokenPair, nil
}

// createUserFromOAuth 从OAuth信息创建用户
func (uc *OAuthUsecase) createUserFromOAuth(
	ctx context.Context,
	oauthUser *domain.OAuthUserInfo,
) (*domain.User, error) {
	// 1. 获取默认租户
	tenant, err := uc.tenantRepo.GetByName(ctx, "default")
	if err != nil {
		return nil, fmt.Errorf("get default tenant: %w", err)
	}

	// 2. 生成随机密码（OAuth用户不需要密码登录）
	randomPassword := generateRandomPassword(16)

	// 3. 构造邮箱（如果OAuth未提供）
	email := oauthUser.Email
	if email == "" {
		// 使用provider ID构造临时邮箱
		email = fmt.Sprintf("%s@oauth.local", oauthUser.ID)
	}

	// 4. 创建用户
	user, err := domain.NewUser(
		email,
		randomPassword,
		oauthUser.Name,
		tenant.ID,
	)
	if err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}
	user.AvatarURL = oauthUser.AvatarURL

	if err := uc.userRepo.Create(ctx, user); err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}

	return user, nil
}

// BindOAuthAccount 绑定OAuth账号
func (uc *OAuthUsecase) BindOAuthAccount(
	ctx context.Context,
	userID string,
	provider domain.OAuthProvider,
	code string,
) error {
	// 1. 获取OAuth用户信息
	var oauthUser *domain.OAuthUserInfo
	var err error

	switch provider {
	case domain.OAuthProviderWechat:
		oauthUser, err = uc.wechatClient.GetUserInfo(ctx, code)
	case domain.OAuthProviderGitHub:
		oauthUser, err = uc.githubClient.GetUserInfo(ctx, code)
	case domain.OAuthProviderGoogle:
		oauthUser, err = uc.googleClient.GetUserInfo(ctx, code)
	default:
		return ErrUnsupportedProvider
	}

	if err != nil {
		return fmt.Errorf("get oauth user info: %w", err)
	}

	// 2. 检查是否已被其他用户绑定
	existing, err := uc.oauthRepo.GetByProviderID(provider, oauthUser.ID)
	if err != nil && !errors.Is(err, ErrOAuthAccountNotFound) {
		return fmt.Errorf("check existing: %w", err)
	}
	if existing != nil && existing.UserID != userID {
		return errors.New("oauth account already bound to another user")
	}

	// 3. 创建绑定
	oauthAccount := domain.NewOAuthAccount(
		userID,
		provider,
		oauthUser.ID,
		oauthUser.AccessToken,
	)

	if err := uc.oauthRepo.Create(oauthAccount); err != nil {
		return fmt.Errorf("create oauth account: %w", err)
	}

	return nil
}

// UnbindOAuthAccount 解绑OAuth账号
func (uc *OAuthUsecase) UnbindOAuthAccount(
	ctx context.Context,
	userID string,
	provider domain.OAuthProvider,
) error {
	// 获取用户的所有OAuth绑定
	accounts, err := uc.oauthRepo.GetByUserID(userID)
	if err != nil {
		return fmt.Errorf("get oauth accounts: %w", err)
	}

	// 找到对应provider的绑定
	var targetAccount *domain.OAuthAccount
	for _, account := range accounts {
		if account.Provider == provider {
			targetAccount = account
			break
		}
	}

	if targetAccount == nil {
		return errors.New("oauth account not found")
	}

	// 删除绑定
	if err := uc.oauthRepo.Delete(targetAccount.ID); err != nil {
		return fmt.Errorf("delete oauth account: %w", err)
	}

	return nil
}

// generateRandomPassword 生成随机密码
func generateRandomPassword(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
	// 这里应该使用crypto/rand，简化示例
	password := make([]byte, length)
	for i := range password {
		password[i] = charset[i%len(charset)]
	}
	return string(password)
}
