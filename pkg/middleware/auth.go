package middleware

import (
	"net/http"
	"strings"
	"voice-assistant/pkg/auth"

	"github.com/gin-gonic/gin"
)

type contextKey string

const (
	UserContextKey contextKey = "user"
)

// AuthMiddleware JWT authentication middleware
func AuthMiddleware(jwtManager *auth.JWTManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Extract token from Authorization header
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authorization header required",
			})
			c.Abort()
			return
		}

		// Check Bearer scheme
		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid authorization header format",
			})
			c.Abort()
			return
		}

		tokenString := parts[1]

		// Validate token
		claims, err := jwtManager.ValidateToken(tokenString)
		if err != nil {
			if err == auth.ErrExpiredToken {
				c.JSON(http.StatusUnauthorized, gin.H{
					"error": "Token expired",
				})
			} else {
				c.JSON(http.StatusUnauthorized, gin.H{
					"error": "Invalid token",
				})
			}
			c.Abort()
			return
		}

		// Store claims in context
		c.Set("user_id", claims.UserID)
		c.Set("username", claims.Username)
		c.Set("email", claims.Email)
		c.Set("roles", claims.Roles)
		c.Set("claims", claims)

		// Check if token should be renewed
		if jwtManager.ShouldRenew(claims) {
			newToken, err := jwtManager.RenewToken(claims)
			if err == nil {
				// Return new token in response header
				c.Header("X-New-Token", newToken)
				// Optional: also set in X-Token-Renewed header to indicate renewal happened
				c.Header("X-Token-Renewed", "true")
			}
			// If renewal fails, continue with the current valid token
		}

		c.Next()
	}
}

// OptionalAuthMiddleware optional JWT authentication
func OptionalAuthMiddleware(jwtManager *auth.JWTManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.Next()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.Next()
			return
		}

		tokenString := parts[1]
		claims, err := jwtManager.ValidateToken(tokenString)
		if err == nil {
			c.Set("user_id", claims.UserID)
			c.Set("username", claims.Username)
			c.Set("email", claims.Email)
			c.Set("roles", claims.Roles)
			c.Set("claims", claims)
		}

		c.Next()
	}
}

// RequirePermission middleware to check permissions
func RequirePermission(rbacManager *auth.RBACManager, permission auth.Permission) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get roles from context
		rolesInterface, exists := c.Get("roles")
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "No roles found in context",
			})
			c.Abort()
			return
		}

		roles, ok := rolesInterface.([]string)
		if !ok {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Invalid roles format",
			})
			c.Abort()
			return
		}

		// Check permission
		if !rbacManager.CheckUserPermission(roles, permission) {
			c.JSON(http.StatusForbidden, gin.H{
				"error":      "Insufficient permissions",
				"required":   permission,
				"user_roles": roles,
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// RequireAnyPermission middleware to check if user has any of the permissions
func RequireAnyPermission(rbacManager *auth.RBACManager, permissions ...auth.Permission) gin.HandlerFunc {
	return func(c *gin.Context) {
		rolesInterface, exists := c.Get("roles")
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "No roles found in context",
			})
			c.Abort()
			return
		}

		roles, ok := rolesInterface.([]string)
		if !ok {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Invalid roles format",
			})
			c.Abort()
			return
		}

		// Check if user has any of the permissions
		hasPermission := false
		for _, permission := range permissions {
			if rbacManager.CheckUserPermission(roles, permission) {
				hasPermission = true
				break
			}
		}

		if !hasPermission {
			c.JSON(http.StatusForbidden, gin.H{
				"error":      "Insufficient permissions",
				"required":   permissions,
				"user_roles": roles,
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// RequireRole middleware to check if user has a specific role
func RequireRole(role auth.Role) gin.HandlerFunc {
	return func(c *gin.Context) {
		rolesInterface, exists := c.Get("roles")
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "No roles found in context",
			})
			c.Abort()
			return
		}

		roles, ok := rolesInterface.([]string)
		if !ok {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Invalid roles format",
			})
			c.Abort()
			return
		}

		// Check if user has the role
		hasRole := false
		for _, r := range roles {
			if auth.Role(r) == role {
				hasRole = true
				break
			}
		}

		if !hasRole {
			c.JSON(http.StatusForbidden, gin.H{
				"error":      "Insufficient role",
				"required":   role,
				"user_roles": roles,
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// GetUserID extracts user ID from context
func GetUserID(c *gin.Context) (string, bool) {
	userID, exists := c.Get("user_id")
	if !exists {
		return "", false
	}
	id, ok := userID.(string)
	return id, ok
}

// GetUserRoles extracts user roles from context
func GetUserRoles(c *gin.Context) ([]string, bool) {
	roles, exists := c.Get("roles")
	if !exists {
		return nil, false
	}
	r, ok := roles.([]string)
	return r, ok
}

// GetClaims extracts JWT claims from context
func GetClaims(c *gin.Context) (*auth.Claims, bool) {
	claims, exists := c.Get("claims")
	if !exists {
		return nil, false
	}
	c, ok := claims.(*auth.Claims)
	return c, ok
}
