package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"voiceassistant/cmd/analytics-service/internal/conf"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

var configFile = flag.String("config", "", "配置文件路径")

func main() {
	flag.Parse()

	// 加载配置
	config, err := conf.Load(*configFile)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// 初始化日志
	logger, err := initLogger(config.Observability)
	if err != nil {
		log.Fatalf("Failed to init logger: %v", err)
	}
	defer logger.Sync()

	logger.Info("Starting Analytics Service",
		zap.String("version", config.Observability.ServiceVersion),
		zap.String("environment", config.Observability.Environment),
	)

	// 初始化应用（通过 Wire 生成）
	app, cleanup, err := initApp(config, logger)
	if err != nil {
		logger.Fatal("Failed to initialize app", zap.Error(err))
	}
	defer cleanup()

	// 启动 HTTP 服务器
	httpAddr := fmt.Sprintf(":%d", config.Server.HTTPPort)
	srv := &http.Server{
		Addr:         httpAddr,
		Handler:      app.HTTPServer.Engine(),
		ReadTimeout:  config.Server.ReadTimeout,
		WriteTimeout: config.Server.WriteTimeout,
	}

	// 启动 Prometheus metrics 服务器
	metricsAddr := ":8006"
	metricsSrv := &http.Server{
		Addr:    metricsAddr,
		Handler: promhttp.Handler(),
	}

	// 启动服务
	go func() {
		logger.Info("HTTP server starting", zap.String("addr", httpAddr))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("HTTP server failed", zap.Error(err))
		}
	}()

	go func() {
		logger.Info("Metrics server starting", zap.String("addr", metricsAddr))
		if err := metricsSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Metrics server failed", zap.Error(err))
		}
	}()

	// 等待中断信号
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down servers...")

	// 优雅关闭
	ctx, cancel := context.WithTimeout(context.Background(), config.Server.ShutdownTimeout)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Error("HTTP server shutdown failed", zap.Error(err))
	}

	if err := metricsSrv.Shutdown(ctx); err != nil {
		logger.Error("Metrics server shutdown failed", zap.Error(err))
	}

	logger.Info("Servers exited")
}

// initLogger 初始化日志
func initLogger(cfg conf.ObservabilityConfig) (*zap.Logger, error) {
	var zapConfig zap.Config

	if cfg.LogFormat == "json" {
		zapConfig = zap.NewProductionConfig()
	} else {
		zapConfig = zap.NewDevelopmentConfig()
	}

	// 设置日志级别
	level, err := zap.ParseAtomicLevel(cfg.LogLevel)
	if err != nil {
		level = zap.NewAtomicLevelAt(zap.InfoLevel)
	}
	zapConfig.Level = level

	// 添加字段
	zapConfig.InitialFields = map[string]interface{}{
		"service":     cfg.ServiceName,
		"version":     cfg.ServiceVersion,
		"environment": cfg.Environment,
	}

	return zapConfig.Build()
}
