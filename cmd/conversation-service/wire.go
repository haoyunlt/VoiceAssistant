//go:build wireinject
// +build wireinject

package main

import (
	"voiceassistant/cmd/conversation-service/internal/biz"
	"voiceassistant/cmd/conversation-service/internal/data"
	"voiceassistant/cmd/conversation-service/internal/server"
	"voiceassistant/cmd/conversation-service/internal/service"

	"github.com/google/wire"
	"gorm.io/gorm"
)

// initApp 初始化应用
func initApp(dbConfig *data.DBConfig) (*server.HTTPServer, func(), error) {
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

		// Cleanup 函数
		newCleanup,
	)

	return nil, nil, nil
}

// newCleanup 创建清理函数
func newCleanup(db *gorm.DB) func() {
	return func() {
		sqlDB, err := db.DB()
		if err != nil {
			return
		}
		_ = sqlDB.Close()
	}
}
