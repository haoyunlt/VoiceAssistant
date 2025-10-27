package domain

import "time"

// TenantBudget 租户预算
type TenantBudget struct {
	ID             string
	TenantID       string
	DailyLimit     float64
	MonthlyLimit   float64
	DailyUsed      float64
	MonthlyUsed    float64
	AlertThreshold float64
	IsActive       bool
	LastResetDate  time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// BudgetRepository 预算仓储接口
type BudgetRepository interface {
	GetByTenant(tenantID string) (*TenantBudget, error)
	Update(budget *TenantBudget) error
	AddUsage(tenantID string, cost float64) error
}
