package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/tracing"
	"github.com/go-kratos/kratos/v2/transport/grpc"

	"github.com/voicehelper/voiceassistant/cmd/notification-service/internal/service"
)

func NewGRPCServer(
	notificationService *service.NotificationService,
	logger log.Logger,
) *grpc.Server {
	var opts = []grpc.ServerOption{
		grpc.Middleware(
			recovery.Recovery(),
			tracing.Server(),
			logging.Server(logger),
		),
	}

	opts = append(opts, grpc.Address(":9000"))

	srv := grpc.NewServer(opts...)
	// pb.RegisterNotificationServer(srv, notificationService)

	log.NewHelper(logger).Info("gRPC server created on :9000")
	return srv
}
