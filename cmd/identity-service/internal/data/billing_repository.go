package data

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"github.com/go-kratos/kratos/v2/log"
)

// BillingRepositoryImpl ClickHouse实现
type BillingRepositoryImpl struct {
	conn driver.Conn
	log  *log.Helper
}

// NewBillingRepository 创建BillingRepository实例
func NewBillingRepository(conn driver.Conn, logger log.Logger) *BillingRepositoryImpl {
	return &BillingRepositoryImpl{
		conn: conn,
		log:  log.NewHelper(logger),
	}
}

// UsageSummary 使用量摘要
type UsageSummary struct {
	TotalCalls      int64     `json:"total_calls"`
	TotalTokens     int64     `json:"total_tokens"`
	TotalCost       float64   `json:"total_cost"`
	UnpaidAmount    float64   `json:"unpaid_amount"`
	LastBillingDate time.Time `json:"last_billing_date"`
}

// HasUnpaidBillsByTenantID 检查租户是否有未支付账单
func (r *BillingRepositoryImpl) HasUnpaidBillsByTenantID(ctx context.Context, tenantID string) (bool, float64, error) {
	query := `
		SELECT SUM(amount) as unpaid_amount
		FROM billing_records
		WHERE tenant_id = ? AND status = 'unpaid'
	`

	var unpaidAmount float64
	if err := r.conn.QueryRow(ctx, query, tenantID).Scan(&unpaidAmount); err != nil {
		if err == sql.ErrNoRows {
			return false, 0, nil
		}
		return false, 0, fmt.Errorf("failed to query unpaid bills: %w", err)
	}

	hasUnpaid := unpaidAmount > 0
	return hasUnpaid, unpaidAmount, nil
}

// GetUsageSummary 获取租户使用量摘要
func (r *BillingRepositoryImpl) GetUsageSummary(ctx context.Context, tenantID string) (*UsageSummary, error) {
	query := `
		SELECT
			COUNT(*) as total_calls,
			SUM(total_tokens) as total_tokens,
			SUM(cost) as total_cost,
			SUM(CASE WHEN status = 'unpaid' THEN amount ELSE 0 END) as unpaid_amount,
			MAX(billing_date) as last_billing_date
		FROM billing_records
		WHERE tenant_id = ?
	`

	var summary UsageSummary
	if err := r.conn.QueryRow(ctx, query, tenantID).Scan(
		&summary.TotalCalls,
		&summary.TotalTokens,
		&summary.TotalCost,
		&summary.UnpaidAmount,
		&summary.LastBillingDate,
	); err != nil {
		return nil, fmt.Errorf("failed to get usage summary: %w", err)
	}

	return &summary, nil
}

// RecordUsage 记录使用量
func (r *BillingRepositoryImpl) RecordUsage(ctx context.Context, tenantID string, tokens int64, cost float64) error {
	query := `
		INSERT INTO billing_records (
			tenant_id, timestamp, total_tokens, cost, amount, status, billing_date
		) VALUES (?, ?, ?, ?, ?, ?, ?)
	`

	now := time.Now()
	err := r.conn.Exec(ctx, query,
		tenantID,
		now,
		tokens,
		cost,
		cost, // amount equals cost for now
		"unpaid",
		now,
	)
	if err != nil {
		return fmt.Errorf("failed to record usage: %w", err)
	}

	r.log.Infof("Recorded usage for tenant %s: tokens=%d, cost=%.4f", tenantID, tokens, cost)
	return nil
}

// MarkBillsPaid 标记账单为已支付
func (r *BillingRepositoryImpl) MarkBillsPaid(ctx context.Context, tenantID string) error {
	query := `
		ALTER TABLE billing_records
		UPDATE status = 'paid'
		WHERE tenant_id = ? AND status = 'unpaid'
	`

	err := r.conn.Exec(ctx, query, tenantID)
	if err != nil {
		return fmt.Errorf("failed to mark bills paid: %w", err)
	}

	r.log.Infof("Marked bills paid for tenant %s", tenantID)
	return nil
}

// GetDailyUsage 获取每日使用量
func (r *BillingRepositoryImpl) GetDailyUsage(ctx context.Context, tenantID string, startDate, endDate time.Time) ([]map[string]interface{}, error) {
	query := `
		SELECT
			toDate(timestamp) as date,
			COUNT(*) as calls,
			SUM(total_tokens) as tokens,
			SUM(cost) as cost
		FROM billing_records
		WHERE tenant_id = ?
			AND timestamp >= ?
			AND timestamp < ?
		GROUP BY date
		ORDER BY date DESC
	`

	rows, err := r.conn.Query(ctx, query, tenantID, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query daily usage: %w", err)
	}
	defer rows.Close()

	results := make([]map[string]interface{}, 0)
	for rows.Next() {
		var date time.Time
		var calls int64
		var tokens int64
		var cost float64

		if err := rows.Scan(&date, &calls, &tokens, &cost); err != nil {
			r.log.Warnf("Failed to scan row: %v", err)
			continue
		}

		results = append(results, map[string]interface{}{
			"date":   date.Format("2006-01-02"),
			"calls":  calls,
			"tokens": tokens,
			"cost":   cost,
		})
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}

	return results, nil
}
