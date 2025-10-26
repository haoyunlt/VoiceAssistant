package grpc

import (
	"context"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/grpc"
)

// NewClient creates a new gRPC client.
func NewClient(
	ctx context.Context,
	endpoint string,
	timeout time.Duration,
	logger log.Logger,
	middlewares ...middleware.Middleware,
) (*grpc.ClientConn, error) {
	opts := []grpc.ClientOption{
		grpc.WithEndpoint(endpoint),
		grpc.WithTimeout(timeout),
		grpc.WithMiddleware(
			recovery.Recovery(),
			tracing.Client(),
			logging.Client(logger),
		),
	}

	if len(middlewares) > 0 {
		opts = append(opts, grpc.WithMiddleware(middlewares...))
	}

	conn, err := grpc.DialInsecure(ctx, opts...)
	if err != nil {
		return nil, err
	}

	return conn, nil
}
