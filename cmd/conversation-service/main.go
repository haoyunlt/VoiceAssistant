package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"
	"voiceassistant/cmd/conversation-service/internal/data"
	"voiceassistant/pkg/config"
)

func main() {
	// 获取配置模式（支持 local 或 nacos）
	configMode := config.GetEnv("CONFIG_MODE", "local")
	log.Printf("Starting Conversation Service in %s mode", configMode)

	var cfgManager *config.Manager
	var dbConfig *data.DBConfig

	// 根据配置模式初始化
	if configMode == "nacos" {
		// Nacos 模式：从配置中心加载配置
		configPath := config.GetEnv("CONFIG_PATH", "./configs/conversation-service.yaml")
		serviceName := "conversation-service"

		cfgManager = config.NewManager()
		if err := cfgManager.LoadConfig(configPath, serviceName); err != nil {
			log.Fatalf("Failed to load config from Nacos: %v", err)
		}
		defer cfgManager.Close()

		log.Printf("✅ Config loaded from Nacos")

		// 解析数据库配置
		var dbConfigStruct struct {
			Data struct {
				Database struct {
					Driver string `mapstructure:"driver"`
					Source string `mapstructure:"source"`
					Host   string `mapstructure:"host"`
					Port   int    `mapstructure:"port"`
					User   string `mapstructure:"user"`
					Pass   string `mapstructure:"password"`
					Name   string `mapstructure:"database"`
				} `mapstructure:"database"`
			} `mapstructure:"data"`
		}

		if err := cfgManager.Unmarshal(&dbConfigStruct); err != nil {
			log.Printf("⚠️  Failed to unmarshal database config from Nacos, using environment variables: %v", err)
		}

		// 构建 DBConfig（环境变量优先级最高）
		dbConfig = &data.DBConfig{
			Host:     config.GetEnv("DB_HOST", getOrDefault(dbConfigStruct.Data.Database.Host, "localhost")),
			Port:     config.GetEnvAsInt("DB_PORT", getIntOrDefault(dbConfigStruct.Data.Database.Port, 5432)),
			User:     config.GetEnv("DB_USER", getOrDefault(dbConfigStruct.Data.Database.User, "postgres")),
			Password: config.GetEnv("DB_PASSWORD", getOrDefault(dbConfigStruct.Data.Database.Pass, "postgres")),
			Database: config.GetEnv("DB_NAME", getOrDefault(dbConfigStruct.Data.Database.Name, "voiceassistant")),
		}
	} else {
		// Local 模式：纯环境变量配置
		log.Printf("✅ Using environment variables for configuration")

		dbConfig = &data.DBConfig{
			Host:     config.GetEnv("DB_HOST", "localhost"),
			Port:     config.GetEnvAsInt("DB_PORT", 5432),
			User:     config.GetEnv("DB_USER", "postgres"),
			Password: config.GetEnv("DB_PASSWORD", "postgres"),
			Database: config.GetEnv("DB_NAME", "voiceassistant"),
		}
	}

	// 初始化应用（使用 Wire 生成的代码）
	appComponents, err := initApp(dbConfig)
	if err != nil {
		log.Fatalf("Failed to initialize app: %v", err)
	}

	// 启动服务器
	var addr string
	if cfgManager != nil {
		// 尝试从配置管理器获取端口
		if port := cfgManager.GetString("server.http.addr"); port != "" {
			addr = port
		}
	}
	if addr == "" {
		addr = fmt.Sprintf(":%s", config.GetEnv("PORT", "8080"))
	}

	log.Printf("🚀 Starting Conversation Service on %s", addr)
	log.Printf("   DB: %s@%s:%d/%s", dbConfig.User, dbConfig.Host, dbConfig.Port, dbConfig.Database)

	// 在单独的 goroutine 中启动服务器
	go func() {
		if err := appComponents.Server.Start(addr); err != nil {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// 等待中断信号以优雅关闭服务器
	quit := make(chan os.Signal, 1)
	// 捕获 SIGINT (Ctrl+C) 和 SIGTERM (kill)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("🛑 Shutting down server...")

	// 创建一个带超时的上下文，用于优雅关闭
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 关闭 HTTP 服务器
	if err := appComponents.Server.Shutdown(ctx); err != nil {
		log.Printf("Server forced to shutdown: %v", err)
	}

	// 清理资源（关闭数据库连接等）
	if appComponents.DB != nil {
		sqlDB, err := appComponents.DB.DB()
		if err == nil {
			_ = sqlDB.Close()
		}
	}

	log.Println("✅ Server exited")
}

// getOrDefault 获取字符串值或默认值
func getOrDefault(value, defaultValue string) string {
	if value != "" {
		return value
	}
	return defaultValue
}

// getIntOrDefault 获取整数值或默认值
func getIntOrDefault(value, defaultValue int) int {
	if value != 0 {
		return value
	}
	return defaultValue
}
