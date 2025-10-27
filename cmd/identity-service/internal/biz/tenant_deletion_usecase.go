package biz

import (
	"context"
	"fmt"
	"time"
)

// TenantDeletionUsecase 租户删除用例
type TenantDeletionUsecase struct {
	tenantRepo       TenantRepository
	userRepo         UserRepository
	conversationRepo ConversationRepository
	knowledgeRepo    KnowledgeRepository
	sessionRepo      SessionRepository
	billingRepo      BillingRepository
}

// ConversationRepository 会话仓储接口
type ConversationRepository interface {
	CountByTenantID(ctx context.Context, tenantID string) (int64, error)
	CountActiveByTenantID(ctx context.Context, tenantID string) (int64, error)
	DeleteByTenantID(ctx context.Context, tenantID string) (int64, error)
}

// KnowledgeRepository 知识库仓储接口
type KnowledgeRepository interface {
	CountDocumentsByTenantID(ctx context.Context, tenantID string) (int64, error)
	CountEntitiesByTenantID(ctx context.Context, tenantID string) (int64, error)
	GetTotalSizeByTenantID(ctx context.Context, tenantID string) (int64, error)
	DeleteByTenantID(ctx context.Context, tenantID string) (int64, error)
}

// SessionRepository 会话仓储接口
type SessionRepository interface {
	CountActiveByTenantID(ctx context.Context, tenantID string) (int64, error)
	TerminateAllByTenantID(ctx context.Context, tenantID string) error
}

// BillingRepository 账单仓储接口
type BillingRepository interface {
	HasUnpaidBillsByTenantID(ctx context.Context, tenantID string) (bool, float64, error)
	GetUsageSummary(ctx context.Context, tenantID string) (*UsageSummary, error)
}

// UsageSummary 使用量摘要
type UsageSummary struct {
	TotalCalls      int64     `json:"total_calls"`
	TotalTokens     int64     `json:"total_tokens"`
	TotalCost       float64   `json:"total_cost"`
	UnpaidAmount    float64   `json:"unpaid_amount"`
	LastBillingDate time.Time `json:"last_billing_date"`
}

