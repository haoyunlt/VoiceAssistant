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
		ProvideDataConfig,
		data.NewDB,
		data.NewData,
		data.NewUserRepo,
		data.NewTenantRepo,

		// Audit Log Service
		biz.NewAuditLogService,

		// Provide Auth Config
		ProvideAuthConfig,

		// OAuth Usecase (placeholder for now)
		biz.NewOAuthUsecase,

		// Business logic layer
		biz.NewUserUsecase,
		biz.NewAuthUsecase,
		biz.NewTenantUsecase,

		// Service layer
		service.NewIdentityService,

		// Server layer
		ProvideHTTPConfig,
		ProvideGRPCConfig,
		server.NewGRPCServer,
		server.NewHTTPServer,

		// App
		newApp,
	))
}

// ProvideJWTSecret provides JWT secret from config
func ProvideJWTSecret(cfg *Config) string {
	return cfg.Auth.JWTSecret
}

// ProvideAuthConfig provides auth config
func ProvideAuthConfig(cfg *Config) *biz.AuthConfig {
	return &biz.AuthConfig{
		JWTSecret:          cfg.Auth.JWTSecret,
		AccessTokenExpiry:  cfg.Auth.AccessTokenExpiry,
		RefreshTokenExpiry: cfg.Auth.RefreshTokenExpiry,
	}
}

// ProvideHTTPConfig provides HTTP server config
func ProvideHTTPConfig(cfg *Config) *server.HTTPConfig {
	return &server.HTTPConfig{
		Network: cfg.Server.HTTP.Network,
		Addr:    cfg.Server.HTTP.Addr,
		Timeout: cfg.Server.HTTP.Timeout,
	}
}

// ProvideGRPCConfig provides gRPC server config
func ProvideGRPCConfig(cfg *Config) *server.GRPCConfig {
	return &server.GRPCConfig{
		Network: cfg.Server.GRPC.Network,
		Addr:    cfg.Server.GRPC.Addr,
		Timeout: cfg.Server.GRPC.Timeout,
	}
}
