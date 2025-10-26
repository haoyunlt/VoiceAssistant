package biz

import (
	"context"
	"time"

	"voiceassistant/cmd/identity-service/internal/domain"
	pkgErrors "voiceassistant/pkg/errors"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/golang-jwt/jwt/v5"
)

// TokenPair Token 对
type TokenPair struct {
	AccessToken  string
	RefreshToken string
	ExpiresIn    int64
}

// Claims JWT Claims
type Claims struct {
	UserID   string   `json:"user_id"`
	Email    string   `json:"email"`
	TenantID string   `json:"tenant_id"`
	Roles    []string `json:"roles"`
	jwt.RegisteredClaims
}

// AuthUsecase 认证用例
type AuthUsecase struct {
	userRepo   domain.UserRepository
	tenantRepo domain.TenantRepository
	jwtSecret  string
	log        *log.Helper
}

// NewAuthUsecase 创建认证用例
func NewAuthUsecase(
	userRepo domain.UserRepository,
	tenantRepo domain.TenantRepository,
	jwtSecret string,
	logger log.Logger,
) *AuthUsecase {
	return &AuthUsecase{
		userRepo:   userRepo,
		tenantRepo: tenantRepo,
		jwtSecret:  jwtSecret,
		log:        log.NewHelper(logger),
	}
}

// Login 用户登录
func (uc *AuthUsecase) Login(ctx context.Context, email, password string) (*TokenPair, *domain.User, error) {
	uc.log.WithContext(ctx).Infof("User login attempt: %s", email)

	// 1. 获取用户
	user, err := uc.userRepo.GetByEmail(ctx, email)
	if err != nil {
		return nil, nil, pkgErrors.NewUnauthorized("INVALID_CREDENTIALS", "邮箱或密码错误")
	}

	// 2. 验证密码
	if !user.VerifyPassword(password) {
		return nil, nil, pkgErrors.NewUnauthorized("INVALID_CREDENTIALS", "邮箱或密码错误")
	}

	// 3. 检查用户状态
	if !user.IsActive() {
		return nil, nil, pkgErrors.NewUnauthorized("USER_INACTIVE", "用户已被停用")
	}

	// 4. 检查租户状态
	tenant, err := uc.tenantRepo.GetByID(ctx, user.TenantID)
	if err != nil {
		return nil, nil, pkgErrors.NewInternalServerError("TENANT_ERROR", "租户信息错误")
	}

	if !tenant.IsActive() {
		return nil, nil, pkgErrors.NewUnauthorized("TENANT_INACTIVE", "租户已被停用")
	}

	// 5. 生成 Token
	tokenPair, err := uc.GenerateTokenPair(user)
	if err != nil {
		return nil, nil, pkgErrors.NewInternalServerError("TOKEN_GENERATION_FAILED", "生成Token失败")
	}

	// 6. 记录登录时间
	user.RecordLogin()
	if err := uc.userRepo.Update(ctx, user); err != nil {
		uc.log.WithContext(ctx).Warnf("Failed to update last login time: %v", err)
	}

	uc.log.WithContext(ctx).Infof("User logged in successfully: %s", user.ID)
	return tokenPair, user, nil
}

// GenerateTokenPair 生成 Token 对
func (uc *AuthUsecase) GenerateTokenPair(user *domain.User) (*TokenPair, error) {
	now := time.Now()
	accessTokenExpiry := now.Add(1 * time.Hour)       // Access Token 1小时
	refreshTokenExpiry := now.Add(7 * 24 * time.Hour) // Refresh Token 7天

	// Access Token
	accessClaims := Claims{
		UserID:   user.ID,
		Email:    user.Email,
		TenantID: user.TenantID,
		Roles:    user.Roles,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(accessTokenExpiry),
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
			Issuer:    "voicehelper-identity",
			Subject:   user.ID,
		},
	}

	accessToken := jwt.NewWithClaims(jwt.SigningMethodHS256, accessClaims)
	accessTokenString, err := accessToken.SignedString([]byte(uc.jwtSecret))
	if err != nil {
		return nil, err
	}

	// Refresh Token
	refreshClaims := Claims{
		UserID:   user.ID,
		Email:    user.Email,
		TenantID: user.TenantID,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(refreshTokenExpiry),
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
			Issuer:    "voicehelper-identity",
			Subject:   user.ID,
		},
	}

	refreshToken := jwt.NewWithClaims(jwt.SigningMethodHS256, refreshClaims)
	refreshTokenString, err := refreshToken.SignedString([]byte(uc.jwtSecret))
	if err != nil {
		return nil, err
	}

	return &TokenPair{
		AccessToken:  accessTokenString,
		RefreshToken: refreshTokenString,
		ExpiresIn:    3600, // 1小时，单位：秒
	}, nil
}

// VerifyToken 验证 Token
func (uc *AuthUsecase) VerifyToken(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		return []byte(uc.jwtSecret), nil
	})

	if err != nil {
		return nil, pkgErrors.NewUnauthorized("INVALID_TOKEN", "Token无效")
	}

	if claims, ok := token.Claims.(*Claims); ok && token.Valid {
		return claims, nil
	}

	return nil, pkgErrors.NewUnauthorized("INVALID_TOKEN", "Token无效")
}

// RefreshToken 刷新 Token
func (uc *AuthUsecase) RefreshToken(ctx context.Context, refreshToken string) (*TokenPair, error) {
	// 验证 Refresh Token
	claims, err := uc.VerifyToken(refreshToken)
	if err != nil {
		return nil, err
	}

	// 获取用户
	user, err := uc.userRepo.GetByID(ctx, claims.UserID)
	if err != nil {
		return nil, pkgErrors.NewUnauthorized("USER_NOT_FOUND", "用户不存在")
	}

	// 检查用户状态
	if !user.IsActive() {
		return nil, pkgErrors.NewUnauthorized("USER_INACTIVE", "用户已被停用")
	}

	// 生成新的 Token 对
	tokenPair, err := uc.GenerateTokenPair(user)
	if err != nil {
		return nil, pkgErrors.NewInternalServerError("TOKEN_GENERATION_FAILED", "生成Token失败")
	}

	uc.log.WithContext(ctx).Infof("Token refreshed for user: %s", user.ID)
	return tokenPair, nil
}

// Logout 用户登出（可选实现：将 Token 加入黑名单）
func (uc *AuthUsecase) Logout(ctx context.Context, userID string) error {
	// TODO: 实现 Token 黑名单机制（使用 Redis）
	uc.log.WithContext(ctx).Infof("User logged out: %s", userID)
	return nil
}
