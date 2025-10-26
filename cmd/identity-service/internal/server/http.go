package server

import (
	pb "voiceassistant/api/proto/identity/v1"
	"voiceassistant/cmd/identity-service/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/http"
)

// NewHTTPServer creates a new HTTP server.
func NewHTTPServer(
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

	// Configure server options
	opts = append(opts, http.Address(":8000"))

	srv := http.NewServer(opts...)

	// Register service (gRPC-Gateway)
	pb.RegisterIdentityHTTPServer(srv, identityService)

	return srv
}
