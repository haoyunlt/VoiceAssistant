package server

import (
	"context"
	"net/http"
	"time"
	"voicehelper/cmd/notification-service/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	khttp "github.com/go-kratos/kratos/v2/transport/http"
)

// HTTPConfig is the HTTP server configuration
type HTTPConfig struct {
	Addr    string
	Timeout int
}

// NewHTTPServer creates a new HTTP server
func NewHTTPServer(
	cfg *HTTPConfig,
	notificationService *service.NotificationService,
	logger log.Logger,
) *khttp.Server {
	opts := []khttp.ServerOption{
		khttp.Middleware(
			recovery.Recovery(),
			logging.Server(logger),
		),
	}

	if cfg.Addr != "" {
		opts = append(opts, khttp.Address(cfg.Addr))
	}

	if cfg.Timeout > 0 {
		opts = append(opts, khttp.Timeout(time.Duration(cfg.Timeout)*time.Second))
	}

	srv := khttp.NewServer(opts...)

	// Register health check endpoints
	srv.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"notification-service"}`))
	})

	srv.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ready":true}`))
	})

	// Register notification endpoints
	registerNotificationRoutes(srv, notificationService)

	// TODO: Register protobuf HTTP handlers when proto files are ready
	// pb.RegisterNotificationHTTPServer(srv, notificationService)

	log.NewHelper(logger).Infof("HTTP server created on %s", cfg.Addr)
	return srv
}

// registerNotificationRoutes registers notification HTTP routes
func registerNotificationRoutes(srv *khttp.Server, svc *service.NotificationService) {
	// POST /api/v1/notifications
	srv.HandleFunc("/api/v1/notifications", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// Parse request body
		var req service.SendNotificationRequest
		// TODO: Parse JSON body when implementing

		// Send notification
		resp, err := svc.SendNotification(context.Background(), &req)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		// Return response
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// TODO: Marshal response to JSON
		_ = resp
	})

	// GET /api/v1/notifications (list user notifications)
	// GET /api/v1/notifications/:id (get notification by ID)
	// PUT /api/v1/notifications/:id/read (mark as read)
	// etc.
}