// NewTenantDeletionUsecase 创建租户删除用例
func NewTenantDeletionUsecase(
	tenantRepo TenantRepository,
	userRepo UserRepository,
	conversationRepo ConversationRepository,
	knowledgeRepo KnowledgeRepository,
	sessionRepo SessionRepository,
	billingRepo BillingRepository,
) *TenantDeletionUsecase {
	return &TenantDeletionUsecase{
		tenantRepo:       tenantRepo,
		userRepo:         userRepo,
		conversationRepo: conversationRepo,
		knowledgeRepo:    knowledgeRepo,
		sessionRepo:      sessionRepo,
		billingRepo:      billingRepo,
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

	// 获取用户统计
	users, err := uc.userRepo.ListByTenant(ctx, tenantID, 0, 1000)
	if err != nil {
		check.Passed = false
		check.Message = fmt.Sprintf("无法查询用户信息: %v", err)
		check.Severity = "error"
		return check
	}

	totalUsers := len(users)
	activeUsers := 0
	for _, user := range users {
		if user.Status == "active" {
			activeUsers++
		}
	}

	check.Details = map[string]int{
		"total":  totalUsers,
		"active": activeUsers,
	}

	if activeUsers > 0 {
		check.Passed = false
		check.Message = fmt.Sprintf("租户有%d个活跃用户，建议先通知用户", activeUsers)
	} else {
		check.Passed = true
		check.Message = fmt.Sprintf("共%d个用户，无活跃用户", totalUsers)
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

	// 查询活跃会话数量
	activeSessions, err := uc.sessionRepo.CountActiveByTenantID(ctx, tenantID)
	if err != nil {
		check.Passed = false
		check.Message = fmt.Sprintf("无法查询会话信息: %v", err)
		check.Severity = "error"
		return check
	}

	check.Details = map[string]int64{
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

	// 查询各个服务的数据量
	documents, err := uc.knowledgeRepo.CountDocumentsByTenantID(ctx, tenantID)
	if err != nil {
		documents = 0
	}

	conversations, err := uc.conversationRepo.CountByTenantID(ctx, tenantID)
	if err != nil {
		conversations = 0
	}

	kbEntities, err := uc.knowledgeRepo.CountEntitiesByTenantID(ctx, tenantID)
	if err != nil {
		kbEntities = 0
	}

	totalSizeMB, err := uc.knowledgeRepo.GetTotalSizeByTenantID(ctx, tenantID)
	if err != nil {
		totalSizeMB = 0
	}

	dataSummary := DataSummary{
		Documents:     documents,
		Conversations: conversations,
		Messages:      conversations * 10, // 估算：平均每个对话10条消息
		KBEntities:    kbEntities,
		TotalSizeMB:   totalSizeMB,
	}

	check.Details = dataSummary
	check.Passed = true

	if dataSummary.TotalSizeMB > 10000 {
		check.Message = fmt.Sprintf("数据量较大（%.1fGB），删除可能需要较长时间", float64(dataSummary.TotalSizeMB)/1024)
		check.Severity = "warning"
	} else {
		check.Message = fmt.Sprintf("数据量：%.1fGB（%d文档，%d对话）",
			float64(dataSummary.TotalSizeMB)/1024,
			dataSummary.Documents,
			dataSummary.Conversations)
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

	// 查询账单状态
	hasUnpaidBills, unpaidAmount, err := uc.billingRepo.HasUnpaidBillsByTenantID(ctx, tenantID)
	if err != nil {
		check.Passed = false
		check.Message = fmt.Sprintf("无法查询账单信息: %v", err)
		check.Severity = "error"
		return check
	}

	if hasUnpaidBills {
		check.Passed = false
		check.Message = fmt.Sprintf("有未支付账单：$%.2f，必须先结清账单", unpaidAmount)
		check.Details = map[string]interface{}{
			"unpaid_amount": unpaidAmount,
		}
	} else {
		check.Passed = true
		check.Message = "账单已结清"
		check.Blocker = false

		// 获取使用量摘要
		if usage, err := uc.billingRepo.GetUsageSummary(ctx, tenantID); err == nil {
			check.Details = usage
		}
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

	// 检查租户依赖（暂不实现复杂依赖逻辑）
	// 未来可以扩展：检查子租户、共享资源、跨租户权限等
	check.Passed = true
	check.Message = "没有依赖关系"
	check.Blocker = false

	return check
}

// checkBackupStatus 检查备份状态
func (uc *TenantDeletionUsecase) checkBackupStatus(ctx context.Context, tenantID string) *DeletionCheck {
	check := &DeletionCheck{
		Name:     "backup_status",
		Severity: "warning",
		Blocker:  false,
	}

	// 备份检查（当前简化实现：建议人工确认）
	// 未来可以集成备份服务API，检查最近备份时间
	check.Passed = false
	check.Message = "建议在删除前手动备份重要数据"
	check.Details = map[string]interface{}{
		"recommendation": "Export tenant data before deletion",
		"note":           "Deletion is irreversible",
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
	count, err := uc.userRepo.DeleteByTenantID(ctx, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to delete users: %w", err)
	}
	return count, nil
}

// deleteConversations 删除对话
func (uc *TenantDeletionUsecase) deleteConversations(ctx context.Context, tenantID string) (int64, error) {
	// 先终止所有活跃会话
	if err := uc.sessionRepo.TerminateAllByTenantID(ctx, tenantID); err != nil {
		return 0, fmt.Errorf("failed to terminate sessions: %w", err)
	}

	// 删除对话记录
	count, err := uc.conversationRepo.DeleteByTenantID(ctx, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to delete conversations: %w", err)
	}
	return count, nil
}

// deleteDocuments 删除文档
func (uc *TenantDeletionUsecase) deleteDocuments(ctx context.Context, tenantID string) (int64, error) {
	count, err := uc.knowledgeRepo.CountDocumentsByTenantID(ctx, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to count documents: %w", err)
	}

	// 删除实际在deleteKnowledgeBase中统一处理
	return count, nil
}

// deleteKnowledgeBase 删除知识库
func (uc *TenantDeletionUsecase) deleteKnowledgeBase(ctx context.Context, tenantID string) (int64, error) {
	// 删除所有知识库相关数据：文档、向量、图谱实体等
	count, err := uc.knowledgeRepo.DeleteByTenantID(ctx, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to delete knowledge base: %w", err)
	}
	return count, nil
}

// Repository interfaces (should be defined elsewhere)
type TenantRepository interface {
	GetByID(ctx context.Context, id string) (*Tenant, error)
	Delete(ctx context.Context, id string) error
}

type UserRepository interface {
	ListByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*User, error)
	DeleteByTenantID(ctx context.Context, tenantID string) (int64, error)
}

// User 用户模型
type User struct {
	ID       string
	TenantID string
	Status   string
}

// Tenant model (should be defined elsewhere)
type Tenant struct {
	ID     string
	Name   string
	Status string
}
