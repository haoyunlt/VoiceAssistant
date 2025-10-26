package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/http"

	"github.com/voicehelper/voiceassistant/cmd/knowledge-service/internal/service"
)

// NewHTTPServer 创建HTTP服务器
func NewHTTPServer(
	knowledgeService *service.KnowledgeService,
	logger log.Logger,
) *http.Server {
	var opts = []http.ServerOption{
		http.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
		),
	}

	// 配置服务器地址
	opts = append(opts, http.Address(":8000"))

	srv := http.NewServer(opts...)

	// 注册HTTP路由
	// pb.RegisterKnowledgeHTTPServer(srv, knowledgeService)
	// 注意：实际需要从proto生成的gRPC-Gateway代码来注册

	log.NewHelper(logger).Info("HTTP server created on :8000")
	return srv
}
