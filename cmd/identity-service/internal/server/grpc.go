package server

import (
	pb "voiceassistant/api/proto/identity/v1"
	"voiceassistant/cmd/identity-service/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/middleware/validate"
	"github.com/go-kratos/kratos/v2/transport/grpc"
)

// NewGRPCServer creates a new gRPC server.
func NewGRPCServer(
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

	// Configure server options
	opts = append(opts, grpc.Address(":9000"))

	srv := grpc.NewServer(opts...)

	// Register service
	pb.RegisterIdentityServer(srv, identityService)

	return srv
}
