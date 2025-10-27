//go:build wireinject
// +build wireinject

// The build tag makes sure the stub is not built in the final build.

package main

import (
	"voiceassistant/cmd/identity-service/internal/biz"
	"voiceassistant/cmd/identity-service/internal/data"
	"voiceassistant/cmd/identity-service/internal/server"
	"voiceassistant/cmd/identity-service/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

// wireApp init kratos application.
func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		// Redis
		NewRedisClient,

		// Consul Registry (commented out due to multiple int params issue)
		// server.NewConsulRegistry,

		// Cache layer
		data.NewCacheManager,

		// Token Blacklist
		data.NewTokenBlacklistService,
		wire.Bind(new(biz.TokenBlacklist), new(*data.TokenBlacklistService)),

		// Data layer
		data.NewDB,
		data.NewData,
		data.NewUserRepo,
		data.NewTenantRepo,

		// Business logic layer
		biz.NewUserUsecase,
		biz.NewAuthUsecase,
		biz.NewTenantUsecase,

		// Service layer
		service.NewIdentityService,

		// Server layer
		server.NewGRPCServer,
		server.NewHTTPServer,

		// App
		newApp,
	))
}
