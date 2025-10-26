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
	"github.com/go-redis/redis/v8"
	"github.com/google/wire"
)

// wireApp init kratos application.
func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		// Redis
		NewRedisClient,

		// Consul Registry
		server.NewConsulRegistry,

		// Cache layer
		data.NewCacheManager,

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

// NewRedisClient 创建 Redis 客户端
func NewRedisClient(conf *Config) *redis.Client {
	return redis.NewClient(&redis.Options{
		Addr:         conf.Data.Redis.Addr,
		Password:     conf.Data.Redis.Password,
		DB:           conf.Data.Redis.DB,
		PoolSize:     conf.Data.Redis.PoolSize,
		MinIdleConns: conf.Data.Redis.MinIdleConns,
	})
}

// Config is application config.
type Config struct {
	Server    ServerConf
	Data      DataConf
	JWTSecret string
}

// ServerConf is server config.
type ServerConf struct {
	HTTP HTTPConf
	GRPC GRPCConf
}

type HTTPConf struct {
	Network string
	Addr    string
	Timeout string
}

type GRPCConf struct {
	Network string
	Addr    string
	Timeout string
}

// DataConf is data config.
type DataConf struct {
	Database data.Config
	Redis    RedisConf
}

type RedisConf struct {
	Addr         string
	Password     string
	DB           int
	PoolSize     int
	MinIdleConns int
	ReadTimeout  string
	WriteTimeout string
}
