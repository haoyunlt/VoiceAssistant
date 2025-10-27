package data

import (
	"time"

	"gorm.io/gorm"

	"voiceassistant/cmd/model-router/internal/domain"
)

type budgetRepo struct {
	db *gorm.DB
}

func NewBudgetRepository(db *gorm.DB) domain.BudgetRepository {
	return &budgetRepo{db: db}
}

func (r *budgetRepo) GetByTenant(tenantID string) (*domain.TenantBudget, error) {
	var budget domain.TenantBudget
	err := r.db.Where("tenant_id = ?", tenantID).First(&budget).Error
	if err == gorm.ErrRecordNotFound {
		// Create default budget
		budget = domain.TenantBudget{
			TenantID:       tenantID,
			DailyLimit:     100.0,  // $100/day
			MonthlyLimit:   3000.0, // $3000/month
			DailyUsed:      0,
			MonthlyUsed:    0,
			AlertThreshold: 0.8, // 80%
			LastResetDate:  time.Now(),
			UpdatedAt:      time.Now(),
		}
		if err := r.db.Create(&budget).Error; err != nil {
			return nil, err
		}
		return &budget, nil
	}
	if err != nil {
		return nil, err
	}

	// Check if need to reset daily/monthly usage
	now := time.Now()
	if now.Day() != budget.LastResetDate.Day() {
		budget.DailyUsed = 0
		budget.LastResetDate = now
	}
	if now.Month() != budget.LastResetDate.Month() {
		budget.MonthlyUsed = 0
		budget.LastResetDate = now
	}

	if budget.DailyUsed == 0 || budget.MonthlyUsed == 0 {
		r.db.Save(&budget)
	}

	return &budget, nil
}

func (r *budgetRepo) Update(budget *domain.TenantBudget) error {
	budget.UpdatedAt = time.Now()
	return r.db.Save(budget).Error
}

func (r *budgetRepo) AddUsage(tenantID string, cost float64) error {
	return r.db.Model(&domain.TenantBudget{}).
		Where("tenant_id = ?", tenantID).
		Updates(map[string]interface{}{
			"daily_used":   gorm.Expr("daily_used + ?", cost),
			"monthly_used": gorm.Expr("monthly_used + ?", cost),
			"updated_at":   time.Now(),
		}).Error
}

func (r *budgetRepo) CheckBudget(tenantID string, estimatedCost float64) (bool, error) {
	budget, err := r.GetByTenant(tenantID)
	if err != nil {
		return false, err
	}

	// Check daily limit
	if budget.DailyUsed+estimatedCost > budget.DailyLimit {
		return false, nil
	}

	// Check monthly limit
	if budget.MonthlyUsed+estimatedCost > budget.MonthlyLimit {
		return false, nil
	}

	return true, nil
}

