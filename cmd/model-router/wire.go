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
	// Data层
	data.NewDB,
	data.NewRedis,
	data.NewData,

	// Repository
	data.NewABTestRepository,

	// Infrastructure
	infrastructure.NewABTestCache,

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

// provideModelRegistry 提供模型注册表
func provideModelRegistry(cfg *Config, logger log.Logger) *domain.ModelRegistry {
	registry := domain.NewModelRegistry(logger)

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

func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		ProviderSet,
		newApp,
	))
}
