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
		// Data layer
		data.NewDB,
		data.NewData,
		data.NewTaskRepo,
		data.NewServiceClient,

		// Domain layer - Pipelines
		wire.Bind(new(domain.ServiceClient), new(*data.GRPCServiceClient)),
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
