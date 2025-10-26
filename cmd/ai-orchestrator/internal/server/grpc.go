package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/middleware/validate"
	"github.com/go-kratos/kratos/v2/transport/grpc"

	"github.com/voicehelper/voiceassistant/cmd/ai-orchestrator/internal/service"
)

// NewGRPCServer 创建gRPC服务器
func NewGRPCServer(
	orchestratorService *service.OrchestratorService,
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

	// 配置服务器地址
	opts = append(opts, grpc.Address(":9000"))

	srv := grpc.NewServer(opts...)

	// 注册服务
	// pb.RegisterOrchestratorServer(srv, orchestratorService)
	// 注意：实际需要从proto生成的代码来注册

	log.NewHelper(logger).Info("gRPC server created on :9000")
	return srv
}
