//go:build wireinject
// +build wireinject

// The build tag makes sure the stub is not built in the final build.

package main

import (
	"voiceassistant/cmd/knowledge-service/internal/biz"
	"voiceassistant/cmd/knowledge-service/internal/data"
	"voiceassistant/cmd/knowledge-service/internal/server"
	"voiceassistant/cmd/knowledge-service/internal/service"

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
		data.NewKnowledgeBaseRepo,
		data.NewDocumentRepo,
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

// Config is application config.
type Config struct {
	Server ServerConf
	Data   DataConf
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
}
