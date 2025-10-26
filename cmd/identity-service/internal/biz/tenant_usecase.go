package biz

import (
	"context"

	"voiceassistant/cmd/identity-service/internal/domain"
	pkgErrors "voiceassistant/pkg/errors"

	"github.com/go-kratos/kratos/v2/log"
)

// TenantUsecase 租户用例
type TenantUsecase struct {
	tenantRepo domain.TenantRepository
	log        *log.Helper
}

// NewTenantUsecase 创建租户用例
func NewTenantUsecase(
	tenantRepo domain.TenantRepository,
	logger log.Logger,
) *TenantUsecase {
	return &TenantUsecase{
		tenantRepo: tenantRepo,
		log:        log.NewHelper(logger),
	}
}

// CreateTenant 创建租户
func (uc *TenantUsecase) CreateTenant(ctx context.Context, name, displayName string, plan domain.TenantPlan) (*domain.Tenant, error) {
	uc.log.WithContext(ctx).Infof("Creating tenant: %s", name)

	// 检查名称是否已存在
	existingTenant, err := uc.tenantRepo.GetByName(ctx, name)
	if err == nil && existingTenant != nil {
		return nil, pkgErrors.NewBadRequest("TENANT_EXISTS", "租户名称已存在")
	}

	// 创建租户
	tenant := domain.NewTenant(name, displayName, plan)

	// 保存
	if err := uc.tenantRepo.Create(ctx, tenant); err != nil {
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("Tenant created successfully: %s", tenant.ID)
	return tenant, nil
}

// GetTenant 获取租户
func (uc *TenantUsecase) GetTenant(ctx context.Context, id string) (*domain.Tenant, error) {
	tenant, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return nil, pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}
	return tenant, nil
}

// GetTenantByName 根据名称获取租户
func (uc *TenantUsecase) GetTenantByName(ctx context.Context, name string) (*domain.Tenant, error) {
	tenant, err := uc.tenantRepo.GetByName(ctx, name)
	if err != nil {
		return nil, pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}
	return tenant, nil
}

// ListTenants 获取租户列表
func (uc *TenantUsecase) ListTenants(ctx context.Context, offset, limit int) ([]*domain.Tenant, error) {
	tenants, err := uc.tenantRepo.List(ctx, offset, limit)
	if err != nil {
		return nil, err
	}
	return tenants, nil
}

// UpdateTenant 更新租户
func (uc *TenantUsecase) UpdateTenant(ctx context.Context, id, displayName string) (*domain.Tenant, error) {
	tenant, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return nil, pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	if displayName != "" {
		tenant.DisplayName = displayName
	}

	if err := uc.tenantRepo.Update(ctx, tenant); err != nil {
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("Tenant updated: %s", id)
	return tenant, nil
}

// SuspendTenant 暂停租户
func (uc *TenantUsecase) SuspendTenant(ctx context.Context, id string) error {
	tenant, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	tenant.Suspend()

	if err := uc.tenantRepo.Update(ctx, tenant); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Tenant suspended: %s", id)
	return nil
}

// ActivateTenant 激活租户
func (uc *TenantUsecase) ActivateTenant(ctx context.Context, id string) error {
	tenant, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	tenant.Activate()

	if err := uc.tenantRepo.Update(ctx, tenant); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Tenant activated: %s", id)
	return nil
}

// UpgradeTenantPlan 升级租户计划
func (uc *TenantUsecase) UpgradeTenantPlan(ctx context.Context, id string, plan domain.TenantPlan) error {
	tenant, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	tenant.UpgradePlan(plan)

	if err := uc.tenantRepo.Update(ctx, tenant); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Tenant plan upgraded: %s -> %s", id, plan)
	return nil
}

// UpdateTenantSettings 更新租户设置
func (uc *TenantUsecase) UpdateTenantSettings(ctx context.Context, id, key string, value interface{}) error {
	tenant, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	tenant.UpdateSettings(key, value)

	if err := uc.tenantRepo.Update(ctx, tenant); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Tenant settings updated: %s", id)
	return nil
}

// DeleteTenant 删除租户
func (uc *TenantUsecase) DeleteTenant(ctx context.Context, id string) error {
	// 检查租户是否存在
	_, err := uc.tenantRepo.GetByID(ctx, id)
	if err != nil {
		return pkgErrors.NewNotFound("TENANT_NOT_FOUND", "租户不存在")
	}

	// TODO: 检查租户下是否还有用户，如果有则不允许删除

	// 删除
	if err := uc.tenantRepo.Delete(ctx, id); err != nil {
		return err
	}

	uc.log.WithContext(ctx).Infof("Tenant deleted: %s", id)
	return nil
}
