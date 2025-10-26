package domain

import (
	"context"
)

// UserRepository 用户仓储接口
type UserRepository interface {
	// Create 创建用户
	Create(ctx context.Context, user *User) error

	// GetByID 根据ID获取用户
	GetByID(ctx context.Context, id string) (*User, error)

	// GetByEmail 根据邮箱获取用户
	GetByEmail(ctx context.Context, email string) (*User, error)

	// GetByTenantID 根据租户ID获取用户列表
	GetByTenantID(ctx context.Context, tenantID string, offset, limit int) ([]*User, error)

	// Update 更新用户
	Update(ctx context.Context, user *User) error

	// Delete 删除用户（软删除）
	Delete(ctx context.Context, id string) error

	// CountByTenantID 统计租户下的用户数量
	CountByTenantID(ctx context.Context, tenantID string) (int, error)
}

// TenantRepository 租户仓储接口
type TenantRepository interface {
	// Create 创建租户
	Create(ctx context.Context, tenant *Tenant) error

	// GetByID 根据ID获取租户
	GetByID(ctx context.Context, id string) (*Tenant, error)

	// GetByName 根据名称获取租户
	GetByName(ctx context.Context, name string) (*Tenant, error)

	// List 获取租户列表
	List(ctx context.Context, offset, limit int) ([]*Tenant, error)

	// Update 更新租户
	Update(ctx context.Context, tenant *Tenant) error

	// Delete 删除租户
	Delete(ctx context.Context, id string) error
}
