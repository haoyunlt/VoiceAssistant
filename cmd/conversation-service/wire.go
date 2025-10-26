//go:build wireinject
// +build wireinject

package main

import (
	"conversation-service/internal/biz"
	"conversation-service/internal/data"
	"conversation-service/internal/server"
	"conversation-service/internal/service"

	"github.com/google/wire"
)

// initApp 初始化应用
func initApp(dbConfig *data.DBConfig) (*server.HTTPServer, error) {
	wire.Build(
		// Data 层
		data.NewDB,
		data.NewConversationRepository,
		data.NewMessageRepository,

		// Biz 层
		biz.NewConversationUsecase,
		biz.NewMessageUsecase,

		// Service 层
		service.NewConversationService,

		// Server 层
		server.NewHTTPServer,
	)

	return nil, nil
}
