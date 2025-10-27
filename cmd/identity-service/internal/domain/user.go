package domain

import (
	"time"

	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

// UserStatus 用户状态
type UserStatus string

const (
	UserStatusActive    UserStatus = "active"
	UserStatusInactive  UserStatus = "inactive"
	UserStatusSuspended UserStatus = "suspended"
	UserStatusDeleted   UserStatus = "deleted"
)

// User 用户聚合根
type User struct {
	ID          string
	Email       string
	Username    string
	DisplayName string
	AvatarURL   string
	PasswordHash string
	TenantID    string
	Roles       []string
	Status      UserStatus
	CreatedAt   time.Time
	UpdatedAt   time.Time
	LastLoginAt *time.Time
}

// NewUser 创建新用户
func NewUser(email, password, username, tenantID string) (*User, error) {
	// 验证邮箱格式
	if err := ValidateEmail(email); err != nil {
		return nil, err
	}

	// 验证密码强度
	if err := ValidatePassword(password, DefaultPasswordPolicy); err != nil {
		return nil, err
	}

	// 生成用户ID
	id := "usr_" + uuid.New().String()

	// 加密密码
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}

	now := time.Now()
	return &User{
		ID:           id,
		Email:        email,
		Username:     username,
		DisplayName:  username,
		PasswordHash: string(hashedPassword),
		TenantID:     tenantID,
		Roles:        []string{"user"}, // 默认角色
		Status:       UserStatusActive,
		CreatedAt:    now,
		UpdatedAt:    now,
	}, nil
}

// VerifyPassword 验证密码
func (u *User) VerifyPassword(password string) bool {
	err := bcrypt.CompareHashAndPassword([]byte(u.PasswordHash), []byte(password))
	return err == nil
}

// UpdatePassword 更新密码
func (u *User) UpdatePassword(newPassword string) error {
	// 验证新密码强度
	if err := ValidatePassword(newPassword, DefaultPasswordPolicy); err != nil {
		return err
	}

	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(newPassword), bcrypt.DefaultCost)
	if err != nil {
		return err
	}
	u.PasswordHash = string(hashedPassword)
	u.UpdatedAt = time.Now()
	return nil
}

// UpdateProfile 更新用户资料
func (u *User) UpdateProfile(displayName, avatarURL string) {
	if displayName != "" {
		u.DisplayName = displayName
	}
	if avatarURL != "" {
		u.AvatarURL = avatarURL
	}
	u.UpdatedAt = time.Now()
}

// RecordLogin 记录登录时间
func (u *User) RecordLogin() {
	now := time.Now()
	u.LastLoginAt = &now
	u.UpdatedAt = now
}

// IsActive 检查用户是否活跃
func (u *User) IsActive() bool {
	return u.Status == UserStatusActive
}

// Suspend 暂停用户
func (u *User) Suspend() {
	u.Status = UserStatusSuspended
	u.UpdatedAt = time.Now()
}

// Activate 激活用户
func (u *User) Activate() {
	u.Status = UserStatusActive
	u.UpdatedAt = time.Now()
}

// HasRole 检查用户是否拥有指定角色
func (u *User) HasRole(role string) bool {
	for _, r := range u.Roles {
		if r == role {
			return true
		}
	}
	return false
}

// AddRole 添加角色
func (u *User) AddRole(role string) {
	if !u.HasRole(role) {
		u.Roles = append(u.Roles, role)
		u.UpdatedAt = time.Now()
	}
}

// RemoveRole 移除角色
func (u *User) RemoveRole(role string) {
	roles := make([]string, 0, len(u.Roles))
	for _, r := range u.Roles {
		if r != role {
			roles = append(roles, r)
		}
	}
	u.Roles = roles
	u.UpdatedAt = time.Now()
}
