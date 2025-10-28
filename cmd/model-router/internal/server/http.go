package server

import (
	"net/http"
	"time"

	"voiceassistant/cmd/model-router/internal/service"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
)

// HTTPServer HTTP服务器（简化版）
type HTTPServer struct {
	router  *gin.Engine
	service *service.ModelRouterService
	server  *http.Server
	logger  log.Logger
}

// NewHTTPServer 创建HTTP服务器
func NewHTTPServer(service *service.ModelRouterService, logger log.Logger, addr string) *HTTPServer {
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	httpServer := &HTTPServer{
		router:  router,
		service: service,
		logger:  logger,
	}

	httpServer.registerRoutes()

	// 创建 HTTP 服务器
	httpServer.server = &http.Server{
		Addr:           addr,
		Handler:        router,
		ReadTimeout:    30 * time.Second,
		WriteTimeout:   30 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}

	return httpServer
}

// registerRoutes 注册路由
func (s *HTTPServer) registerRoutes() {
	// 健康检查
	s.router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "model-router",
		})
	})

	s.router.GET("/ready", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "ready",
		})
	})

	// API v1
	v1 := s.router.Group("/api/v1")
	{
		// 路由接口
		v1.POST("/route", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{
				"message": "Route endpoint - not implemented yet",
			})
		})

		// A/B测试接口
		v1.POST("/abtests", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{
				"message": "Create AB test - not implemented yet",
			})
		})

		v1.GET("/abtests", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{
				"tests": []interface{}{},
			})
		})
	}
}

// Start 启动HTTP服务器
func (s *HTTPServer) Start() error {
	helper := log.NewHelper(s.logger)
	helper.Infof("HTTP server listening on %s", s.server.Addr)
	return s.server.ListenAndServe()
}

// Stop 停止HTTP服务器
func (s *HTTPServer) Stop() error {
	return s.server.Close()
}
