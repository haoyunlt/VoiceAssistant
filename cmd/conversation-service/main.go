package main

import (
	"fmt"
	"log"
	"os"

	"conversation-service/internal/data"
)

func main() {
	// 加载配置
	dbConfig := &data.DBConfig{
		Host:     getEnv("DB_HOST", "localhost"),
		Port:     getEnvAsInt("DB_PORT", 5432),
		User:     getEnv("DB_USER", "postgres"),
		Password: getEnv("DB_PASSWORD", "postgres"),
		Database: getEnv("DB_NAME", "voicehelper"),
	}

	// 初始化应用（使用 Wire 生成的代码）
	httpServer, err := initApp(dbConfig)
	if err != nil {
		log.Fatalf("Failed to initialize app: %v", err)
	}

	// 启动服务器
	addr := fmt.Sprintf(":%s", getEnv("PORT", "8080"))
	log.Printf("Starting Conversation Service on %s", addr)

	if err := httpServer.Start(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

// getEnv 获取环境变量
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsInt 获取整型环境变量
func getEnvAsInt(key string, defaultValue int) int {
	valueStr := getEnv(key, "")
	if valueStr == "" {
		return defaultValue
	}

	var value int
	fmt.Sscanf(valueStr, "%d", &value)
	return value
}
