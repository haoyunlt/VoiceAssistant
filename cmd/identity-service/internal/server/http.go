package server

import (
	"time"

	"voicehelper/cmd/identity-service/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/http"
)

// HTTPConfig HTTP server configuration
type HTTPConfig struct {
	Network string
	Addr    string
	Timeout string
}

// NewHTTPServer creates a new HTTP server.
func NewHTTPServer(
	cfg *HTTPConfig,
	identityService *service.IdentityService,
	logger log.Logger,
) *http.Server {
	var opts = []http.ServerOption{
		http.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
		),
	}

	// Configure server options from config
	if cfg.Network != "" {
		opts = append(opts, http.Network(cfg.Network))
	}
	if cfg.Addr != "" {
		opts = append(opts, http.Address(cfg.Addr))
	} else {
		opts = append(opts, http.Address(":8000")) // fallback default
	}
	if cfg.Timeout != "" {
		timeout, err := time.ParseDuration(cfg.Timeout)
		if err == nil {
			opts = append(opts, http.Timeout(timeout))
		}
	}

	srv := http.NewServer(opts...)

	// Register service routes
	// Note: Kratos HTTP server requires manual route registration or proto with HTTP annotations
	// For now, we'll register gRPC and let gateway handle HTTP
	// TODO: Add HTTP route registration when needed
	_ = identityService // unused for now

	return srv
}
