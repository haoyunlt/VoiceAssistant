package domain

import "time"

// Permission 权限
type Permission struct {
	Resource   string                 // 资源：kb:123, doc:456
	Action     string                 // 操作：read, write, delete, admin
	Effect     string                 // 效果：allow, deny
	Conditions map[string]interface{} // 条件
}

// Role 角色
type Role struct {
	ID          string
	Name        string
	Description string
	Permissions []Permission
	TenantID    string
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// UserRole 用户角色关联
type UserRole struct {
	ID        string
	UserID    string
	RoleID    string
	TenantID  string
	Resource  string    // 可选：限定角色作用的资源范围
	CreatedAt time.Time
	ExpiresAt *time.Time // 可选：角色过期时间
}

// AuditLog 审计日志
type AuditLog struct {
	ID         string
	TenantID   string
	UserID     string
	Action     string // 操作：create_kb, delete_doc, rollback_version
	Resource   string // 资源
	Details    string // 详细信息（JSON）
	IP         string
	UserAgent  string
	Status     string // 状态：success, failed
	Error      string // 错误信息
	CreatedAt  time.Time
}

// ResourceType 资源类型
type ResourceType string

const (
	ResourceTypeKnowledgeBase ResourceType = "kb"
	ResourceTypeDocument      ResourceType = "doc"
	ResourceTypeChunk         ResourceType = "chunk"
	ResourceTypeVersion       ResourceType = "version"
)

// Action 操作类型
type Action string

const (
	ActionRead   Action = "read"
	ActionWrite  Action = "write"
	ActionDelete Action = "delete"
	ActionAdmin  Action = "admin"
)

// Effect 效果
type Effect string

const (
	EffectAllow Effect = "allow"
	EffectDeny  Effect = "deny"
)

// PermissionRepository 权限仓库
type PermissionRepository interface {
	// GetUserRoles 获取用户的所有角色
	GetUserRoles(ctx interface{}, userID, tenantID string) ([]*Role, error)

	// CheckPermission 检查权限
	CheckPermission(ctx interface{}, userID, resource, action string) (bool, error)

	// GrantRole 授予角色
	GrantRole(ctx interface{}, userRole *UserRole) error

	// RevokeRole 撤销角色
	RevokeRole(ctx interface{}, userID, roleID string) error
}

// AuditLogRepository 审计日志仓库
type AuditLogRepository interface {
	// Create 创建审计日志
	Create(ctx interface{}, log *AuditLog) error

	// List 列出审计日志
	List(ctx interface{}, tenantID string, filters map[string]interface{}, offset, limit int) ([]*AuditLog, int64, error)
}

// NewAuditLog 创建审计日志
func NewAuditLog(
	tenantID, userID, action, resource, details, ip, userAgent, status, errorMsg string,
) *AuditLog {
	return &AuditLog{
		ID:        generateID(),
		TenantID:  tenantID,
		UserID:    userID,
		Action:    action,
		Resource:  resource,
		Details:   details,
		IP:        ip,
		UserAgent: userAgent,
		Status:    status,
		Error:     errorMsg,
		CreatedAt: time.Now(),
	}
}
