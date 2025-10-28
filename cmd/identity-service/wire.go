//go:build wireinject
// +build wireinject

// The build tag makes sure the stub is not built in the final build.

package main

import (
	"voicehelper/cmd/identity-service/internal/biz"
	"voicehelper/cmd/identity-service/internal/data"
	"voicehelper/cmd/identity-service/internal/infra/oauth"
	"voicehelper/cmd/identity-service/internal/server"
	"voicehelper/cmd/identity-service/internal/service"

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

		// Cache layer (commented out as it's not used yet)
		// data.NewCacheManager,

		// Token Blacklist
		data.NewTokenBlacklistService,
		wire.Bind(new(biz.TokenBlacklist), new(*data.TokenBlacklistService)),

		// Data layer
		ProvideDataConfig,
		data.NewDB,
		data.NewData,
		data.NewUserRepo,
		data.NewTenantRepo,
		data.NewAuditLogRepository,
		data.NewOAuthRepo,

		// Audit Log Service
		biz.NewAuditLogService,

		// Provide Auth Config
		ProvideAuthConfig,

		// OAuth Clients
		ProvideWechatClient,
		ProvideGithubClient,
		ProvideGoogleClient,

		// OAuth Usecase
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

// ProvideWechatClient provides Wechat OAuth client
func ProvideWechatClient(cfg *Config) *biz.WechatClient {
	client := oauth.NewWechatClient(cfg.Auth.OAuth.Wechat.AppID, cfg.Auth.OAuth.Wechat.AppSecret)
	return &biz.WechatClient{OAuthClient: client}
}

// ProvideGithubClient provides GitHub OAuth client
func ProvideGithubClient(cfg *Config) *biz.GithubClient {
	client := oauth.NewGitHubClient(cfg.Auth.OAuth.Github.ClientID, cfg.Auth.OAuth.Github.ClientSecret)
	return &biz.GithubClient{OAuthClient: client}
}

// ProvideGoogleClient provides Google OAuth client
func ProvideGoogleClient(cfg *Config) *biz.GoogleClient {
	client := oauth.NewGoogleClient(
		cfg.Auth.OAuth.Google.ClientID,
		cfg.Auth.OAuth.Google.ClientSecret,
		cfg.Auth.OAuth.Google.RedirectURI,
	)
	return &biz.GoogleClient{OAuthClient: client}
}
