package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/middleware/validate"
	"github.com/go-kratos/kratos/v2/transport/grpc"

	"voiceassistant/cmd/knowledge-service/internal/service"
)

// GRPCConfig gRPC服务器配置
type GRPCConfig struct {
	Network string
	Addr    string
	Timeout string
}

// NewGRPCServer 创建gRPC服务器
func NewGRPCServer(
	config *GRPCConfig,
	knowledgeService *service.KnowledgeService,
	logger log.Logger,
) *grpc.Server {
	opts := []grpc.ServerOption{
		grpc.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
			validate.Validator(),
		),
	}

	// 配置服务器地址和超时
	if config.Network != "" {
		opts = append(opts, grpc.Network(config.Network))
	}
	if config.Addr != "" {
		opts = append(opts, grpc.Address(config.Addr))
	}
	if config.Timeout != "" {
		opts = append(opts, grpc.Timeout(parseDuration(config.Timeout)))
	}

	srv := grpc.NewServer(opts...)

	// 注册服务
	// TODO: 生成proto后取消注释
	// pb.RegisterKnowledgeServer(srv, knowledgeService)

	log.NewHelper(logger).Infof("gRPC server created on %s", config.Addr)
	return srv
}
