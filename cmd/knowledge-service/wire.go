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
		// Config conversion providers
		provideDataConfig,
		provideStorageConfig,
		provideEventConfig,
		provideSecurityConfig,
		provideHTTPConfig,
		provideGRPCConfig,

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

// provideStorageConfig converts main Config to storage.MinIOConfig
func provideStorageConfig(c *Config) storage.MinIOConfig {
	return storage.MinIOConfig{
		Endpoint:        c.Storage.Endpoint,
		AccessKeyID:     c.Storage.AccessKeyID,
		SecretAccessKey: c.Storage.SecretAccessKey,
		BucketName:      c.Storage.BucketName,
		UseSSL:          c.Storage.UseSSL,
	}
}

// provideEventConfig converts main Config to event.EventPublisherConfig
func provideEventConfig(c *Config) event.EventPublisherConfig {
	return event.EventPublisherConfig{
		Brokers: c.Event.Brokers,
		Topic:   c.Event.Topic,
	}
}

// provideSecurityConfig converts main Config to security.ClamAVConfig
func provideSecurityConfig(c *Config) security.ClamAVConfig {
	return security.ClamAVConfig{
		Host:    c.Security.ClamAV.Host,
		Port:    c.Security.ClamAV.Port,
		Timeout: c.Security.ClamAV.Timeout,
	}
}

// provideHTTPConfig converts main Config to server.HTTPConfig
func provideHTTPConfig(c *Config) *server.HTTPConfig {
	return &server.HTTPConfig{
		Network: c.Server.HTTP.Network,
		Addr:    c.Server.HTTP.Addr,
		Timeout: c.Server.HTTP.Timeout.String(),
	}
}

// provideGRPCConfig converts main Config to server.GRPCConfig
func provideGRPCConfig(c *Config) *server.GRPCConfig {
	return &server.GRPCConfig{
		Network: c.Server.GRPC.Network,
		Addr:    c.Server.GRPC.Addr,
		Timeout: c.Server.GRPC.Timeout.String(),
	}
}
