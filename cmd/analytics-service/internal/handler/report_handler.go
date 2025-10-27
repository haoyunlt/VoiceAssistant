package handler

import (
	"analytics-service/internal/biz"
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// ReportHandler 报表处理器
type ReportHandler struct {
	generator *biz.ReportGenerator
}

// NewReportHandler 创建报表处理器
func NewReportHandler(generator *biz.ReportGenerator) *ReportHandler {
	return &ReportHandler{
		generator: generator,
	}
}

// GenerateReportRequest 生成报表请求
type GenerateReportRequest struct {
	Type       string                 `json:"type" binding:"required"` // usage, cost, model, user
	TenantID   string                 `json:"tenant_id,omitempty"`
	StartDate  string                 `json:"start_date" binding:"required"`
	EndDate    string                 `json:"end_date" binding:"required"`
	Parameters map[string]interface{} `json:"parameters,omitempty"`
	Format     string                 `json:"format,omitempty"` // json, pdf, excel
}

// GenerateReport 生成报表
func (h *ReportHandler) GenerateReport(c *gin.Context) {
	var req GenerateReportRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 创建报表记录
	reportID := uuid.New().String()
	report := &biz.Report{
		ID:         reportID,
		Type:       biz.ReportType(req.Type),
		Status:     biz.ReportStatusGenerating,
		TenantID:   req.TenantID,
		StartDate:  req.StartDate,
		EndDate:    req.EndDate,
		Parameters: req.Parameters,
		CreatedAt:  time.Now(),
	}

	// 估计完成时间
	estimatedCompletion := time.Now().Add(2 * time.Minute)
	report.EstimatedCompletion = &estimatedCompletion

	// 异步生成报表
	go h.generateReportAsync(report)

	c.JSON(http.StatusOK, gin.H{
		"report_id":            reportID,
		"type":                 req.Type,
		"status":               "generating",
		"estimated_completion": estimatedCompletion.Format(time.RFC3339),
	})
}

// generateReportAsync 异步生成报表
func (h *ReportHandler) generateReportAsync(report *biz.Report) {
	ctx := context.Background()

	var data interface{}
	var err error

	switch report.Type {
	case biz.ReportTypeUsage:
		data, err = h.generator.GenerateUsageReport(ctx, report.TenantID, report.StartDate, report.EndDate)
	case biz.ReportTypeCost:
		data, err = h.generator.GenerateCostReport(ctx, report.TenantID, report.StartDate, report.EndDate)
	case biz.ReportTypeModel:
		data, err = h.generator.GenerateModelReport(ctx, report.TenantID, report.StartDate, report.EndDate)
	case biz.ReportTypeUser:
		data, err = h.generator.GenerateUserReport(ctx, report.TenantID, report.StartDate, report.EndDate)
	default:
		err = fmt.Errorf("unsupported report type: %s", report.Type)
	}

	completedAt := time.Now()
	report.CompletedAt = &completedAt

	if err != nil {
		report.Status = biz.ReportStatusFailed
		report.Error = err.Error()
	} else {
		report.Status = biz.ReportStatusCompleted
		report.Data = data

		// 生成下载URL（实际应该上传到对象存储）
		report.DownloadURL = fmt.Sprintf("https://storage.example.com/reports/%s.json", report.ID)
	}

	// TODO: 保存报表到数据库
	// h.reportRepo.Save(ctx, report)
}

// GetReport 获取报表
func (h *ReportHandler) GetReport(c *gin.Context) {
	reportID := c.Param("id")

	// TODO: 从数据库获取报表
	// report, err := h.reportRepo.Get(ctx, reportID)

	// Mock response
	c.JSON(http.StatusOK, gin.H{
		"report_id":    reportID,
		"type":         "usage",
		"status":       "completed",
		"download_url": fmt.Sprintf("https://storage.example.com/reports/%s.json", reportID),
		"created_at":   time.Now().Add(-1 * time.Hour).Format(time.RFC3339),
		"completed_at": time.Now().Add(-30 * time.Minute).Format(time.RFC3339),
	})
}

// ListReports 列出报表
func (h *ReportHandler) ListReports(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	reportType := c.Query("type")

	// TODO: 从数据库查询报表列表
	// reports, err := h.reportRepo.List(ctx, tenantID, reportType)

	// Mock response
	reports := []gin.H{
		{
			"report_id":  "report_123",
			"type":       "usage",
			"tenant_id":  tenantID,
			"status":     "completed",
			"created_at": time.Now().Add(-24 * time.Hour).Format(time.RFC3339),
		},
		{
			"report_id":  "report_124",
			"type":       "cost",
			"tenant_id":  tenantID,
			"status":     "completed",
			"created_at": time.Now().Add(-48 * time.Hour).Format(time.RFC3339),
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"reports": reports,
		"total":   len(reports),
	})
}

// GenerateUsageReport 直接生成使用报表（同步）
func (h *ReportHandler) GenerateUsageReport(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	startDate := c.Query("start_date")
	endDate := c.Query("end_date")

	if startDate == "" || endDate == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "start_date and end_date are required"})
		return
	}

	report, err := h.generator.GenerateUsageReport(c.Request.Context(), tenantID, startDate, endDate)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, report)
}

// GenerateCostReport 直接生成成本报表（同步）
func (h *ReportHandler) GenerateCostReport(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	startDate := c.Query("start_date")
	endDate := c.Query("end_date")

	if startDate == "" || endDate == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "start_date and end_date are required"})
		return
	}

	report, err := h.generator.GenerateCostReport(c.Request.Context(), tenantID, startDate, endDate)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, report)
}

// GenerateModelReport 直接生成模型报表（同步）
func (h *ReportHandler) GenerateModelReport(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	startDate := c.Query("start_date")
	endDate := c.Query("end_date")

	if startDate == "" || endDate == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "start_date and end_date are required"})
		return
	}

	report, err := h.generator.GenerateModelReport(c.Request.Context(), tenantID, startDate, endDate)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, report)
}

// GenerateUserReport 直接生成用户报表（同步）
func (h *ReportHandler) GenerateUserReport(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	startDate := c.Query("start_date")
	endDate := c.Query("end_date")

	if startDate == "" || endDate == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "start_date and end_date are required"})
		return
	}

	report, err := h.generator.GenerateUserReport(c.Request.Context(), tenantID, startDate, endDate)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, report)
}
