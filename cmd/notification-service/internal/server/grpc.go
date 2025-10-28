package server

import (
	"time"
	"voicehelper/cmd/notification-service/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/grpc"
)

// GRPCConfig is the GRPC server configuration
type GRPCConfig struct {
	Addr    string
	Timeout int
}

// NewGRPCServer creates a new GRPC server
func NewGRPCServer(
	cfg *GRPCConfig,
	notificationService *service.NotificationService,
	logger log.Logger,
) *grpc.Server {
	opts := []grpc.ServerOption{
		grpc.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
		),
	}

	if cfg.Addr != "" {
		opts = append(opts, grpc.Address(cfg.Addr))
	}

	if cfg.Timeout > 0 {
		opts = append(opts, grpc.Timeout(time.Duration(cfg.Timeout)*time.Second))
	}

	srv := grpc.NewServer(opts...)

	// TODO: Register protobuf GRPC handlers when proto files are ready
	// pb.RegisterNotificationServer(srv, notificationService)

	log.NewHelper(logger).Infof("gRPC server created on %s", cfg.Addr)
	return srv
}
