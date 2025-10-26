package biz

import (
	"context"
	"fmt"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/domain"
	pkgErrors "github.com/voicehelper/voiceassistant/pkg/errors"
)

// UserUsecase 用户用例
type UserUsecase struct {
	userRepo   domain.UserRepository
	tenantRepo domain.TenantRepository
	log        *log.Helper
}

// NewUserUsecase 创建用户用例
func NewUserUsecase(
	userRepo domain.UserRepository,
	tenantRepo domain.TenantRepository,
	logger log.Logger,
) *UserUsecase {
	return &UserUsecase{
		userRepo:   userRepo,
		tenantRepo: tenantRepo,
		log:        log.NewHelper(logger),
	}
}

// CreateUser 创建用户
func (uc *UserUsecase) CreateUser(ctx context.Context, email, password, username, tenantID string) (*domain.User, error) {
	uc.log.WithContext(ctx).Infof("Creating user: %s, tenant: %s", email, tenantID)

	// 1. 验证租户
	tenant, err := uc.tenantRepo.GetByID(ctx, tenantID)
	if err != nil {
		return nil, pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	if !tenant.IsActive() {
		return nil, pkgErrors.NewBadRequest("TENANT_INACTIVE", "租户未激活")
	}

	// 2. 检查用户配额
	userCount, err := uc.userRepo.CountByTenantID(ctx, tenantID)
	if err != nil {
		return nil, err
	}

	if !tenant.CanAddUser(userCount) {
		return nil, pkgErrors.NewBadRequest("USER_LIMIT_EXCEEDED", "已达到用户数量上限")
	}

	// 3. 检查邮箱是否已存在
	existingUser, err := uc.userRepo.GetByEmail(ctx, email)
	if err == nil && existingUser != nil {
		return nil, pkgErrors.NewBadRequest("EMAIL_EXISTS", "邮箱已存在")
	}

	// 4. 创建用户
	user, err := domain.NewUser(email, password, username, tenantID)
	if err != nil {
		return nil, pkgErrors.NewInternalServerError("CREATE_USER_FAILED", "创建用户失败")
	}

	// 5. 保存用户
	if err := uc.userRepo.Create(ctx, user); err != nil {
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("User created successfully: %s", user.ID)
	return user, nil
}

// GetUser 获取用户
func (uc *UserUsecase) GetUser(ctx context.Context, id string) (*domain.User, error) {
	user, err := uc.userRepo.GetByID(ctx, id)
	if err != nil {
		return nil, pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}
	return user, nil
}

// GetUserByEmail 根据邮箱获取用户
func (uc *UserUsecase) GetUserByEmail(ctx context.Context, email string) (*domain.User, error) {
	user, err := uc.userRepo.GetByEmail(ctx, email)
	if err != nil {
		return nil, pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}
	return user, nil
}

// UpdateUserProfile 更新用户资料
func (uc *UserUsecase) UpdateUserProfile(ctx context.Context, id, displayName, avatarURL string) (*domain.User, error) {
	// 获取用户
	user, err := uc.userRepo.GetByID(ctx, id)
	if err != nil {
		return nil, pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	// 更新资料
	user.UpdateProfile(displayName, avatarURL)

	// 保存
	if err := uc.userRepo.Update(ctx, user); err != nil {
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("User profile updated: %s", id)
	return user, nil
}

// UpdatePassword 更新密码
func (uc *UserUsecase) UpdatePassword(ctx context.Context, id, oldPassword, newPassword string) error {
	// 获取用户
	user, err := uc.userRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	// 验证旧密码
	if !user.VerifyPassword(oldPassword) {
		return pkgErrors.NewUnauthorized("INVALID_PASSWORD", "密码错误")
	}

	// 更新密码
	if err := user.UpdatePassword(newPassword); err != nil {
		return pkgErrors.NewInternalServerError("UPDATE_PASSWORD_FAILED", "更新密码失败")
	}

	// 保存
	if err := uc.userRepo.Update(ctx, user); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("User password updated: %s", id)
	return nil
}

// DeleteUser 删除用户
func (uc *UserUsecase) DeleteUser(ctx context.Context, id string) error {
	// 检查用户是否存在
	_, err := uc.userRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	// 软删除
	if err := uc.userRepo.Delete(ctx, id); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("User deleted: %s", id)
	return nil
}

// ListUsersByTenant 获取租户下的用户列表
func (uc *UserUsecase) ListUsersByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*domain.User, error) {
	// 验证租户
	_, err := uc.tenantRepo.GetByID(ctx, tenantID)
	if err != nil {
		return nil, pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	// 获取用户列表
	users, err := uc.userRepo.GetByTenantID(ctx, tenantID, offset, limit)
	if err != nil {
		return nil, err
	}

	return users, nil
}

// SuspendUser 暂停用户
func (uc *UserUsecase) SuspendUser(ctx context.Context, id string) error {
	user, err := uc.userRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	user.Suspend()

	if err := uc.userRepo.Update(ctx, user); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("User suspended: %s", id)
	return nil
}

// ActivateUser 激活用户
func (uc *UserUsecase) ActivateUser(ctx context.Context, id string) error {
	user, err := uc.userRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	user.Activate()

	if err := uc.userRepo.Update(ctx, user); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("User activated: %s", id)
	return nil
}

// AssignRole 分配角色
func (uc *UserUsecase) AssignRole(ctx context.Context, userID, role string) error {
	user, err := uc.userRepo.GetByID(ctx, userID)
	if err != nil {
		return pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	user.AddRole(role)

	if err := uc.userRepo.Update(ctx, user); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Role assigned to user %s: %s", userID, role)
	return nil
}

// RemoveRole 移除角色
func (uc *UserUsecase) RemoveRole(ctx context.Context, userID, role string) error {
	user, err := uc.userRepo.GetByID(ctx, userID)
	if err != nil {
		return pkgErrors.NewNotFound("USER_NOT_FOUND", "用户不存在")
	}

	user.RemoveRole(role)

	if err := uc.userRepo.Update(ctx, user); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Role removed from user %s: %s", userID, role)
	return nil
}
