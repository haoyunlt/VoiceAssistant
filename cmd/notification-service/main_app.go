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
	Name     = "notification-service"
	Version  = "v1.0.0"
	flagconf string
)

func init() {
	flag.StringVar(&flagconf, "conf", "../../configs/app/notification-service.yaml", "config path")
}

func newApp(logger log.Logger, gs *grpc.Server, hs *http.Server) *kratos.App {
	return kratos.New(
		kratos.Name(Name),
		kratos.Version(Version),
		kratos.Logger(logger),
		kratos.Server(gs, hs),
	)
}

func main() {
	flag.Parse()

	logger := log.With(log.NewStdLogger(os.Stdout),
		"service.name", Name,
		"service.version", Version,
		"ts", log.DefaultTimestamp,
		"caller", log.DefaultCaller,
	)

	c := config.New(config.WithSource(file.NewSource(flagconf)))
	defer c.Close()

	if err := c.Load(); err != nil {
		panic(err)
	}

	var conf Config
	if err := c.Scan(&conf); err != nil {
		panic(err)
	}

	app, cleanup, err := wireApp(&conf, logger)
	if err != nil {
		panic(err)
	}
	defer cleanup()

	log.NewHelper(logger).Info("starting notification-service...")
	if err := app.Run(); err != nil {
		panic(err)
	}
}
