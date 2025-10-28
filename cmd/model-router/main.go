package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"syscall"

	"voicehelper/cmd/model-router/internal/server"
	"voicehelper/pkg/observability"

	"github.com/go-kratos/kratos/v2"
	kratoslog "github.com/go-kratos/kratos/v2/log"
	"gopkg.in/yaml.v3"
)

var (
	flagconf string
)

func init() {
	flag.StringVar(&flagconf, "conf", "configs/model-router.yaml", "config path, eg: -conf config.yaml")
}

func main() {
	flag.Parse()

	// 1. 加载配置
	cfg, err := loadConfig(flagconf)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// 2. 初始化日志
	logger := kratoslog.NewStdLogger(os.Stdout)
	logger = kratoslog.With(logger,
		"service", "model-router",
		"version", "v1.0.0",
		"timestamp", kratoslog.DefaultTimestamp,
		"caller", kratoslog.DefaultCaller,
	)
	helper := kratoslog.NewHelper(logger)

	// 3. 初始化可观测性（OpenTelemetry）
	tracingConfig := observability.TracingConfig{
		ServiceName:    "model-router",
		ServiceVersion: "v1.0.0",
		Environment:    "development",
		Endpoint:       cfg.Observability.Tracing.Endpoint,
		SamplingRate:   cfg.Observability.Tracing.Sampler,
		Enabled:        cfg.Observability.Tracing.Enabled,
	}
	shutdown, err := observability.InitTracing(context.Background(), tracingConfig)
	if err != nil {
		helper.Warnf("Failed to initialize tracing: %v", err)
	} else {
		defer shutdown(context.Background())
	}

	// 4. 使用 Wire 构建应用
	app, cleanup, err := wireApp(cfg, logger)
	if err != nil {
		helper.Fatalf("Failed to wire app: %v", err)
	}
	defer cleanup()

	helper.Infow(
		"msg", "Model Router service starting",
		"http_addr", cfg.Server.HTTP.Addr,
		"grpc_addr", cfg.Server.GRPC.Addr,
	)

	// 5. 启动应用
	if err := app.Run(); err != nil {
		helper.Fatalf("Failed to run app: %v", err)
	}

	helper.Info("Model Router service stopped gracefully")
}

// loadConfig 加载配置文件
func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// 环境变量覆盖
	if addr := os.Getenv("HTTP_ADDR"); addr != "" {
		cfg.Server.HTTP.Addr = addr
	}
	if addr := os.Getenv("GRPC_ADDR"); addr != "" {
		cfg.Server.GRPC.Addr = addr
	}

	return &cfg, nil
}

// newApp 创建 Kratos 应用
func newApp(
	cfg *Config,
	logger kratoslog.Logger,
	httpServer *server.HTTPServer,
) *kratos.App {
	return kratos.New(
		kratos.Name("model-router"),
		kratos.Version("v1.0.0"),
		kratos.Logger(logger),
		kratos.Server(
			// httpServer, // TODO: 适配 Kratos Server 接口
		),
		kratos.Signal(syscall.SIGTERM, syscall.SIGINT),
		kratos.Context(context.Background()),
	)
}
