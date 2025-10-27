//go:build wireinject
// +build wireinject

package main

import (
	"voiceassistant/cmd/notification-service/internal/biz"
	"voiceassistant/cmd/notification-service/internal/data"
	"voiceassistant/cmd/notification-service/internal/server"
	"voiceassistant/cmd/notification-service/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

func wireApp(*Config, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		data.NewDB,
		data.NewData,
		biz.NewNotificationUsecase,
		biz.NewTemplateUsecase,
		service.NewNotificationService,
		server.NewGRPCServer,
		server.NewHTTPServer,
		newApp,
	))
}
