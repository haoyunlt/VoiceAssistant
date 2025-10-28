package data

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	_ "github.com/lib/pq"
)

// UserRepositoryImpl PostgreSQL实现
type UserRepositoryImpl struct {
	db  *sql.DB
	log *log.Helper
}

// NewUserRepository 创建UserRepository实例
func NewUserRepository(db *sql.DB, logger log.Logger) *UserRepositoryImpl {
	return &UserRepositoryImpl{
		db:  db,
		log: log.NewHelper(logger),
	}
}

// User 用户模型
type User struct {
	ID        string
	TenantID  string
	Email     string
	Name      string
	Status    string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// ListByTenant 根据租户ID列出用户
func (r *UserRepositoryImpl) ListByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*User, error) {
	query := `
		SELECT id, tenant_id, email, name, status, created_at, updated_at
		FROM users
		WHERE tenant_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := r.db.QueryContext(ctx, query, tenantID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to query users: %w", err)
	}
	defer rows.Close()

	users := make([]*User, 0)
	for rows.Next() {
		var user User
		if err := rows.Scan(
			&user.ID,
			&user.TenantID,
			&user.Email,
			&user.Name,
			&user.Status,
			&user.CreatedAt,
			&user.UpdatedAt,
		); err != nil {
			r.log.Warnf("Failed to scan user row: %v", err)
			continue
		}
		users = append(users, &user)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}

	return users, nil
}

// DeleteByTenantID 删除租户下的所有用户
func (r *UserRepositoryImpl) DeleteByTenantID(ctx context.Context, tenantID string) (int64, error) {
	query := `DELETE FROM users WHERE tenant_id = $1`

	result, err := r.db.ExecContext(ctx, query, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to delete users: %w", err)
	}

	count, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected: %w", err)
	}

	r.log.Infof("Deleted %d users for tenant %s", count, tenantID)
	return count, nil
}

// CountByTenant 统计租户下的用户数
func (r *UserRepositoryImpl) CountByTenant(ctx context.Context, tenantID string) (int64, error) {
	query := `SELECT COUNT(*) FROM users WHERE tenant_id = $1`

	var count int64
	if err := r.db.QueryRowContext(ctx, query, tenantID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count users: %w", err)
	}

	return count, nil
}

// GetByID 根据ID获取用户
func (r *UserRepositoryImpl) GetByID(ctx context.Context, userID string) (*User, error) {
	query := `
		SELECT id, tenant_id, email, name, status, created_at, updated_at
		FROM users
		WHERE id = $1
	`

	var user User
	if err := r.db.QueryRowContext(ctx, query, userID).Scan(
		&user.ID,
		&user.TenantID,
		&user.Email,
		&user.Name,
		&user.Status,
		&user.CreatedAt,
		&user.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("user not found: %s", userID)
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	return &user, nil
}

// Create 创建用户
func (r *UserRepositoryImpl) Create(ctx context.Context, user *User) error {
	query := `
		INSERT INTO users (id, tenant_id, email, name, status, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	now := time.Now()
	if user.CreatedAt.IsZero() {
		user.CreatedAt = now
	}
	if user.UpdatedAt.IsZero() {
		user.UpdatedAt = now
	}

	_, err := r.db.ExecContext(ctx, query,
		user.ID,
		user.TenantID,
		user.Email,
		user.Name,
		user.Status,
		user.CreatedAt,
		user.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}

	r.log.Infof("Created user: %s for tenant: %s", user.ID, user.TenantID)
	return nil
}

// Update 更新用户
func (r *UserRepositoryImpl) Update(ctx context.Context, user *User) error {
	query := `
		UPDATE users
		SET email = $2, name = $3, status = $4, updated_at = $5
		WHERE id = $1
	`

	user.UpdatedAt = time.Now()

	result, err := r.db.ExecContext(ctx, query,
		user.ID,
		user.Email,
		user.Name,
		user.Status,
		user.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to update user: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("user not found: %s", user.ID)
	}

	r.log.Infof("Updated user: %s", user.ID)
	return nil
}
