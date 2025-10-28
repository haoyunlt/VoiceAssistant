package main

import (
	"context"
	"flag"
	"os"
	"syscall"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/config"
	"github.com/go-kratos/kratos/v2/config/file"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/transport/grpc"
	"github.com/go-kratos/kratos/v2/transport/http"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.4.0"
)

var (
	Name    = "notification-service"
	Version = "v1.0.0"

	flagConf string
)

func init() {
	flag.StringVar(&flagConf, "conf", "../../configs/notification-service.yaml", "config path, eg: -conf config.yaml")
}

func main() {
	flag.Parse()

	// Initialize logger
	logger := log.With(log.NewStdLogger(os.Stdout),
		"service.name", Name,
		"service.version", Version,
		"ts", log.DefaultTimestamp,
		"caller", log.DefaultCaller,
	)

	// Load configuration
	c := config.New(
		config.WithSource(
			file.NewSource(flagConf),
		),
	)
	defer c.Close()

	if err := c.Load(); err != nil {
		log.NewHelper(logger).Fatalf("failed to load config: %v", err)
	}

	var cfg Config
	if err := c.Scan(&cfg); err != nil {
		log.NewHelper(logger).Fatalf("failed to scan config: %v", err)
	}

	// Initialize OpenTelemetry
	tp, err := initTracer()
	if err != nil {
		log.NewHelper(logger).Errorf("failed to initialize tracer: %v", err)
	}
	if tp != nil {
		defer func() {
			if err := tp.Shutdown(context.Background()); err != nil {
				log.NewHelper(logger).Errorf("failed to shutdown tracer: %v", err)
			}
		}()
	}

	// Initialize app with dependency injection
	app, cleanup, err := wireApp(&cfg, logger)
	if err != nil {
		log.NewHelper(logger).Fatalf("failed to initialize app: %v", err)
	}
	defer cleanup()

	// Start and wait for stop signal
	if err := app.Run(); err != nil {
		log.NewHelper(logger).Fatalf("failed to run app: %v", err)
	}
}

// newApp creates a new kratos application
func newApp(logger log.Logger, hs *http.Server, gs *grpc.Server) *kratos.App {
	return kratos.New(
		kratos.ID(Name),
		kratos.Name(Name),
		kratos.Version(Version),
		kratos.Metadata(map[string]string{}),
		kratos.Logger(logger),
		kratos.Server(
			hs,
			gs,
		),
		kratos.Signal(
			syscall.SIGINT,
			syscall.SIGTERM,
		),
	)
}

// initTracer initializes OpenTelemetry tracer
func initTracer() (*sdktrace.TracerProvider, error) {
	// Check if OTEL endpoint is configured
	if os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == "" {
		return nil, nil // Skip if not configured
	}

	exporter, err := otlptracehttp.New(
		context.Background(),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceNameKey.String(Name),
			semconv.ServiceVersionKey.String(Version),
		)),
	)

	otel.SetTracerProvider(tp)
	return tp, nil
}
