package biz

import (
	"context"
	"time"

	"voiceassistant/cmd/identity-service/internal/domain"
	pkgErrors "voiceassistant/pkg/errors"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/golang-jwt/jwt/v5"
)

// TokenBlacklist Token黑名单接口
type TokenBlacklist interface {
	AddToBlacklist(ctx context.Context, token string, expiresAt time.Time) error
	IsBlacklisted(ctx context.Context, token string) (bool, error)
	GetBlacklistStats(ctx context.Context) (map[string]interface{}, error)
}

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
	userRepo       domain.UserRepository
	tenantRepo     domain.TenantRepository
	tokenBlacklist TokenBlacklist
	auditLogSvc    *AuditLogService
	jwtSecret      string
	log            *log.Helper
}

// NewAuthUsecase 创建认证用例
func NewAuthUsecase(
	userRepo domain.UserRepository,
	tenantRepo domain.TenantRepository,
	tokenBlacklist TokenBlacklist,
	auditLogSvc *AuditLogService,
	jwtSecret string,
	logger log.Logger,
) *AuthUsecase {
	return &AuthUsecase{
		userRepo:       userRepo,
		tenantRepo:     tenantRepo,
		tokenBlacklist: tokenBlacklist,
		auditLogSvc:    auditLogSvc,
		jwtSecret:      jwtSecret,
		log:            log.NewHelper(logger),
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
		// 记录失败的审计日志
		if uc.auditLogSvc != nil {
			_ = uc.auditLogSvc.LogFailure(ctx, user.TenantID, user.ID, AuditActionUserLogin, "user:"+user.ID,
				pkgErrors.NewUnauthorized("INVALID_CREDENTIALS", "密码错误"), map[string]interface{}{
					"email":  email,
					"reason": "invalid_password",
				})
		}
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

	// 7. 记录审计日志
	if uc.auditLogSvc != nil {
		_ = uc.auditLogSvc.LogSuccess(ctx, user.TenantID, user.ID, AuditActionUserLogin, "user:"+user.ID, map[string]interface{}{
			"email":  email,
			"method": "password",
		})
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
func (uc *AuthUsecase) VerifyToken(ctx context.Context, tokenString string) (*Claims, error) {
	// 1. 解析Token
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		return []byte(uc.jwtSecret), nil
	})

	if err != nil {
		return nil, pkgErrors.NewUnauthorized("INVALID_TOKEN", "Token无效")
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, pkgErrors.NewUnauthorized("INVALID_TOKEN", "Token无效")
	}

	// 2. 检查是否在黑名单中
	if uc.tokenBlacklist != nil {
		isBlacklisted, err := uc.tokenBlacklist.IsBlacklisted(ctx, tokenString)
		if err != nil {
			uc.log.WithContext(ctx).Warnf("Failed to check token blacklist: %v", err)
			// 黑名单检查失败，不影响正常流程（降级处理）
		} else if isBlacklisted {
			return nil, pkgErrors.NewUnauthorized("TOKEN_REVOKED", "Token已被吊销")
		}
	}

	return claims, nil
}

// RefreshToken 刷新 Token
func (uc *AuthUsecase) RefreshToken(ctx context.Context, refreshToken string) (*TokenPair, error) {
	// 验证 Refresh Token
	claims, err := uc.VerifyToken(ctx, refreshToken)
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

	// 将旧的Refresh Token加入黑名单
	if uc.tokenBlacklist != nil && claims.ExpiresAt != nil {
		err = uc.tokenBlacklist.AddToBlacklist(ctx, refreshToken, claims.ExpiresAt.Time)
		if err != nil {
			uc.log.WithContext(ctx).Warnf("Failed to add old refresh token to blacklist: %v", err)
			// 不中断流程，继续生成新Token
		}
	}

	// 生成新的 Token 对
	tokenPair, err := uc.GenerateTokenPair(user)
	if err != nil {
		return nil, pkgErrors.NewInternalServerError("TOKEN_GENERATION_FAILED", "生成Token失败")
	}

	uc.log.WithContext(ctx).Infof("Token refreshed for user: %s", user.ID)
	return tokenPair, nil
}

// Logout 用户登出
func (uc *AuthUsecase) Logout(ctx context.Context, accessToken, refreshToken string) error {
	// 1. 解析Access Token获取过期时间
	claims, err := uc.VerifyToken(ctx, accessToken)
	if err != nil {
		// Token已经无效，可能已过期，直接返回成功
		uc.log.WithContext(ctx).Warnf("Logout with invalid token: %v", err)
		return nil
	}

	// 2. 将Access Token加入黑名单
	if uc.tokenBlacklist != nil {
		if claims.ExpiresAt != nil {
			err = uc.tokenBlacklist.AddToBlacklist(ctx, accessToken, claims.ExpiresAt.Time)
			if err != nil {
				uc.log.WithContext(ctx).Errorf("Failed to add access token to blacklist: %v", err)
				return pkgErrors.NewInternalServerError("BLACKLIST_ERROR", "登出失败")
			}
		}

		// 3. 如果提供了Refresh Token，也加入黑名单
		if refreshToken != "" {
			refreshClaims, err := uc.VerifyToken(ctx, refreshToken)
			if err == nil && refreshClaims.ExpiresAt != nil {
				err = uc.tokenBlacklist.AddToBlacklist(ctx, refreshToken, refreshClaims.ExpiresAt.Time)
				if err != nil {
					uc.log.WithContext(ctx).Warnf("Failed to add refresh token to blacklist: %v", err)
					// 不阻塞登出流程
				}
			}
		}
	}

	// 4. 记录审计日志
	if uc.auditLogSvc != nil {
		_ = uc.auditLogSvc.LogSuccess(ctx, claims.TenantID, claims.UserID, AuditActionUserLogout, "user:"+claims.UserID, map[string]interface{}{
			"method": "token_revocation",
		})
	}

	uc.log.WithContext(ctx).Infof("User logged out: %s", claims.UserID)
	return nil
}

// GetBlacklistStats 获取黑名单统计信息（用于监控）
func (uc *AuthUsecase) GetBlacklistStats(ctx context.Context) (map[string]interface{}, error) {
	if uc.tokenBlacklist == nil {
		return map[string]interface{}{
			"enabled": false,
		}, nil
	}

	stats, err := uc.tokenBlacklist.GetBlacklistStats(ctx)
	if err != nil {
		return nil, pkgErrors.NewInternalServerError("STATS_ERROR", "获取统计信息失败")
	}

	stats["enabled"] = true
	return stats, nil
}
