//go:build wireinject
// +build wireinject

// The build tag makes sure the stub is not built in the final build.

package main

import (
	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/biz"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/data"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/server"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/service"
)

// wireApp init kratos application.
func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
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
	ReadTimeout  string
	WriteTimeout string
}
