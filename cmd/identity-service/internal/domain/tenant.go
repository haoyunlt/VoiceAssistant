package domain

import (
	"time"

	"github.com/google/uuid"
)

// TenantStatus 租户状态
type TenantStatus string

const (
	TenantStatusActive    TenantStatus = "active"
	TenantStatusSuspended TenantStatus = "suspended"
	TenantStatusDeleted   TenantStatus = "deleted"
)

// TenantPlan 租户计划
type TenantPlan string

const (
	TenantPlanFree       TenantPlan = "free"
	TenantPlanBasic      TenantPlan = "basic"
	TenantPlanPro        TenantPlan = "pro"
	TenantPlanEnterprise TenantPlan = "enterprise"
)

// Tenant 租户聚合根
type Tenant struct {
	ID          string
	Name        string
	DisplayName string
	Plan        TenantPlan
	Status      TenantStatus
	MaxUsers    int
	Settings    map[string]interface{}
	CreatedAt   time.Time
	UpdatedAt   time.Time
	ExpiresAt   *time.Time
}

// NewTenant 创建新租户
func NewTenant(name, displayName string, plan TenantPlan) *Tenant {
	id := "tenant_" + uuid.New().String()
	now := time.Now()

	maxUsers := 5 // 默认最大用户数
	switch plan {
	case TenantPlanBasic:
		maxUsers = 20
	case TenantPlanPro:
		maxUsers = 100
	case TenantPlanEnterprise:
		maxUsers = -1 // 无限制
	}

	return &Tenant{
		ID:          id,
		Name:        name,
		DisplayName: displayName,
		Plan:        plan,
		Status:      TenantStatusActive,
		MaxUsers:    maxUsers,
		Settings:    make(map[string]interface{}),
		CreatedAt:   now,
		UpdatedAt:   now,
	}
}

// IsActive 检查租户是否活跃
func (t *Tenant) IsActive() bool {
	if t.Status != TenantStatusActive {
		return false
	}
	if t.ExpiresAt != nil && time.Now().After(*t.ExpiresAt) {
		return false
	}
	return true
}

// Suspend 暂停租户
func (t *Tenant) Suspend() {
	t.Status = TenantStatusSuspended
	t.UpdatedAt = time.Now()
}

// Activate 激活租户
func (t *Tenant) Activate() {
	t.Status = TenantStatusActive
	t.UpdatedAt = time.Now()
}

// UpgradePlan 升级计划
func (t *Tenant) UpgradePlan(plan TenantPlan) {
	t.Plan = plan
	switch plan {
	case TenantPlanBasic:
		t.MaxUsers = 20
	case TenantPlanPro:
		t.MaxUsers = 100
	case TenantPlanEnterprise:
		t.MaxUsers = -1
	}
	t.UpdatedAt = time.Now()
}

// UpdateSettings 更新设置
func (t *Tenant) UpdateSettings(key string, value interface{}) {
	if t.Settings == nil {
		t.Settings = make(map[string]interface{})
	}
	t.Settings[key] = value
	t.UpdatedAt = time.Now()
}

// GetSetting 获取设置
func (t *Tenant) GetSetting(key string) (interface{}, bool) {
	if t.Settings == nil {
		return nil, false
	}
	value, ok := t.Settings[key]
	return value, ok
}

// CanAddUser 检查是否可以添加用户
func (t *Tenant) CanAddUser(currentUserCount int) bool {
	if !t.IsActive() {
		return false
	}
	if t.MaxUsers == -1 {
		return true
	}
	return currentUserCount < t.MaxUsers
}
