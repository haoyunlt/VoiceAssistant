//go:build wireinject
// +build wireinject

package main

import (
	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
	"github.com/voicehelper/voiceassistant/cmd/model-router/internal/biz"
	"github.com/voicehelper/voiceassistant/cmd/model-router/internal/data"
	"github.com/voicehelper/voiceassistant/cmd/model-router/internal/server"
	"github.com/voicehelper/voiceassistant/cmd/model-router/internal/service"
)

func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		data.NewDB,
		data.NewData,
		data.NewModelRepo,
		data.NewModelMetricsRepo,
		biz.NewModelUsecase,
		biz.NewRouterUsecase,
		service.NewModelRouterService,
		server.NewGRPCServer,
		server.NewHTTPServer,
		newApp,
	))
}

type Config struct {
	Server ServerConf
	Data   DataConf
}

type ServerConf struct {
	HTTP HTTPConf
	GRPC GRPCConf
}

type HTTPConf struct {
	Addr string
}

type GRPCConf struct {
	Addr string
}

type DataConf struct {
	Database data.Config
}
