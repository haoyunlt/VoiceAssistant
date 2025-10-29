package biz

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"voicehelper/cmd/knowledge-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/uuid"
	"google.golang.org/grpc/metadata"
)

// AuthzService 授权服务
type AuthzService struct {
	permRepo  domain.PermissionRepository
	auditRepo domain.AuditLogRepository
	cache     Cache
	log       *log.Helper
}

// Cache 缓存接口
type Cache interface {
	Get(key string) (interface{}, bool)
	Set(key string, value interface{}, ttl time.Duration)
	Delete(key string)
}

// NewAuthzService 创建授权服务
func NewAuthzService(
	permRepo domain.PermissionRepository,
	auditRepo domain.AuditLogRepository,
	cache Cache,
	logger log.Logger,
) *AuthzService {
	return &AuthzService{
		permRepo:  permRepo,
		auditRepo: auditRepo,
		cache:     cache,
		log:       log.NewHelper(logger),
	}
}

// CheckPermission 检查权限
func (s *AuthzService) CheckPermission(
	ctx context.Context,
	userID, resource, action string,
) (bool, error) {
	// 1. 从缓存获取
	cacheKey := fmt.Sprintf("perm:%s:%s:%s", userID, resource, action)
	if cached, found := s.cache.Get(cacheKey); found {
		return cached.(bool), nil
	}

	// 2. 获取用户角色
	tenantID := s.getTenantIDFromContext(ctx)
	roles, err := s.permRepo.GetUserRoles(ctx, userID, tenantID)
	if err != nil {
		return false, fmt.Errorf("get user roles: %w", err)
	}

	// 3. 评估权限
	allowed := s.evaluatePermissions(roles, resource, action)

	// 4. 缓存结果（TTL=5分钟）
	s.cache.Set(cacheKey, allowed, 5*time.Minute)

	return allowed, nil
}

// evaluatePermissions 评估权限
func (s *AuthzService) evaluatePermissions(
	roles []*domain.Role,
	resource, action string,
) bool {
	// Deny优先原则
	for _, role := range roles {
		for _, perm := range role.Permissions {
			if s.matchResource(perm.Resource, resource) && s.matchAction(perm.Action, action) {
				if perm.Effect == string(domain.EffectDeny) {
					return false
				}
			}
		}
	}

	// 检查Allow
	for _, role := range roles {
		for _, perm := range role.Permissions {
			if s.matchResource(perm.Resource, resource) && s.matchAction(perm.Action, action) {
				if perm.Effect == string(domain.EffectAllow) {
					return true
				}
			}
		}
	}

	return false // 默认拒绝
}

// matchResource 匹配资源
func (s *AuthzService) matchResource(pattern, resource string) bool {
	// 支持通配符：kb:* 匹配所有知识库
	if pattern == "*" {
		return true
	}

	if strings.HasSuffix(pattern, ":*") {
		prefix := strings.TrimSuffix(pattern, ":*")
		return strings.HasPrefix(resource, prefix+":")
	}

	return pattern == resource
}

// matchAction 匹配操作
func (s *AuthzService) matchAction(pattern, action string) bool {
	// admin包含所有权限
	if pattern == string(domain.ActionAdmin) {
		return true
	}

	// write包含read
	if pattern == string(domain.ActionWrite) && action == string(domain.ActionRead) {
		return true
	}

	return pattern == action
}

// getTenantIDFromContext 从上下文获取租户ID
func (s *AuthzService) getTenantIDFromContext(ctx context.Context) string {
	// 优先从上下文中的metadata获取
	if tenantID, ok := ctx.Value("tenant_id").(string); ok && tenantID != "" {
		return tenantID
	}

	// 从gRPC metadata获取
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		if values := md.Get("x-tenant-id"); len(values) > 0 {
			return values[0]
		}
		// 也尝试从Authorization header中的JWT获取
		if values := md.Get("authorization"); len(values) > 0 {
			claims := extractJWTClaims(values[0])
			if tenantID, ok := claims["tenant_id"].(string); ok {
				return tenantID
			}
		}
	}

	return "default"
}

// LogAudit 记录审计日志
func (s *AuthzService) LogAudit(
	ctx context.Context,
	action, resource, details, status, errorMsg string,
) error {
	userID := s.getUserIDFromContext(ctx)
	tenantID := s.getTenantIDFromContext(ctx)
	ip := s.getIPFromContext(ctx)
	userAgent := s.getUserAgentFromContext(ctx)

	auditLog := domain.NewAuditLog(
		tenantID,
		userID,
		action,
		resource,
		details,
		ip,
		userAgent,
		status,
		errorMsg,
	)

	if err := s.auditRepo.Create(ctx, auditLog); err != nil {
		s.log.WithContext(ctx).Errorf("Failed to create audit log: %v", err)
		return err
	}

	return nil
}

// getUserIDFromContext 从上下文获取用户ID
func (s *AuthzService) getUserIDFromContext(ctx context.Context) string {
	// 优先从上下文中的metadata获取
	if userID, ok := ctx.Value("user_id").(string); ok && userID != "" {
		return userID
	}

	// 从gRPC metadata获取
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		if values := md.Get("x-user-id"); len(values) > 0 {
			return values[0]
		}
		// 从JWT token获取
		if values := md.Get("authorization"); len(values) > 0 {
			claims := extractJWTClaims(values[0])
			if userID, ok := claims["user_id"].(string); ok {
				return userID
			}
			if sub, ok := claims["sub"].(string); ok {
				return sub
			}
		}
	}

	return "unknown"
}

