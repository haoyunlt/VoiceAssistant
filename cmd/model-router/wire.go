//go:build wireinject
// +build wireinject

package main

import (
	"voiceassistant/cmd/model-router/internal/application"
	"voiceassistant/cmd/model-router/internal/data"
	"voiceassistant/cmd/model-router/internal/domain"
	"voiceassistant/cmd/model-router/internal/infrastructure"
	"voiceassistant/cmd/model-router/internal/server"
	"voiceassistant/cmd/model-router/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

// ProviderSet 依赖注入集合
var ProviderSet = wire.NewSet(
	// Provide config components
	provideDBConfig,
	provideRedisConfig,
	provideBudgetConfig,

	// Data层
	data.NewDB,
	data.NewRedis,
	data.NewData,

	// Repository
	data.NewABTestRepository,

	// Infrastructure
	infrastructure.NewABTestCache,
	wire.Bind(new(application.ABTestCache), new(*infrastructure.ABTestCacheImpl)),

	// Domain
	provideModelRegistry,

	// Application
	application.NewABTestingServiceV2,
	application.NewRoutingService,
	application.NewCostOptimizer,
	application.NewFallbackManager,

	// Service
	service.NewModelRouterService,

	// Server
	provideHTTPServer,
	server.NewGRPCServer,
	server.NewABTestHandler,
)

// provideDBConfig 提供数据库配置
func provideDBConfig(cfg *Config) *data.Config {
	return &cfg.Data.Database
}

// provideRedisConfig 提供Redis配置
func provideRedisConfig(cfg *Config) *data.RedisConfig {
	return &data.RedisConfig{
		Addr:         cfg.Data.Redis.Addr,
		Password:     cfg.Data.Redis.Password,
		DB:           cfg.Data.Redis.DB,
		DialTimeout:  cfg.Data.Redis.DialTimeout,
		ReadTimeout:  cfg.Data.Redis.ReadTimeout,
		WriteTimeout: cfg.Data.Redis.WriteTimeout,
	}
}

// provideBudgetConfig 提供预算配置
func provideBudgetConfig(cfg *Config) *application.BudgetConfig {
	return &application.BudgetConfig{
		DailyBudget:    100.0,  // 默认每日预算 $100
		WeeklyBudget:   500.0,  // 默认每周预算 $500
		MonthlyBudget:  2000.0, // 默认每月预算 $2000
		AlertThreshold: 0.8,    // 80% 时告警
	}
}

// provideModelRegistry 提供模型注册表
func provideModelRegistry(cfg *Config, logger log.Logger) *domain.ModelRegistry {
	registry := domain.NewModelRegistry()

	// 从配置文件加载模型
	if cfg.Models.ConfigPath != "" {
		if err := loadModelsFromConfig(cfg.Models.ConfigPath, registry); err != nil {
			log.NewHelper(logger).Warnf("Failed to load models from config: %v", err)
		}
	}

	return registry
}

// provideHTTPServer 提供 HTTP 服务器
func provideHTTPServer(
	service *service.ModelRouterService,
	logger log.Logger,
	cfg *Config,
) *server.HTTPServer {
	return server.NewHTTPServer(service, logger, cfg.Server.HTTP.Addr)
}

// loadModelsFromConfig 从配置文件加载模型
func loadModelsFromConfig(path string, registry *domain.ModelRegistry) error {
	models, err := domain.LoadModelsFromFile(path)
	if err != nil {
		return err
	}

	for _, model := range models {
		if err := registry.Register(model); err != nil {
			return err
		}
	}

	return nil
}

func wireApp(cfg *Config, logger log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		ProviderSet,
		newApp,
	))
}
