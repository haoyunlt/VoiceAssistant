//go:build wireinject
// +build wireinject

package main

import (
	"voicehelper/cmd/analytics-service/internal/app"
	"voicehelper/cmd/analytics-service/internal/biz"
	"voicehelper/cmd/analytics-service/internal/conf"
	"voicehelper/cmd/analytics-service/internal/data"
	"voicehelper/cmd/analytics-service/internal/server"
	"voicehelper/cmd/analytics-service/internal/service"

	"github.com/google/wire"
	"go.uber.org/zap"
)

// initApp 初始化应用
func initApp(config *conf.Config, logger *zap.Logger) (*app.App, func(), error) {
	wire.Build(
		// 提供配置
		provideDBConfig,
		provideClickHouseConfig,

		// Data 层
		data.NewDB,
		data.NewClickHouseClient,
		data.NewMemoryCache,
		data.NewMetricRepository,
		data.NewReportRepository,

		// Biz 层
		wire.Bind(new(biz.ClickHouseClient), new(*data.ClickHouseClient)),
		wire.Bind(new(biz.CacheClient), new(*data.MemoryCache)),
		biz.NewMetricUsecase,
		biz.NewReportUsecase,
		biz.NewRealtimeDashboardUsecase,

		// Service 层
		service.NewAnalyticsService,

		// Server 层
		wire.Bind(new(server.Logger), new(*zap.Logger)),
		server.NewHTTPServer,

		// App
		app.NewApp,
	)

	return nil, func() {}, nil
}

// provideDBConfig 提供数据库配置
func provideDBConfig(config *conf.Config) *data.DBConfig {
	return &data.DBConfig{
		Host:            config.Database.Host,
		Port:            config.Database.Port,
		DBName:          config.Database.DBName,
		User:            config.Database.User,
		Password:        config.Database.Password,
		SSLMode:         config.Database.SSLMode,
		MaxOpenConns:    config.Database.MaxOpenConns,
		MaxIdleConns:    config.Database.MaxIdleConns,
		ConnMaxLifetime: config.Database.ConnMaxLifetime,
	}
}

// provideClickHouseConfig 提供 ClickHouse 配置
func provideClickHouseConfig(config *conf.Config) *data.ClickHouseConfig {
	return &data.ClickHouseConfig{
		Addr:     config.ClickHouse.Addr,
		Database: config.ClickHouse.Database,
		Username: config.ClickHouse.Username,
		Password: config.ClickHouse.Password,
	}
}
