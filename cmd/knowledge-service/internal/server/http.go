package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/middleware/validate"
	"github.com/go-kratos/kratos/v2/transport/http"

	"voiceassistant/cmd/knowledge-service/internal/service"
)

// HTTPConfig HTTP服务器配置
type HTTPConfig struct {
	Network string
	Addr    string
	Timeout string
}

// NewHTTPServer 创建HTTP服务器
func NewHTTPServer(
	config *HTTPConfig,
	knowledgeService *service.KnowledgeService,
	logger log.Logger,
) *http.Server {
	opts := []http.ServerOption{
		http.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
			validate.Validator(),
		),
	}

	// 配置服务器地址和超时
	if config.Network != "" {
		opts = append(opts, http.Network(config.Network))
	}
	if config.Addr != "" {
		opts = append(opts, http.Address(config.Addr))
	}
	if config.Timeout != "" {
		opts = append(opts, http.Timeout(parseDuration(config.Timeout)))
	}

	srv := http.NewServer(opts...)

	// 注册HTTP路由
	// TODO: 生成proto后取消注释
	// pb.RegisterKnowledgeHTTPServer(srv, knowledgeService)

	log.NewHelper(logger).Infof("HTTP server created on %s", config.Addr)
	return srv
}
