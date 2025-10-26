package domain

import "time"

// Report 报表聚合根
type Report struct {
	ID          string
	TenantID    string
	Type        ReportType
	Name        string
	Description string
	Status      ReportStatus
	Format      ReportFormat
	Data        map[string]interface{}
	FileURL     string
	CreatedBy   string
	CreatedAt   time.Time
	CompletedAt *time.Time
}

// ReportType 报表类型
type ReportType string

const (
	ReportTypeUsage  ReportType = "usage"  // 使用报表
	ReportTypeCost   ReportType = "cost"   // 成本报表
	ReportTypeModel  ReportType = "model"  // 模型报表
	ReportTypeUser   ReportType = "user"   // 用户报表
	ReportTypeCustom ReportType = "custom" // 自定义报表
)

// ReportStatus 报表状态
type ReportStatus string

const (
	ReportStatusPending    ReportStatus = "pending"    // 待处理
	ReportStatusProcessing ReportStatus = "processing" // 处理中
	ReportStatusCompleted  ReportStatus = "completed"  // 已完成
	ReportStatusFailed     ReportStatus = "failed"     // 失败
)

// ReportFormat 报表格式
type ReportFormat string

const (
	ReportFormatJSON  ReportFormat = "json"  // JSON
	ReportFormatCSV   ReportFormat = "csv"   // CSV
	ReportFormatExcel ReportFormat = "excel" // Excel
	ReportFormatPDF   ReportFormat = "pdf"   // PDF
)

// NewReport 创建报表
func NewReport(tenantID, reportType, name, createdBy string) *Report {
	return &Report{
		ID:        generateID(),
		TenantID:  tenantID,
		Type:      ReportType(reportType),
		Name:      name,
		Status:    ReportStatusPending,
		Format:    ReportFormatJSON,
		Data:      make(map[string]interface{}),
		CreatedBy: createdBy,
		CreatedAt: time.Now(),
	}
}

// Complete 完成报表
func (r *Report) Complete(fileURL string) {
	r.Status = ReportStatusCompleted
	r.FileURL = fileURL
	now := time.Now()
	r.CompletedAt = &now
}

// Fail 标记失败
func (r *Report) Fail() {
	r.Status = ReportStatusFailed
	now := time.Now()
	r.CompletedAt = &now
}

func generateID() string {
	// 简化实现，实际应使用 UUID
	return "report_" + time.Now().Format("20060102150405")
}
