package biz

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// AuditAction 审计动作类型
type AuditAction string

const (
	// 用户操作
	AuditActionUserLogin    AuditAction = "user.login"
	AuditActionUserLogout   AuditAction = "user.logout"
	AuditActionUserRegister AuditAction = "user.register"
	AuditActionUserUpdate   AuditAction = "user.update"
	AuditActionUserDelete   AuditAction = "user.delete"
	
	// 权限操作
	AuditActionRoleAssign    AuditAction = "role.assign"
	AuditActionRoleRevoke    AuditAction = "role.revoke"
	AuditActionPermissionGrant AuditAction = "permission.grant"
	AuditActionPermissionDeny  AuditAction = "permission.deny"
	
	// 租户操作
	AuditActionTenantCreate AuditAction = "tenant.create"
	AuditActionTenantUpdate AuditAction = "tenant.update"
	AuditActionTenantDelete AuditAction = "tenant.delete"
	
	// 敏感操作
	AuditActionPasswordChange AuditAction = "password.change"
	AuditActionPasswordReset  AuditAction = "password.reset"
	AuditActionTokenRefresh   AuditAction = "token.refresh"
	AuditActionTokenRevoke    AuditAction = "token.revoke"
)

// AuditLevel 审计级别
type AuditLevel string

const (
	AuditLevelInfo     AuditLevel = "info"     // 信息级别
	AuditLevelWarning  AuditLevel = "warning"  // 警告级别
	AuditLevelCritical AuditLevel = "critical" // 严重级别
)

// AuditLog 审计日志
type AuditLog struct {
	ID        string                 `json:"id"`
	TenantID  string                 `json:"tenant_id"`
	UserID    string                 `json:"user_id"`
	Action    AuditAction            `json:"action"`
	Resource  string                 `json:"resource"`
	Level     AuditLevel             `json:"level"`
	Status    string                 `json:"status"` // success, failure
	IPAddress string                 `json:"ip_address"`
	UserAgent string                 `json:"user_agent"`
	Details   map[string]interface{} `json:"details"`
	Error     string                 `json:"error,omitempty"`
	CreatedAt time.Time              `json:"created_at"`
}

// AuditLogRepository 审计日志仓储接口
type AuditLogRepository interface {
	Create(ctx context.Context, auditLog *AuditLog) error
	Query(ctx context.Context, filters *AuditLogFilters) ([]*AuditLog, int, error)
	GetByID(ctx context.Context, id string) (*AuditLog, error)
}

// AuditLogFilters 审计日志查询过滤器
type AuditLogFilters struct {
	TenantID  string
	UserID    string
	Action    AuditAction
	Resource  string
	Level     AuditLevel
	Status    string
	StartTime *time.Time
	EndTime   *time.Time
	Limit     int
	Offset    int
}

// AuditLogService 审计日志服务
type AuditLogService struct {
	repo AuditLogRepository
	log  *log.Helper
}

// NewAuditLogService 创建审计日志服务
func NewAuditLogService(repo AuditLogRepository, logger log.Logger) *AuditLogService {
	return &AuditLogService{
		repo: repo,
		log:  log.NewHelper(logger),
	}
}

// Log 记录审计日志
func (s *AuditLogService) Log(ctx context.Context, auditLog *AuditLog) error {
	// 设置创建时间
	if auditLog.CreatedAt.IsZero() {
		auditLog.CreatedAt = time.Now()
	}

	// 生成ID
	if auditLog.ID == "" {
		auditLog.ID = generateAuditLogID()
	}

	// 持久化日志
	if err := s.repo.Create(ctx, auditLog); err != nil {
		s.log.WithContext(ctx).Errorf("Failed to create audit log: %v", err)
		return err
	}

	// 根据级别输出不同的日志
	logMsg := s.formatLogMessage(auditLog)
	switch auditLog.Level {
	case AuditLevelCritical:
		s.log.WithContext(ctx).Error(logMsg)
	case AuditLevelWarning:
		s.log.WithContext(ctx).Warn(logMsg)
	default:
		s.log.WithContext(ctx).Info(logMsg)
	}

	return nil
}

