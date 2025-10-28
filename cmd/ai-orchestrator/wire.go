//go:build wireinject
// +build wireinject

// The build tag makes sure the stub is not built in the final build.

package main

import (
	"voiceassistant/cmd/ai-orchestrator/internal/biz"
	"voiceassistant/cmd/ai-orchestrator/internal/data"
	"voiceassistant/cmd/ai-orchestrator/internal/domain"
	"voiceassistant/cmd/ai-orchestrator/internal/server"
	"voiceassistant/cmd/ai-orchestrator/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

// wireApp init kratos application.
func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		// Config providers
		provideDataConfig,

		// Data layer
		data.NewDB,
		data.NewData,
		data.NewTaskRepo,
		data.NewServiceClient,

		// Bind ServiceClient interface
		wire.Bind(new(domain.ServiceClient), new(*data.GRPCServiceClient)),

		// Domain layer - Pipelines
		domain.NewRAGPipeline,
		domain.NewAgentPipeline,
		domain.NewVoicePipeline,

		// Business logic layer
		biz.NewTaskUsecase,

		// Service layer
		service.NewOrchestratorService,

		// Server layer
		server.NewGRPCServer,
		server.NewHTTPServer,

		// App
		newApp,
	))
}

// provideDataConfig 提供数据层配置
func provideDataConfig(c *Config) *data.Config {
	return &data.Config{
		Driver:          c.Data.Database.Driver,
		Source:          c.Data.Database.Source,
		MaxIdleConns:    c.Data.Database.MaxIdleConns,
		MaxOpenConns:    c.Data.Database.MaxOpenConns,
		ConnMaxLifetime: ParseDuration(c.Data.Database.ConnMaxLifetime),
	}
}
