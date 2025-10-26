package server

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/transport/http"

	"voiceassistant/cmd/notification-service/internal/service"
)

func NewHTTPServer(
	notificationService *service.NotificationService,
	logger log.Logger,
) *http.Server {
	var opts = []http.ServerOption{
		http.Middleware(
			recovery.Recovery(),
			logging.Server(logger),
		),
	}

	opts = append(opts, http.Address(":8000"))

	srv := http.NewServer(opts...)
	// pb.RegisterNotificationHTTPServer(srv, notificationService)

	log.NewHelper(logger).Info("HTTP server created on :8000")
	return srv
}
