package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/http"

	"github.com/voicehelper/voiceassistant/cmd/model-router/internal/service"
)

// NewHTTPServer 创建HTTP服务器
func NewHTTPServer(
	modelRouterService *service.ModelRouterService,
	logger log.Logger,
) *http.Server {
	var opts = []http.ServerOption{
		http.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
		),
	}

	opts = append(opts, http.Address(":8000"))

	srv := http.NewServer(opts...)
	// pb.RegisterModelRouterHTTPServer(srv, modelRouterService)

	log.NewHelper(logger).Info("HTTP server created on :8000")
	return srv
}
