package main

import (
	"flag"
	"os"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/config"
	"github.com/go-kratos/kratos/v2/config/file"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/transport/grpc"
	"github.com/go-kratos/kratos/v2/transport/http"
)

var (
	// Name is the name of the compiled software.
	Name = "knowledge-service"
	// Version is the version of the compiled software.
	Version = "v1.0.0"

	flagconf string
)

func init() {
	flag.StringVar(&flagconf, "conf", "../../configs/app/knowledge-service.yaml", "config path, eg: -conf config.yaml")
}

func newApp(logger log.Logger, gs *grpc.Server, hs *http.Server) *kratos.App {
	return kratos.New(
		kratos.Name(Name),
		kratos.Version(Version),
		kratos.Metadata(map[string]string{}),
		kratos.Logger(logger),
		kratos.Server(
			gs,
			hs,
		),
	)
}

func main() {
	flag.Parse()

	// 创建日志
	logger := log.With(log.NewStdLogger(os.Stdout),
		"service.name", Name,
		"service.version", Version,
		"ts", log.DefaultTimestamp,
		"caller", log.DefaultCaller,
	)

	// 加载配置
	c := config.New(
		config.WithSource(
			file.NewSource(flagconf),
		),
	)
	defer c.Close()

	if err := c.Load(); err != nil {
		panic(err)
	}

	var conf Config
	if err := c.Scan(&conf); err != nil {
		panic(err)
	}

	// 使用Wire依赖注入初始化应用
	app, cleanup, err := wireApp(&conf, logger)
	if err != nil {
		panic(err)
	}
	defer cleanup()

	// 启动应用
	helper := log.NewHelper(logger)
	helper.Infof("starting %s version %s...", Name, Version)
	helper.Infof("http server: %s, grpc server: %s", conf.Server.HTTP.Addr, conf.Server.GRPC.Addr)

	if err := app.Run(); err != nil {
		helper.Errorf("failed to run app: %v", err)
		panic(err)
	}
}
