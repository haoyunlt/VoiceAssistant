//go:build wireinject
// +build wireinject

package main

import (
	"analytics-service/internal/biz"
	"analytics-service/internal/data"
	"analytics-service/internal/server"
	"analytics-service/internal/service"

	"github.com/google/wire"
)

// initApp 初始化应用
func initApp(
	dbConfig *data.DBConfig,
	chConfig *data.ClickHouseConfig,
) (*server.HTTPServer, error) {
	wire.Build(
		// Data 层
		data.NewDB,
		data.NewClickHouseClient,
		data.NewMetricRepository,
		data.NewReportRepository,

		// Biz 层
		biz.NewMetricUsecase,
		biz.NewReportUsecase,

		// Service 层
		service.NewAnalyticsService,

		// Server 层
		server.NewHTTPServer,
	)

	return nil, nil
}
