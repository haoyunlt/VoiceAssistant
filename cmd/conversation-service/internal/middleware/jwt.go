package middleware

import (
	"fmt"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/golang-jwt/jwt/v5"
)

// JWTManager JWT 管理器
type JWTManager struct {
	secretKey     string
	tokenDuration time.Duration
	skipPaths     []string
	logger        *log.Helper
}

// Claims JWT Claims
type Claims struct {
	UserID   string `json:"user_id"`
	TenantID string `json:"tenant_id"`
	Role     string `json:"role"`
	Tier     string `json:"tier"` // 用户等级（用于限流）
	jwt.RegisteredClaims
}

// JWTConfig JWT 配置
type JWTConfig struct {
	SecretKey     string
	TokenDuration time.Duration
	SkipPaths     []string
}

// NewJWTManager 创建 JWT 管理器
func NewJWTManager(config *JWTConfig, logger log.Logger) *JWTManager {
	if config == nil {
		config = &JWTConfig{
			SecretKey:     "default-secret-key",
			TokenDuration: 24 * time.Hour,
			SkipPaths:     []string{"/health", "/metrics"},
		}
	}

	return &JWTManager{
		secretKey:     config.SecretKey,
		tokenDuration: config.TokenDuration,
		skipPaths:     config.SkipPaths,
		logger:        log.NewHelper(log.With(logger, "module", "jwt")),
	}
}

// Middleware JWT 认证中间件
func (m *JWTManager) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 检查是否跳过认证
		path := c.Request.URL.Path
		if m.shouldSkip(path) {
			c.Next()
			return
		}

		// 提取 Authorization header
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			m.logger.Warn("Missing authorization header")
			c.JSON(401, gin.H{
				"code":    401,
				"message": "Missing authorization header",
			})
			c.Abort()
			return
		}

		// 检查 Bearer token 格式
		parts := strings.Split(authHeader, " ")
		if len(parts) != 2 || parts[0] != "Bearer" {
			m.logger.Warn("Invalid authorization format")
			c.JSON(401, gin.H{
				"code":    401,
				"message": "Invalid authorization format, expected 'Bearer <token>'",
			})
			c.Abort()
			return
		}

		// 验证 token
		claims, err := m.VerifyToken(parts[1])
		if err != nil {
			m.logger.Warnf("Invalid token: %v", err)
			c.JSON(401, gin.H{
				"code":    401,
				"message": "Invalid or expired token",
				"error":   err.Error(),
			})
			c.Abort()
			return
		}

		// 注入上下文
		c.Set("user_id", claims.UserID)
		c.Set("tenant_id", claims.TenantID)
		c.Set("role", claims.Role)
		c.Set("tier", claims.Tier)

		// 可选：记录认证日志
		m.logger.Debugf("Authenticated: user=%s, tenant=%s, role=%s", claims.UserID, claims.TenantID, claims.Role)

		c.Next()
	}
}

// VerifyToken 验证 JWT token
func (m *JWTManager) VerifyToken(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		// 验证签名算法
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(m.secretKey), nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token claims")
	}

	// 检查是否过期
	if claims.ExpiresAt != nil && claims.ExpiresAt.Before(time.Now()) {
		return nil, fmt.Errorf("token expired")
	}

	return claims, nil
}

// GenerateToken 生成 JWT token（用于测试或集成）
func (m *JWTManager) GenerateToken(userID, tenantID, role, tier string) (string, error) {
	now := time.Now()
	claims := &Claims{
		UserID:   userID,
		TenantID: tenantID,
		Role:     role,
		Tier:     tier,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(now.Add(m.tokenDuration)),
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
			Issuer:    "conversation-service",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(m.secretKey))
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	return tokenString, nil
}

// RefreshToken 刷新 token（可选功能）
func (m *JWTManager) RefreshToken(tokenString string) (string, error) {
	// 验证旧 token
	claims, err := m.VerifyToken(tokenString)
	if err != nil {
		// 如果 token 过期但不超过刷新窗口（例如 7 天），允许刷新
		// 这里简化处理，直接返回错误
		return "", fmt.Errorf("cannot refresh invalid token: %w", err)
	}

	// 生成新 token
	return m.GenerateToken(claims.UserID, claims.TenantID, claims.Role, claims.Tier)
}

// shouldSkip 检查是否应该跳过认证
func (m *JWTManager) shouldSkip(path string) bool {
	for _, skipPath := range m.skipPaths {
		if strings.HasPrefix(path, skipPath) {
			return true
		}
	}
	return false
}

// ExtractClaims 从 gin.Context 提取 claims（辅助函数）
func ExtractClaims(c *gin.Context) (*Claims, error) {
	userID := c.GetString("user_id")
	tenantID := c.GetString("tenant_id")
	role := c.GetString("role")
	tier := c.GetString("tier")

	if userID == "" || tenantID == "" {
		return nil, fmt.Errorf("missing authentication context")
	}

	return &Claims{
		UserID:   userID,
		TenantID: tenantID,
		Role:     role,
		Tier:     tier,
	}, nil
}
