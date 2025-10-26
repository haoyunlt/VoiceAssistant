package main

import (
	"context"
	"flag"
	"os"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/config"
	"github.com/go-kratos/kratos/v2/config/file"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/grpc"
	"github.com/go-kratos/kratos/v2/transport/http"
	
	_ "go.uber.org/automaxprocs"
)

var (
	Name    = "model-router"
	Version = "v2.0.0"
	
	flagconf string
	id, _    = os.Hostname()
)

func init() {
	flag.StringVar(&flagconf, "conf", "../../configs/model-router.yaml", "config path")
}

func newApp(logger log.Logger, gs *grpc.Server, hs *http.Server) *kratos.App {
	return kratos.New(
		kratos.ID(id),
		kratos.Name(Name),
		kratos.Version(Version),
		kratos.Metadata(map[string]string{}),
		kratos.Logger(logger),
		kratos.Server(gs, hs),
	)
}

func main() {
	flag.Parse()
	
	logger := log.With(log.NewStdLogger(os.Stdout),
		"ts", log.DefaultTimestamp,
		"caller", log.DefaultCaller,
		"service.id", id,
		"service.name", Name,
		"service.version", Version,
	)
	
	c := config.New(config.WithSource(file.NewSource(flagconf)))
	defer c.Close()
	
	if err := c.Load(); err != nil {
		panic(err)
	}
	
	httpSrv := http.NewServer(
		http.Address(":8000"),
		http.Middleware(recovery.Recovery(), tracing.Server()),
	)
	
	grpcSrv := grpc.NewServer(
		grpc.Address(":9000"),
		grpc.Middleware(recovery.Recovery(), tracing.Server()),
	)
	
	app := newApp(logger, grpcSrv, httpSrv)
	
	if err := app.Run(); err != nil {
		panic(err)
	}
}
