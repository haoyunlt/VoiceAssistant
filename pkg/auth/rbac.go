package auth

import (
	"fmt"
	"sync"
)

// Role represents a user role
type Role string

const (
	RoleAdmin     Role = "admin"
	RoleUser      Role = "user"
	RoleDeveloper Role = "developer"
	RoleGuest     Role = "guest"
)

// Permission represents a permission
type Permission string

const (
	// User permissions
	PermissionReadUser   Permission = "user:read"
	PermissionWriteUser  Permission = "user:write"
	PermissionDeleteUser Permission = "user:delete"

	// Chat permissions
	PermissionChat        Permission = "chat:use"
	PermissionChatHistory Permission = "chat:history"

	// Knowledge Graph permissions
	PermissionReadKG   Permission = "kg:read"
	PermissionWriteKG  Permission = "kg:write"
	PermissionDeleteKG Permission = "kg:delete"

	// RAG permissions
	PermissionUseRAG    Permission = "rag:use"
	PermissionManageRAG Permission = "rag:manage"

	// Agent permissions
	PermissionUseAgent    Permission = "agent:use"
	PermissionManageAgent Permission = "agent:manage"

	// System permissions
	PermissionReadMetrics  Permission = "system:metrics"
	PermissionManageSystem Permission = "system:manage"
)

// RBACManager manages role-based access control
type RBACManager struct {
	mu              sync.RWMutex
	rolePermissions map[Role][]Permission
}

// NewRBACManager creates a new RBAC manager
func NewRBACManager() *RBACManager {
	manager := &RBACManager{
		rolePermissions: make(map[Role][]Permission),
	}
	manager.initializeDefaultRoles()
	return manager
}

// initializeDefaultRoles initializes default role permissions
func (m *RBACManager) initializeDefaultRoles() {
	// Admin - Full access
	m.rolePermissions[RoleAdmin] = []Permission{
		PermissionReadUser,
		PermissionWriteUser,
		PermissionDeleteUser,
		PermissionChat,
		PermissionChatHistory,
		PermissionReadKG,
		PermissionWriteKG,
		PermissionDeleteKG,
		PermissionUseRAG,
		PermissionManageRAG,
		PermissionUseAgent,
		PermissionManageAgent,
		PermissionReadMetrics,
		PermissionManageSystem,
	}

	// Developer - Development access
	m.rolePermissions[RoleDeveloper] = []Permission{
		PermissionReadUser,
		PermissionChat,
		PermissionChatHistory,
		PermissionReadKG,
		PermissionWriteKG,
		PermissionUseRAG,
		PermissionManageRAG,
		PermissionUseAgent,
		PermissionManageAgent,
		PermissionReadMetrics,
	}

	// User - Standard user access
	m.rolePermissions[RoleUser] = []Permission{
		PermissionReadUser,
		PermissionChat,
		PermissionChatHistory,
		PermissionReadKG,
		PermissionUseRAG,
		PermissionUseAgent,
	}

	// Guest - Limited access
	m.rolePermissions[RoleGuest] = []Permission{
		PermissionChat,
		PermissionReadKG,
	}
}

// HasPermission checks if a role has a specific permission
func (m *RBACManager) HasPermission(role Role, permission Permission) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()

	permissions, exists := m.rolePermissions[role]
	if !exists {
		return false
	}

	for _, p := range permissions {
		if p == permission {
			return true
		}
	}
	return false
}

// HasAnyPermission checks if a role has any of the specified permissions
func (m *RBACManager) HasAnyPermission(role Role, permissions ...Permission) bool {
	for _, permission := range permissions {
		if m.HasPermission(role, permission) {
			return true
		}
	}
	return false
}

// HasAllPermissions checks if a role has all of the specified permissions
func (m *RBACManager) HasAllPermissions(role Role, permissions ...Permission) bool {
	for _, permission := range permissions {
		if !m.HasPermission(role, permission) {
			return false
		}
	}
	return true
}

// CheckUserPermission checks if a user (with multiple roles) has a permission
func (m *RBACManager) CheckUserPermission(roles []string, permission Permission) bool {
	for _, roleStr := range roles {
		role := Role(roleStr)
		if m.HasPermission(role, permission) {
			return true
		}
	}
	return false
}

// CheckUserPermissions checks if a user has all specified permissions
func (m *RBACManager) CheckUserPermissions(roles []string, permissions ...Permission) bool {
	for _, permission := range permissions {
		hasPermission := false
		for _, roleStr := range roles {
			role := Role(roleStr)
			if m.HasPermission(role, permission) {
				hasPermission = true
				break
			}
		}
		if !hasPermission {
			return false
		}
	}
	return true
}

// AddPermissionToRole adds a permission to a role
func (m *RBACManager) AddPermissionToRole(role Role, permission Permission) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if permissions, exists := m.rolePermissions[role]; exists {
		// Check if permission already exists
		for _, p := range permissions {
			if p == permission {
				return
			}
		}
		m.rolePermissions[role] = append(permissions, permission)
	} else {
		m.rolePermissions[role] = []Permission{permission}
	}
}

// RemovePermissionFromRole removes a permission from a role
func (m *RBACManager) RemovePermissionFromRole(role Role, permission Permission) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if permissions, exists := m.rolePermissions[role]; exists {
		newPermissions := make([]Permission, 0, len(permissions))
		for _, p := range permissions {
			if p != permission {
				newPermissions = append(newPermissions, p)
			}
		}
		m.rolePermissions[role] = newPermissions
	}
}

// GetRolePermissions returns all permissions for a role
func (m *RBACManager) GetRolePermissions(role Role) []Permission {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if permissions, exists := m.rolePermissions[role]; exists {
		// Return a copy to prevent external modification
		result := make([]Permission, len(permissions))
		copy(result, permissions)
		return result
	}
	return []Permission{}
}

// ValidateRole checks if a role is valid
func (m *RBACManager) ValidateRole(role string) error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	r := Role(role)
	if _, exists := m.rolePermissions[r]; !exists {
		return fmt.Errorf("invalid role: %s", role)
	}
	return nil
}
