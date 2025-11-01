package main

import (
	"flag"
	"os"
	"syscall"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/config"
	"github.com/go-kratos/kratos/v2/config/file"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/grpc"
	"github.com/go-kratos/kratos/v2/transport/http"

	_ "go.uber.org/automaxprocs"
)

// go build -ldflags "-X main.Version=x.y.z"
var (
	// Name is the name of the compiled software.
	Name string = "ai-orchestrator"
	// Version is the version of the compiled software.
	Version string = "v1.0.0"
	// flagconf is the config flag.
	flagconf string

	id, _ = os.Hostname()
)

func init() {
	flag.StringVar(&flagconf, "conf", "../../configs/app/ai-orchestrator.yaml", "config path, eg: -conf config.yaml")
}

func main() {
	flag.Parse()
	logger := log.With(log.NewStdLogger(os.Stdout),
		"ts", log.DefaultTimestamp,
		"caller", log.DefaultCaller,
		"service.id", id,
		"service.name", Name,
		"service.version", Version,
		"trace.id", tracing.TraceID(),
		"span.id", tracing.SpanID(),
	)
	helper := log.NewHelper(logger)

	// 加载配置
	c := config.New(
		config.WithSource(
			file.NewSource(flagconf),
		),
	)
	defer c.Close()

	if err := c.Load(); err != nil {
		helper.Fatalf("Failed to load config from %s: %v", flagconf, err)
	}

	var bc Config
	if err := c.Scan(&bc); err != nil {
		helper.Fatalf("Failed to scan config: %v", err)
	}

	helper.Infof("config loaded: %+v", bc)

	// 使用Wire构建应用
	app, cleanup, err := wireApp(&bc, logger)
	if err != nil {
		helper.Fatalf("Failed to initialize application: %v", err)
	}
	defer cleanup()

	// 启动应用
	helper.Infof("Starting %s %s", Name, Version)
	if err := app.Run(); err != nil {
		helper.Fatalf("Failed to run application: %v", err)
	}
}

// newApp 创建Kratos应用
func newApp(logger log.Logger, gs *grpc.Server, hs *http.Server) *kratos.App {
	return kratos.New(
		kratos.ID(id),
		kratos.Name(Name),
		kratos.Version(Version),
		kratos.Metadata(map[string]string{}),
		kratos.Logger(logger),
		kratos.Server(
			gs,
			hs,
		),
		kratos.Signal(syscall.SIGTERM, syscall.SIGINT),
	)
}
