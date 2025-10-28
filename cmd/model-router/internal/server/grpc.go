package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/middleware/validate"
	"github.com/go-kratos/kratos/v2/transport/grpc"

	"voicehelper/cmd/model-router/internal/service"
)

// NewGRPCServer 创建gRPC服务器
func NewGRPCServer(
	modelRouterService *service.ModelRouterService,
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

	opts = append(opts, grpc.Address(":9000"))

	srv := grpc.NewServer(opts...)
	// pb.RegisterModelRouterServer(srv, modelRouterService)

	log.NewHelper(logger).Info("gRPC server created on :9000")
	return srv
}
