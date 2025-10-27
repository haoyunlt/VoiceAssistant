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
	server.NewHTTPServer,
	server.NewGRPCServer,
	server.NewABTestHandler,
)

// provideModelRegistry 提供模型注册表
func provideModelRegistry(logger log.Logger) *domain.ModelRegistry {
	registry := domain.NewModelRegistry(logger)
	// TODO: 从配置文件加载模型
	return registry
}

func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		ProviderSet,
		newApp,
	))
}
