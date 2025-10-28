package app

import (
	"context"
	"voicehelper/cmd/analytics-service/internal/data"
	"voicehelper/cmd/analytics-service/internal/server"

	"go.uber.org/zap"
)

// App 应用程序
type App struct {
	Logger     *zap.Logger
	HTTPServer *server.HTTPServer
	DB         *data.DB
	ClickHouse *data.ClickHouseClient
}

// Cleanup 清理资源
func (a *App) Cleanup() error {
	a.Logger.Info("Cleaning up resources...")

	// 关闭数据库连接
	if a.DB != nil {
		if err := a.DB.Close(); err != nil {
			a.Logger.Error("Failed to close database", zap.Error(err))
		}
	}

	// 关闭 ClickHouse 连接
	if a.ClickHouse != nil {
		if err := a.ClickHouse.Close(); err != nil {
			a.Logger.Error("Failed to close ClickHouse", zap.Error(err))
		}
	}

	return nil
}

// NewApp 创建应用程序
func NewApp(
	logger *zap.Logger,
	httpServer *server.HTTPServer,
	db *data.DB,
	clickHouse *data.ClickHouseClient,
) *App {
	return &App{
		Logger:     logger,
		HTTPServer: httpServer,
		DB:         db,
		ClickHouse: clickHouse,
	}
}

// Start 启动应用
func (a *App) Start(ctx context.Context) error {
	a.Logger.Info("Application started successfully")
	return nil
}
