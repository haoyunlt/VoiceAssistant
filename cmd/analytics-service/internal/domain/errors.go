package domain

import "errors"

var (
	// ErrMetricNotFound 指标未找到
	ErrMetricNotFound = errors.New("metric not found")

	// ErrReportNotFound 报表未找到
	ErrReportNotFound = errors.New("report not found")

	// ErrInvalidTimePeriod 无效的时间周期
	ErrInvalidTimePeriod = errors.New("invalid time period")

	// ErrInvalidReportType 无效的报表类型
	ErrInvalidReportType = errors.New("invalid report type")

	// ErrReportGenerationFailed 报表生成失败
	ErrReportGenerationFailed = errors.New("report generation failed")

	// ErrInsufficientData 数据不足
	ErrInsufficientData = errors.New("insufficient data")
)
