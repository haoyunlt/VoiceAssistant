package grpc

import (
	"context"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	kratosgrpc "github.com/go-kratos/kratos/v2/transport/grpc"
	"google.golang.org/grpc"
)

// NewClient creates a new gRPC client.
func NewClient(
	ctx context.Context,
	endpoint string,
	timeout time.Duration,
	logger log.Logger,
	middlewares ...middleware.Middleware,
) (*grpc.ClientConn, error) {
	opts := []kratosgrpc.ClientOption{
		kratosgrpc.WithEndpoint(endpoint),
		kratosgrpc.WithTimeout(timeout),
		kratosgrpc.WithMiddleware(
			recovery.Recovery(),
			tracing.Client(),
			logging.Client(logger),
		),
	}

	if len(middlewares) > 0 {
		opts = append(opts, kratosgrpc.WithMiddleware(middlewares...))
	}

	conn, err := kratosgrpc.DialInsecure(ctx, opts...)
	if err != nil {
		return nil, err
	}

	return conn, nil
}
