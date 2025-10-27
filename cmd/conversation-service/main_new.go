package main

import (
	"fmt"
	"log"
	"os"

	"voiceassistant/cmd/conversation-service/internal/data"

	"voiceassistant/pkg/config"
)

func main() {
	// 配置文件路径（本地配置或Nacos连接配置）
	configPath := getEnv("CONFIG_PATH", "./configs/conversation-service.yaml")
	serviceName := "conversation-service"

	// 初始化配置管理器
	cfgManager := config.NewManager()
	if err := cfgManager.LoadConfig(configPath, serviceName); err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}
	defer cfgManager.Close()

	log.Printf("Config mode: %s", cfgManager.GetMode())

	// 解析数据库配置
	var dbConfig struct {
		Data struct {
			Database struct {
				Driver string `mapstructure:"driver"`
				Source string `mapstructure:"source"`
			} `mapstructure:"database"`
		} `mapstructure:"data"`
	}

	if err := cfgManager.Unmarshal(&dbConfig); err != nil {
		log.Fatalf("Failed to unmarshal database config: %v", err)
	}

	// 构建 DBConfig（环境变量可以覆盖）
	finalDBConfig := &data.DBConfig{
		Host:     getEnv("DB_HOST", "localhost"),
		Port:     getEnvAsInt("DB_PORT", 5432),
		User:     getEnv("DB_USER", "postgres"),
		Password: getEnv("DB_PASSWORD", "postgres"),
		Database: getEnv("DB_NAME", "voiceassistant"),
	}

	// 初始化应用（使用 Wire 生成的代码）
	httpServer, err := initApp(finalDBConfig)
	if err != nil {
		log.Fatalf("Failed to initialize app: %v", err)
	}

	// 启动服务器
	port := cfgManager.GetString("server.http.addr")
	if port == "" {
		port = fmt.Sprintf(":%s", getEnv("PORT", "8080"))
	}

	log.Printf("Starting Conversation Service on %s", port)

	if err := httpServer.Start(port); err != nil {
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