// LogSuccess 记录成功的审计日志
func (s *AuditLogService) LogSuccess(
	ctx context.Context,
	tenantID, userID string,
	action AuditAction,
	resource string,
	details map[string]interface{},
) error {
	return s.Log(ctx, &AuditLog{
		TenantID: tenantID,
		UserID:   userID,
		Action:   action,
		Resource: resource,
		Level:    s.determineLevel(action),
		Status:   "success",
		Details:  details,
	})
}

// LogFailure 记录失败的审计日志
func (s *AuditLogService) LogFailure(
	ctx context.Context,
	tenantID, userID string,
	action AuditAction,
	resource string,
	err error,
	details map[string]interface{},
) error {
	return s.Log(ctx, &AuditLog{
		TenantID: tenantID,
		UserID:   userID,
		Action:   action,
		Resource: resource,
		Level:    AuditLevelWarning,
		Status:   "failure",
		Error:    err.Error(),
		Details:  details,
	})
}

// Query 查询审计日志
func (s *AuditLogService) Query(ctx context.Context, filters *AuditLogFilters) ([]*AuditLog, int, error) {
	logs, total, err := s.repo.Query(ctx, filters)
	if err != nil {
		s.log.WithContext(ctx).Errorf("Failed to query audit logs: %v", err)
		return nil, 0, err
	}

	return logs, total, nil
}

// GetByID 根据ID获取审计日志
func (s *AuditLogService) GetByID(ctx context.Context, id string) (*AuditLog, error) {
	log, err := s.repo.GetByID(ctx, id)
	if err != nil {
		s.log.WithContext(ctx).Errorf("Failed to get audit log by ID: %v", err)
		return nil, err
	}

	return log, nil
}

// determineLevel 根据动作类型确定审计级别
func (s *AuditLogService) determineLevel(action AuditAction) AuditLevel {
	criticalActions := map[AuditAction]bool{
		AuditActionUserDelete:      true,
		AuditActionTenantDelete:    true,
		AuditActionPasswordReset:   true,
		AuditActionTokenRevoke:     true,
		AuditActionRoleAssign:      true,
		AuditActionRoleRevoke:      true,
		AuditActionPermissionGrant: true,
		AuditActionPermissionDeny:  true,
	}

	if criticalActions[action] {
		return AuditLevelCritical
	}

	warningActions := map[AuditAction]bool{
		AuditActionPasswordChange: true,
		AuditActionTokenRefresh:   true,
		AuditActionUserUpdate:     true,
		AuditActionTenantUpdate:   true,
	}

	if warningActions[action] {
		return AuditLevelWarning
	}

	return AuditLevelInfo
}

// formatLogMessage 格式化日志消息
func (s *AuditLogService) formatLogMessage(auditLog *AuditLog) string {
	detailsJSON, _ := json.Marshal(auditLog.Details)
	
	msg := map[string]interface{}{
		"audit_id":   auditLog.ID,
		"tenant_id":  auditLog.TenantID,
		"user_id":    auditLog.UserID,
		"action":     auditLog.Action,
		"resource":   auditLog.Resource,
		"status":     auditLog.Status,
		"ip_address": auditLog.IPAddress,
		"user_agent": auditLog.UserAgent,
		"details":    string(detailsJSON),
	}

	if auditLog.Error != "" {
		msg["error"] = auditLog.Error
	}

	msgJSON, _ := json.Marshal(msg)
	return string(msgJSON)
}

// generateAuditLogID 生成审计日志ID
func generateAuditLogID() string {
	return "audit_" + time.Now().Format("20060102150405") + "_" + generateRandomString(8)
}

// generateRandomString 生成随机字符串
func generateRandomString(length int) string {
	// 简化实现，实际应使用crypto/rand
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, length)
	for i := range b {
		b[i] = charset[time.Now().UnixNano()%int64(len(charset))]
	}
	return string(b)
}
