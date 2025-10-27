//go:build wireinject
// +build wireinject

package main

import (
	"voiceassistant/cmd/notification-service/internal/biz"
	"voiceassistant/cmd/notification-service/internal/data"
	"voiceassistant/cmd/notification-service/internal/infra"
	"voiceassistant/cmd/notification-service/internal/server"
	"voiceassistant/cmd/notification-service/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

// ProviderSet is the wire provider set
var ProviderSet = wire.NewSet(
	// Data layer
	provideDataConfig,
	data.NewDB,
	data.NewData,
	data.NewNotificationRepository,
	data.NewTemplateRepository,

	// Infrastructure
	infra.NewEmailProvider,
	infra.NewSMSProvider,
	infra.NewWebSocketManager,
	infra.NewHealthChecker,
	infra.NewMetricsCollector,

	// Business logic
	biz.NewNotificationUsecase,
	biz.NewTemplateUsecase,

	// Service layer
	service.NewNotificationService,

	// Server
	provideHTTPServerConfig,
	provideGRPCServerConfig,
	server.NewGRPCServer,
	server.NewHTTPServer,

	// App
	newApp,
)

// provideDataConfig extracts data configuration
func provideDataConfig(c *Config) *data.Config {
	return &c.Data.Database
}

// provideHTTPServerConfig extracts HTTP server configuration
func provideHTTPServerConfig(c *Config) *server.HTTPConfig {
	return &server.HTTPConfig{
		Addr:    c.Server.HTTP.Addr,
		Timeout: c.Server.HTTP.Timeout,
	}
}

// provideGRPCServerConfig extracts GRPC server configuration
func provideGRPCServerConfig(c *Config) *server.GRPCConfig {
	return &server.GRPCConfig{
		Addr:    c.Server.GRPC.Addr,
		Timeout: c.Server.GRPC.Timeout,
	}
}

// wireApp initializes the application with dependency injection
func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(ProviderSet))
}
