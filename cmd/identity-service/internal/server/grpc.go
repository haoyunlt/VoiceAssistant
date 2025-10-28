package server

import (
	"time"

	pb "voicehelper/api/proto/identity/v1"
	"voicehelper/cmd/identity-service/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/middleware/validate"
	"github.com/go-kratos/kratos/v2/transport/grpc"
)

// GRPCConfig gRPC server configuration
type GRPCConfig struct {
	Network string
	Addr    string
	Timeout string
}

// NewGRPCServer creates a new gRPC server.
func NewGRPCServer(
	cfg *GRPCConfig,
	identityService *service.IdentityService,
	logger log.Logger,
) *grpc.Server {
	var opts = []grpc.ServerOption{
		grpc.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
			validate.Validator(),
		),
	}

	// Configure server options from config
	if cfg.Network != "" {
		opts = append(opts, grpc.Network(cfg.Network))
	}
	if cfg.Addr != "" {
		opts = append(opts, grpc.Address(cfg.Addr))
	} else {
		opts = append(opts, grpc.Address(":9000")) // fallback default
	}
	if cfg.Timeout != "" {
		timeout, err := time.ParseDuration(cfg.Timeout)
		if err == nil {
			opts = append(opts, grpc.Timeout(timeout))
		}
	}

	srv := grpc.NewServer(opts...)

	// Register service
	pb.RegisterIdentityServiceServer(srv, identityService)

	return srv
}
