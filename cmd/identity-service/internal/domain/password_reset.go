package domain

import "time"

// ResetToken 密码重置令牌
type ResetToken struct {
	ID        string
	UserID    string
	Token     string
	ExpiresAt time.Time
	Used      bool
	CreatedAt time.Time
}

// NewResetToken 创建重置令牌
func NewResetToken(userID string, token string, ttl time.Duration) *ResetToken {
	return &ResetToken{
		ID:        generateID(),
		UserID:    userID,
		Token:     token,
		ExpiresAt: time.Now().Add(ttl),
		Used:      false,
		CreatedAt: time.Now(),
	}
}

// IsExpired 检查是否过期
func (t *ResetToken) IsExpired() bool {
	return time.Now().After(t.ExpiresAt)
}

// MarkUsed 标记为已使用
func (t *ResetToken) MarkUsed() {
	t.Used = true
}

// ResetTokenRepository 密码重置令牌仓储接口
type ResetTokenRepository interface {
	Create(token *ResetToken) error
	GetByToken(token string) (*ResetToken, error)
	Delete(id string) error
	DeleteByUserID(userID string) error
	MarkUsed(id string) error
}
