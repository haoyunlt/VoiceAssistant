package biz

import (
	"context"
	"fmt"
	"time"
)

// TenantDeletionUsecase 租户删除用例
type TenantDeletionUsecase struct {
	tenantRepo TenantRepository
	userRepo   UserRepository
	// 其他需要清理的资源仓储
}

// NewTenantDeletionUsecase 创建租户删除用例
func NewTenantDeletionUsecase(
	tenantRepo TenantRepository,
	userRepo UserRepository,
) *TenantDeletionUsecase {
	return &TenantDeletionUsecase{
		tenantRepo: tenantRepo,
		userRepo:   userRepo,
	}
}

// DeletionCheck 删除前检查
type DeletionCheck struct {
	Name     string      `json:"name"`
	Passed   bool        `json:"passed"`
	Message  string      `json:"message"`
	Details  interface{} `json:"details,omitempty"`
	Severity string      `json:"severity"` // warning, error, critical
	Blocker  bool        `json:"blocker"`  // 是否阻止删除
}

// DeletionSummary 删除摘要
type DeletionSummary struct {
	TenantID      string           `json:"tenant_id"`
	TenantName    string           `json:"tenant_name"`
	CanDelete     bool             `json:"can_delete"`
	Checks        []*DeletionCheck `json:"checks"`
	Warnings      int              `json:"warnings"`
	Errors        int              `json:"errors"`
	TotalUsers    int              `json:"total_users"`
	ActiveUsers   int              `json:"active_users"`
	TotalData     DataSummary      `json:"total_data"`
	EstimatedTime string           `json:"estimated_time"`
	CheckedAt     time.Time        `json:"checked_at"`
}

// DataSummary 数据摘要
type DataSummary struct {
	Documents     int64 `json:"documents"`
	Conversations int64 `json:"conversations"`
	Messages      int64 `json:"messages"`
	KBEntities    int64 `json:"kb_entities"`
	TotalSizeMB   int64 `json:"total_size_mb"`
}

// DeletionResult 删除结果
type DeletionResult struct {
	TenantID    string           `json:"tenant_id"`
	Success     bool             `json:"success"`
	DeletedData map[string]int64 `json:"deleted_data"`
	Errors      []string         `json:"errors,omitempty"`
	StartedAt   time.Time        `json:"started_at"`
	CompletedAt time.Time        `json:"completed_at"`
	Duration    string           `json:"duration"`
}

// CheckTenantDeletion 检查租户是否可以删除
func (uc *TenantDeletionUsecase) CheckTenantDeletion(ctx context.Context, tenantID string) (*DeletionSummary, error) {
	// 获取租户信息
	tenant, err := uc.tenantRepo.GetByID(ctx, tenantID)
	if err != nil {
		return nil, fmt.Errorf("failed to get tenant: %w", err)
	}

	summary := &DeletionSummary{
		TenantID:   tenantID,
		TenantName: tenant.Name,
		Checks:     make([]*DeletionCheck, 0),
		CheckedAt:  time.Now(),
	}

	// 1. 检查租户状态
	statusCheck := uc.checkTenantStatus(ctx, tenant)
	summary.Checks = append(summary.Checks, statusCheck)

	// 2. 检查用户数量
	userCheck := uc.checkUsers(ctx, tenantID)
	summary.Checks = append(summary.Checks, userCheck)
	if userStats, ok := userCheck.Details.(map[string]int); ok {
		summary.TotalUsers = userStats["total"]
		summary.ActiveUsers = userStats["active"]
	}

	// 3. 检查活跃会话
	sessionCheck := uc.checkActiveSessions(ctx, tenantID)
	summary.Checks = append(summary.Checks, sessionCheck)

	// 4. 检查数据量
	dataCheck := uc.checkDataVolume(ctx, tenantID)
	summary.Checks = append(summary.Checks, dataCheck)
	if dataSummary, ok := dataCheck.Details.(DataSummary); ok {
		summary.TotalData = dataSummary
	}

	// 5. 检查付费状态
	billingCheck := uc.checkBillingStatus(ctx, tenantID)
	summary.Checks = append(summary.Checks, billingCheck)

	// 6. 检查依赖关系
	dependencyCheck := uc.checkDependencies(ctx, tenantID)
	summary.Checks = append(summary.Checks, dependencyCheck)

	// 7. 检查备份状态
	backupCheck := uc.checkBackupStatus(ctx, tenantID)
	summary.Checks = append(summary.Checks, backupCheck)

	// 统计警告和错误
	canDelete := true
	for _, check := range summary.Checks {
		if !check.Passed {
			if check.Severity == "error" || check.Severity == "critical" {
				summary.Errors++
				if check.Blocker {
					canDelete = false
				}
			} else {
				summary.Warnings++
			}
		}
	}

	summary.CanDelete = canDelete

	// 估算删除时间
	summary.EstimatedTime = uc.estimateDeletionTime(summary.TotalData)

	return summary, nil
}