// getIPFromContext 从上下文获取IP
func (s *AuthzService) getIPFromContext(ctx context.Context) string {
	// 从gRPC metadata获取
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		// 尝试获取真实IP（通过代理传递）
		if values := md.Get("x-real-ip"); len(values) > 0 {
			return values[0]
		}
		if values := md.Get("x-forwarded-for"); len(values) > 0 {
			// X-Forwarded-For 可能包含多个IP，取第一个
			ips := strings.Split(values[0], ",")
			if len(ips) > 0 {
				return strings.TrimSpace(ips[0])
			}
		}
	}

	return "0.0.0.0"
}

// getUserAgentFromContext 从上下文获取UserAgent
func (s *AuthzService) getUserAgentFromContext(ctx context.Context) string {
	// 从gRPC metadata获取
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		if values := md.Get("user-agent"); len(values) > 0 {
			return values[0]
		}
		if values := md.Get("grpc-user-agent"); len(values) > 0 {
			return values[0]
		}
	}

	return "unknown"
}

// extractJWTClaims 从JWT token提取claims
func extractJWTClaims(authorization string) map[string]interface{} {
	// 移除 "Bearer " 前缀
	token := strings.TrimPrefix(authorization, "Bearer ")
	token = strings.TrimPrefix(token, "bearer ")

	if token == "" || token == authorization {
		return nil
	}

	// 简单的JWT解析（仅提取payload，不验证签名）
	// JWT格式: header.payload.signature
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil
	}

	// Base64解码payload
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		// 尝试标准base64解码
		payload, err = base64.URLEncoding.DecodeString(parts[1])
		if err != nil {
			return nil
		}
	}

	// 解析JSON
	var claims map[string]interface{}
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil
	}

	return claims
}

// GrantRole 授予角色
func (s *AuthzService) GrantRole(
	ctx context.Context,
	userID, roleID, resource string,
	expiresAt *time.Time,
) error {
	tenantID := s.getTenantIDFromContext(ctx)

	userRole := &domain.UserRole{
		ID:        uuid.NewString(),
		UserID:    userID,
		RoleID:    roleID,
		TenantID:  tenantID,
		Resource:  resource,
		CreatedAt: time.Now(),
		ExpiresAt: expiresAt,
	}

	if err := s.permRepo.GrantRole(ctx, userRole); err != nil {
		return fmt.Errorf("grant role: %w", err)
	}

	// 清除缓存
	s.clearUserPermissionCache(userID)

	// 记录审计日志
	s.LogAudit(ctx, "grant_role", fmt.Sprintf("user:%s", userID), fmt.Sprintf("role:%s", roleID), "success", "")

	return nil
}

// RevokeRole 撤销角色
func (s *AuthzService) RevokeRole(
	ctx context.Context,
	userID, roleID string,
) error {
	if err := s.permRepo.RevokeRole(ctx, userID, roleID); err != nil {
		return fmt.Errorf("revoke role: %w", err)
	}

	// 清除缓存
	s.clearUserPermissionCache(userID)

	// 记录审计日志
	s.LogAudit(ctx, "revoke_role", fmt.Sprintf("user:%s", userID), fmt.Sprintf("role:%s", roleID), "success", "")

	return nil
}

// clearUserPermissionCache 清除用户权限缓存
func (s *AuthzService) clearUserPermissionCache(userID string) {
	// 简化实现：使用通配符清除
	// TODO: 实现更精确的缓存清除
	s.cache.Delete(fmt.Sprintf("perm:%s:*", userID))
}

// GetAuditLogs 获取审计日志
func (s *AuthzService) GetAuditLogs(
	ctx context.Context,
	filters map[string]interface{},
	offset, limit int,
) ([]*domain.AuditLog, int64, error) {
	tenantID := s.getTenantIDFromContext(ctx)

	logs, total, err := s.auditRepo.List(ctx, tenantID, filters, offset, limit)
	if err != nil {
		return nil, 0, fmt.Errorf("list audit logs: %w", err)
	}

	return logs, total, nil
}

// BuiltinRoles 内置角色
var BuiltinRoles = []*domain.Role{
	{
		ID:          "role_admin",
		Name:        "Administrator",
		Description: "Full access to all resources",
		Permissions: []domain.Permission{
			{
				Resource: "*",
				Action:   string(domain.ActionAdmin),
				Effect:   string(domain.EffectAllow),
			},
		},
	},
	{
		ID:          "role_editor",
		Name:        "Editor",
		Description: "Can read and write knowledge bases and documents",
		Permissions: []domain.Permission{
			{
				Resource: "kb:*",
				Action:   string(domain.ActionWrite),
				Effect:   string(domain.EffectAllow),
			},
			{
				Resource: "doc:*",
				Action:   string(domain.ActionWrite),
				Effect:   string(domain.EffectAllow),
			},
		},
	},
	{
		ID:          "role_viewer",
		Name:        "Viewer",
		Description: "Can only read knowledge bases and documents",
		Permissions: []domain.Permission{
			{
				Resource: "kb:*",
				Action:   string(domain.ActionRead),
				Effect:   string(domain.EffectAllow),
			},
			{
				Resource: "doc:*",
				Action:   string(domain.ActionRead),
				Effect:   string(domain.EffectAllow),
			},
		},
	},
}
