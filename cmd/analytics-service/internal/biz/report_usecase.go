package biz

import (
	"context"
	"fmt"

	"analytics-service/internal/domain"
)

// ReportUsecase 报表用例
type ReportUsecase struct {
	reportRepo domain.ReportRepository
	metricRepo domain.MetricRepository
}

// NewReportUsecase 创建报表用例
func NewReportUsecase(reportRepo domain.ReportRepository, metricRepo domain.MetricRepository) *ReportUsecase {
	return &ReportUsecase{
		reportRepo: reportRepo,
		metricRepo: metricRepo,
	}
}

// CreateReport 创建报表
func (uc *ReportUsecase) CreateReport(ctx context.Context, tenantID, reportType, name, createdBy string) (*domain.Report, error) {
	// 验证报表类型
	if err := uc.validateReportType(domain.ReportType(reportType)); err != nil {
		return nil, err
	}

	// 创建报表
	report := domain.NewReport(tenantID, reportType, name, createdBy)

	// 保存到数据库
	if err := uc.reportRepo.CreateReport(ctx, report); err != nil {
		return nil, fmt.Errorf("failed to create report: %w", err)
	}

	// 异步生成报表
	go uc.generateReportAsync(context.Background(), report)

	return report, nil
}

// GetReport 获取报表
func (uc *ReportUsecase) GetReport(ctx context.Context, id string) (*domain.Report, error) {
	report, err := uc.reportRepo.GetReport(ctx, id)
	if err != nil {
		return nil, err
	}

	return report, nil
}

// ListReports 列出报表
func (uc *ReportUsecase) ListReports(ctx context.Context, tenantID string, limit, offset int) ([]*domain.Report, int, error) {
	reports, total, err := uc.reportRepo.ListReports(ctx, tenantID, limit, offset)
	if err != nil {
		return nil, 0, err
	}

	return reports, total, nil
}

// DeleteReport 删除报表
func (uc *ReportUsecase) DeleteReport(ctx context.Context, id string) error {
	return uc.reportRepo.DeleteReport(ctx, id)
}

// generateReportAsync 异步生成报表
func (uc *ReportUsecase) generateReportAsync(ctx context.Context, report *domain.Report) {
	// 更新状态为处理中
	report.Status = domain.ReportStatusProcessing
	_ = uc.reportRepo.UpdateReport(ctx, report)

	// 根据报表类型生成数据
	var err error
	switch report.Type {
	case domain.ReportTypeUsage:
		err = uc.generateUsageReport(ctx, report)
	case domain.ReportTypeCost:
		err = uc.generateCostReport(ctx, report)
	case domain.ReportTypeModel:
		err = uc.generateModelReport(ctx, report)
	case domain.ReportTypeUser:
		err = uc.generateUserReport(ctx, report)
	default:
		err = fmt.Errorf("unsupported report type: %s", report.Type)
	}

	// 更新报表状态
	if err != nil {
		report.Fail()
	} else {
		// 生成文件并上传到对象存储（简化实现）
		fileURL := fmt.Sprintf("s3://reports/%s.json", report.ID)
		report.Complete(fileURL)
	}

	_ = uc.reportRepo.UpdateReport(ctx, report)
}

// generateUsageReport 生成使用报表
func (uc *ReportUsecase) generateUsageReport(ctx context.Context, report *domain.Report) error {
	// TODO: 实现使用报表生成逻辑
	// 1. 从 ClickHouse 查询数据
	// 2. 聚合统计
	// 3. 生成报表数据
	report.Data = map[string]interface{}{
		"total_conversations": 1000,
		"total_messages":      5000,
		"total_tokens":        100000,
	}
	return nil
}

// generateCostReport 生成成本报表
func (uc *ReportUsecase) generateCostReport(ctx context.Context, report *domain.Report) error {
	// TODO: 实现成本报表生成逻辑
	report.Data = map[string]interface{}{
		"total_cost":     100.50,
		"model_cost":     80.00,
		"embedding_cost": 15.00,
		"rerank_cost":    5.50,
	}
	return nil
}

// generateModelReport 生成模型报表
func (uc *ReportUsecase) generateModelReport(ctx context.Context, report *domain.Report) error {
	// TODO: 实现模型报表生成逻辑
	report.Data = map[string]interface{}{
		"models": []map[string]interface{}{
			{"name": "gpt-4", "requests": 500, "tokens": 50000, "cost": 50.00},
			{"name": "gpt-3.5-turbo", "requests": 1000, "tokens": 30000, "cost": 15.00},
		},
	}
	return nil
}

// generateUserReport 生成用户报表
func (uc *ReportUsecase) generateUserReport(ctx context.Context, report *domain.Report) error {
	// TODO: 实现用户报表生成逻辑
	report.Data = map[string]interface{}{
		"active_users":         100,
		"total_users":          500,
		"avg_session_duration": 300,
	}
	return nil
}

// validateReportType 验证报表类型
func (uc *ReportUsecase) validateReportType(reportType domain.ReportType) error {
	switch reportType {
	case domain.ReportTypeUsage, domain.ReportTypeCost, domain.ReportTypeModel, domain.ReportTypeUser, domain.ReportTypeCustom:
		return nil
	default:
		return domain.ErrInvalidReportType
	}
}