// checkTenantStatus 检查租户状态
func (uc *TenantDeletionUsecase) checkTenantStatus(ctx context.Context, tenant *Tenant) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "tenant_status",
		Severity: "error",
		Blocker:  true,
	}

	if tenant.Status == "deleted" {
		check.Passed = false
		check.Message = "租户已被标记为删除"
		return check
	}

	if tenant.Status == "suspended" {
		check.Passed = true
		check.Message = "租户已暂停，可以删除"
		check.Severity = "info"
	} else {
		check.Passed = true
		check.Message = "租户状态正常"
		check.Severity = "info"
	}

	return check
}

// checkUsers 检查用户
func (uc *TenantDeletionUsecase) checkUsers(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "users",
		Severity: "warning",
		Blocker:  false,
	}

	// 获取用户统计（实际应该调用repository）
	totalUsers := 25  // Mock数据
	activeUsers := 15 // Mock数据

	check.Details = map[string]int{
		"total":  totalUsers,
		"active": activeUsers,
	}

	if activeUsers > 0 {
		check.Passed = false
		check.Message = fmt.Sprintf("租户有%d个活跃用户，建议先通知用户", activeUsers)
	} else {
		check.Passed = true
		check.Message = "没有活跃用户"
	}

	return check
}

// checkActiveSessions 检查活跃会话
func (uc *TenantDeletionUsecase) checkActiveSessions(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "active_sessions",
		Severity: "warning",
		Blocker:  false,
	}

	// 实际应该查询会话服务
	activeSessions := 3 // Mock数据

	check.Details = map[string]int{
		"count": activeSessions,
	}

	if activeSessions > 0 {
		check.Passed = false
		check.Message = fmt.Sprintf("有%d个活跃会话，将被强制终止", activeSessions)
	} else {
		check.Passed = true
		check.Message = "没有活跃会话"
	}

	return check
}

// checkDataVolume 检查数据量
func (uc *TenantDeletionUsecase) checkDataVolume(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "data_volume",
		Severity: "info",
		Blocker:  false,
	}

	// 实际应该查询各个服务的数据量
	dataSummary := DataSummary{
		Documents:     120,
		Conversations: 350,
		Messages:      4200,
		KBEntities:    850,
		TotalSizeMB:   2500,
	}

	check.Details = dataSummary
	check.Passed = true

	if dataSummary.TotalSizeMB > 10000 {
		check.Message = fmt.Sprintf("数据量较大（%.1fGB），删除可能需要较长时间", float64(dataSummary.TotalSizeMB)/1024)
		check.Severity = "warning"
	} else {
		check.Message = fmt.Sprintf("数据量：%.1fGB", float64(dataSummary.TotalSizeMB)/1024)
	}

	return check
}

// checkBillingStatus 检查付费状态
func (uc *TenantDeletionUsecase) checkBillingStatus(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "billing_status",
		Severity: "error",
		Blocker:  true,
	}

	// 实际应该查询账单服务
	hasUnpaidBills := false // Mock数据
	unpaidAmount := 0.0     // Mock数据

	if hasUnpaidBills {
		check.Passed = false
		check.Message = fmt.Sprintf("有未支付账单：$%.2f，请先结清", unpaidAmount)
		check.Details = map[string]interface{}{
			"unpaid_amount": unpaidAmount,
		}
	} else {
		check.Passed = true
		check.Message = "没有未支付账单"
		check.Blocker = false
	}

	return check
}

// checkDependencies 检查依赖关系
func (uc *TenantDeletionUsecase) checkDependencies(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "dependencies",
		Severity: "error",
		Blocker:  true,
	}

	// 实际应该检查是否有其他租户依赖
	hasDependencies := false // Mock数据

	if hasDependencies {
		check.Passed = false
		check.Message = "存在依赖关系，无法删除"
	} else {
		check.Passed = true
		check.Message = "没有依赖关系"
		check.Blocker = false
	}

	return check
}

