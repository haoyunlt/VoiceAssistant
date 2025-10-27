//go:build wireinject
// +build wireinject

package main

import (
	"voiceassistant/cmd/conversation-service/internal/biz"
	"voiceassistant/cmd/conversation-service/internal/data"
	"voiceassistant/cmd/conversation-service/internal/server"
	"voiceassistant/cmd/conversation-service/internal/service"

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
