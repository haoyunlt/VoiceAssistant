//go:build wireinject
// +build wireinject

// The build tag makes sure the stub is not built in the final build.

package main

import (
	"voiceassistant/cmd/knowledge-service/internal/biz"
	"voiceassistant/cmd/knowledge-service/internal/data"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/event"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/security"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/storage"
	"voiceassistant/cmd/knowledge-service/internal/server"
	"voiceassistant/cmd/knowledge-service/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

// wireApp init kratos application.
func wireApp(c *Config, logger log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		// Config conversion
		provideDataConfig,

		// Infrastructure layer
		storage.NewMinIOClient,
		security.NewClamAVScanner,
		wire.Bind(new(security.VirusScanner), new(*security.ClamAVScanner)),
		event.NewKafkaPublisher,
		wire.Bind(new(event.EventPublisher), new(*event.KafkaPublisher)),

		// Data layer
		data.NewDB,
		data.NewData,
		data.NewKnowledgeBaseRepo,
		data.NewDocumentRepo,
		wire.Bind(new(biz.DocumentRepository), new(*data.DocumentRepository)),
		data.NewChunkRepo,

		// Business logic layer
		biz.NewKnowledgeBaseUsecase,
		biz.NewDocumentUsecase,

		// Service layer
		service.NewKnowledgeService,

		// Server layer
		server.NewGRPCServer,
		server.NewHTTPServer,

		// App
		newApp,
	))
}

// provideDataConfig converts main Config to data.Config
func provideDataConfig(c *Config) *data.Config {
	return &c.Data.Database
}