// checkBackupStatus 检查备份状态
func (uc *TenantDeletionUsecase) checkBackupStatus(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "backup_status",
		Severity: "warning",
		Blocker:  false,
	}

	// 实际应该检查最近的备份时间
	hasRecentBackup := false // Mock数据
	lastBackup := time.Now().Add(-48 * time.Hour)

	check.Details = map[string]interface{}{
		"last_backup": lastBackup.Format(time.RFC3339),
	}

	if !hasRecentBackup {
		check.Passed = false
		check.Message = fmt.Sprintf("最近备份时间：%s，建议先备份数据", lastBackup.Format("2006-01-02"))
	} else {
		check.Passed = true
		check.Message = "数据已备份"
	}

	return check
}

// estimateDeletionTime 估算删除时间
func (uc *TenantDeletionUsecase) estimateDeletionTime(data DataSummary) string {
	// 简单估算：每GB大约需要1分钟
	minutes := data.TotalSizeMB / 1024

	if minutes < 1 {
		return "< 1分钟"
	} else if minutes < 60 {
		return fmt.Sprintf("约%d分钟", minutes)
	} else {
		hours := minutes / 60
		return fmt.Sprintf("约%d小时", hours)
	}
}

// DeleteTenant 删除租户（执行实际删除）
func (uc *TenantDeletionUsecase) DeleteTenant(ctx context.Context, tenantID string, force bool) (*DeletionResult, error) {
	startTime := time.Now()

	result := &DeletionResult{
		TenantID:    tenantID,
		DeletedData: make(map[string]int64),
		Errors:      make([]string, 0),
		StartedAt:   startTime,
	}

	// 如果不是强制删除，先进行安全检查
	if !force {
		summary, err := uc.CheckTenantDeletion(ctx, tenantID)
		if err != nil {
			return nil, fmt.Errorf("pre-deletion check failed: %w", err)
		}

		if !summary.CanDelete {
			return nil, fmt.Errorf("tenant cannot be deleted: %d errors", summary.Errors)
		}
	}

	// 1. 删除用户数据
	if count, err := uc.deleteUsers(ctx, tenantID); err != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("delete users: %v", err))
	} else {
		result.DeletedData["users"] = count
	}

	// 2. 删除对话和消息
	if count, err := uc.deleteConversations(ctx, tenantID); err != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("delete conversations: %v", err))
	} else {
		result.DeletedData["conversations"] = count
	}

	// 3. 删除文档
	if count, err := uc.deleteDocuments(ctx, tenantID); err != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("delete documents: %v", err))
	} else {
		result.DeletedData["documents"] = count
	}

	// 4. 删除知识库
	if count, err := uc.deleteKnowledgeBase(ctx, tenantID); err != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("delete knowledge base: %v", err))
	} else {
		result.DeletedData["kb_entities"] = count
	}

	// 5. 删除租户记录
	if err := uc.tenantRepo.Delete(ctx, tenantID); err != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("delete tenant: %v", err))
	}

	result.CompletedAt = time.Now()
	result.Duration = result.CompletedAt.Sub(startTime).String()
	result.Success = len(result.Errors) == 0

	return result, nil
}

// deleteUsers 删除用户
func (uc *TenantDeletionUsecase) deleteUsers(ctx context.Context, tenantID string) (int64, error) {
	// 实际应该调用用户服务API
	// 这里返回Mock数据
	return 25, nil
}

// deleteConversations 删除对话
func (uc *TenantDeletionUsecase) deleteConversations(ctx context.Context, tenantID string) (int64, error) {
	// 实际应该调用对话服务API
	return 350, nil
}

// deleteDocuments 删除文档
func (uc *TenantDeletionUsecase) deleteDocuments(ctx context.Context, tenantID string) (int64, error) {
	// 实际应该调用文档服务API
	return 120, nil
}

// deleteKnowledgeBase 删除知识库
func (uc *TenantDeletionUsecase) deleteKnowledgeBase(ctx context.Context, tenantID string) (int64, error) {
	// 实际应该调用知识库服务API
	return 850, nil
}

// Repository interfaces (should be defined elsewhere)
type TenantRepository interface {
	GetByID(ctx context.Context, id string) (*Tenant, error)
	Delete(ctx context.Context, id string) error
}

type UserRepository interface {
	CountByTenant(ctx context.Context, tenantID string) (int, error)
}

// Tenant model (should be defined elsewhere)
type Tenant struct {
	ID     string
	Name   string
	Status string
}
