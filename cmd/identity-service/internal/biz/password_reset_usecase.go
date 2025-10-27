package biz

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"time"

	"github.com/VoiceAssistant/cmd/identity-service/internal/domain"
)

var (
	ErrInvalidResetToken = errors.New("invalid reset token")
	ErrResetTokenExpired = errors.New("reset token expired")
	ErrResetTokenUsed    = errors.New("reset token already used")
)

// EmailService 邮件服务接口
type EmailService interface {
	SendPasswordResetEmail(to, resetURL string) error
}

// PasswordResetUsecase 密码重置用例
type PasswordResetUsecase struct {
	userRepo       domain.UserRepository
	resetTokenRepo domain.ResetTokenRepository
	emailService   EmailService
}

// NewPasswordResetUsecase 创建密码重置用例
func NewPasswordResetUsecase(
	userRepo domain.UserRepository,
	resetTokenRepo domain.ResetTokenRepository,
	emailService EmailService,
) *PasswordResetUsecase {
	return &PasswordResetUsecase{
		userRepo:       userRepo,
		resetTokenRepo: resetTokenRepo,
		emailService:   emailService,
	}
}

// RequestPasswordReset 请求密码重置
func (uc *PasswordResetUsecase) RequestPasswordReset(
	ctx context.Context,
	email string,
) error {
	// 1. 查找用户
	user, err := uc.userRepo.GetByEmail(ctx, email)
	if err != nil {
		// 安全考虑：即使用户不存在也返回成功，防止枚举
		return nil
	}

	// 2. 删除该用户之前未使用的重置令牌
	uc.resetTokenRepo.DeleteByUserID(user.ID)

	// 3. 生成重置Token
	token, err := generateSecureToken(32)
	if err != nil {
		return fmt.Errorf("generate token: %w", err)
	}

	resetToken := domain.NewResetToken(user.ID, token, 1*time.Hour)

	if err := uc.resetTokenRepo.Create(resetToken); err != nil {
		return fmt.Errorf("create reset token: %w", err)
	}

	// 4. 发送重置邮件
	resetURL := fmt.Sprintf("https://app.voiceassistant.ai/reset-password?token=%s", token)
	if err := uc.emailService.SendPasswordResetEmail(user.Email, resetURL); err != nil {
		return fmt.Errorf("send email: %w", err)
	}

	return nil
}

// ResetPassword 重置密码
func (uc *PasswordResetUsecase) ResetPassword(
	ctx context.Context,
	token string,
	newPassword string,
) error {
	// 1. 验证Token
	resetToken, err := uc.resetTokenRepo.GetByToken(token)
	if err != nil {
		return ErrInvalidResetToken
	}

	// 2. 检查是否过期
	if resetToken.IsExpired() {
		return ErrResetTokenExpired
	}

	// 3. 检查是否已使用
	if resetToken.Used {
		return ErrResetTokenUsed
	}

	// 4. 获取用户
	user, err := uc.userRepo.GetByID(ctx, resetToken.UserID)
	if err != nil {
		return fmt.Errorf("get user: %w", err)
	}

	// 5. 验证新密码
	if len(newPassword) < 8 {
		return errors.New("password must be at least 8 characters")
	}

	// 6. 更新密码
	if err := user.UpdatePassword(newPassword); err != nil {
		return fmt.Errorf("update password: %w", err)
	}

	if err := uc.userRepo.Update(ctx, user); err != nil {
		return fmt.Errorf("save user: %w", err)
	}

	// 7. 标记Token为已使用
	if err := uc.resetTokenRepo.MarkUsed(resetToken.ID); err != nil {
		return fmt.Errorf("mark token used: %w", err)
	}

	return nil
}

// VerifyResetToken 验证重置令牌（用于前端验证）
func (uc *PasswordResetUsecase) VerifyResetToken(
	ctx context.Context,
	token string,
) error {
	resetToken, err := uc.resetTokenRepo.GetByToken(token)
	if err != nil {
		return ErrInvalidResetToken
	}

	if resetToken.IsExpired() {
		return ErrResetTokenExpired
	}

	if resetToken.Used {
		return ErrResetTokenUsed
	}

	return nil
}

// generateSecureToken 生成安全的随机令牌
func generateSecureToken(length int) (string, error) {
	bytes := make([]byte, length)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}
