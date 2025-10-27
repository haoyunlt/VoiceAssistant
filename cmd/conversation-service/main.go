package main

import (
	"fmt"
	"log"

	"voiceassistant/cmd/conversation-service/internal/data"
	"voiceassistant/pkg/config"
)

func main() {
	// 加载配置（使用统一配置工具）
	dbConfig := &data.DBConfig{
		Host:     config.GetEnv("DB_HOST", "localhost"),
		Port:     config.GetEnvAsInt("DB_PORT", 5432),
		User:     config.GetEnv("DB_USER", "postgres"),
		Password: config.GetEnv("DB_PASSWORD", "postgres"),
		Database: config.GetEnv("DB_NAME", "voiceassistant"),
	}

	// 初始化应用（使用 Wire 生成的代码）
	httpServer, err := initApp(dbConfig)
	if err != nil {
		log.Fatalf("Failed to initialize app: %v", err)
	}

	// 启动服务器
	addr := fmt.Sprintf(":%s", config.GetEnv("PORT", "8080"))
	log.Printf("Starting Conversation Service on %s", addr)

	if err := httpServer.Start(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
