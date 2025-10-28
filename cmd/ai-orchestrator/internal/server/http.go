package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	khttp "github.com/go-kratos/kratos/v2/transport/http"

	"voiceassistant/cmd/ai-orchestrator/internal/service"
)

// NewHTTPServer 创建HTTP服务器
func NewHTTPServer(
	orchestratorService *service.OrchestratorService,
	logger log.Logger,
) *khttp.Server {
	opts := []khttp.ServerOption{
		khttp.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
		),
	}

	// 配置服务器地址
	opts = append(opts, khttp.Address(":8000"))

	srv := khttp.NewServer(opts...)

	// 注册HTTP路由
	// pb.RegisterOrchestratorHTTPServer(srv, orchestratorService)
	// 注意：实际需要从proto生成的gRPC-Gateway代码来注册

	log.NewHelper(logger).Info("HTTP server created on :8000")
	return srv
}
