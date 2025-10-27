package server

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"voiceassistant/cmd/model-router/internal/application"
	"voiceassistant/cmd/model-router/internal/service"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	// Prometheus 指标
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "model_router_http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "model_router_http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path"},
	)

	routingDecisions = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "model_router_routing_decisions_total",
			Help: "Total number of routing decisions",
		},
		[]string{"strategy", "model_id", "success"},
	)
)

func init() {
	// 注册 Prometheus 指标
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
	prometheus.MustRegister(routingDecisions)
}

// HTTPServer HTTP服务器
type HTTPServer struct {
	router  *gin.Engine
	service *service.ModelRouterService
	server  *http.Server
	logger  log.Logger
}

// NewHTTPServer 创建HTTP服务器
func NewHTTPServer(service *service.ModelRouterService, logger log.Logger, addr string) *HTTPServer {
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()

	// 使用自定义中间件
	router.Use(gin.Recovery())
	router.Use(loggingMiddleware(logger))
	router.Use(metricsMiddleware())

	server := &HTTPServer{
		router:  router,
		service: service,
		logger:  logger,
	}

	server.registerRoutes()

	// 创建 HTTP 服务器
	server.server = &http.Server{
		Addr:           addr,
		Handler:        router,
		ReadTimeout:    30 * time.Second,
		WriteTimeout:   30 * time.Second,
		MaxHeaderBytes: 1 << 20, // 1MB
	}

	return server
}

// registerRoutes 注册路由
func (s *HTTPServer) registerRoutes() {
	// Prometheus metrics
	s.router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Health check
	s.router.GET("/health", s.healthCheck)
	s.router.GET("/ready", s.readinessCheck)

	// API v1
	v1 := s.router.Group("/api/v1")
	{
		// 路由决策
		v1.POST("/route", s.route)

		// 模型管理
		v1.GET("/models", s.listModels)
		v1.GET("/models/:id", s.getModel)

		// 使用统计
		v1.POST("/usage", s.recordUsage)
		v1.GET("/usage/stats", s.getUsageStats)

		// 成本管理
		v1.POST("/cost/predict", s.predictCost)
		v1.POST("/cost/compare", s.compareCosts)
		v1.GET("/cost/recommendations", s.getRecommendations)

		// 熔断器状态
		v1.GET("/circuit-breakers", s.getCircuitStates)
	}
}

// healthCheck 健康检查
func (s *HTTPServer) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "healthy",
		"service": "model-router",
		"time":    time.Now().Format(time.RFC3339),
	})
}

// readinessCheck 就绪检查
func (s *HTTPServer) readinessCheck(c *gin.Context) {
	// TODO: 检查依赖服务（数据库、Redis 等）
	c.JSON(http.StatusOK, gin.H{
		"ready": true,
		"checks": gin.H{
			"database": "ok",
			"redis":    "ok",
			"models":   "ok",
		},
	})
}

// route 路由决策
func (s *HTTPServer) route(c *gin.Context) {
	var req application.RoutingRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	response, err := s.service.Route(c.Request.Context(), &req)
	if err != nil {
		routingDecisions.WithLabelValues(string(req.Strategy), "", "false").Inc()
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 记录 Prometheus 指标
	routingDecisions.WithLabelValues(string(req.Strategy), response.ModelID, "true").Inc()

	c.JSON(http.StatusOK, response)
}

// listModels 列出所有模型
func (s *HTTPServer) listModels(c *gin.Context) {
	models := s.service.ListModels(c.Request.Context())
	c.JSON(http.StatusOK, gin.H{
		"models": models,
		"count":  len(models),
	})
}

// getModel 获取模型信息
func (s *HTTPServer) getModel(c *gin.Context) {
	modelID := c.Param("id")

	model, err := s.service.GetModelInfo(c.Request.Context(), modelID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, model)
}

// recordUsage 记录使用情况
func (s *HTTPServer) recordUsage(c *gin.Context) {
	var req struct {
		ModelID      string `json:"model_id" binding:"required"`
		InputTokens  int    `json:"input_tokens" binding:"required"`
		OutputTokens int    `json:"output_tokens" binding:"required"`
		Success      bool   `json:"success"`
		Latency      int64  `json:"latency"` // milliseconds
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	err := s.service.RecordUsage(
		c.Request.Context(),
		req.ModelID,
		req.InputTokens,
		req.OutputTokens,
		req.Success,
		req.Latency,
	)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Usage recorded successfully"})
}

// getUsageStats 获取使用统计
func (s *HTTPServer) getUsageStats(c *gin.Context) {
	stats := s.service.GetUsageStats(c.Request.Context())
	if stats == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Usage stats not available"})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// predictCost 预测成本
func (s *HTTPServer) predictCost(c *gin.Context) {
	var req struct {
		ModelID      string `json:"model_id" binding:"required"`
		InputTokens  int    `json:"input_tokens" binding:"required"`
		OutputTokens int    `json:"output_tokens" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	cost, err := s.service.PredictCost(
		c.Request.Context(),
		req.ModelID,
		req.InputTokens,
		req.OutputTokens,
	)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"model_id":      req.ModelID,
		"input_tokens":  req.InputTokens,
		"output_tokens": req.OutputTokens,
		"cost":          cost,
		"currency":      "USD",
	})
}

// compareCosts 比较成本
func (s *HTTPServer) compareCosts(c *gin.Context) {
	var req struct {
		ModelIDs     []string `json:"model_ids" binding:"required"`
		InputTokens  int      `json:"input_tokens" binding:"required"`
		OutputTokens int      `json:"output_tokens" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	costs, err := s.service.CompareCosts(
		c.Request.Context(),
		req.ModelIDs,
		req.InputTokens,
		req.OutputTokens,
	)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"input_tokens":  req.InputTokens,
		"output_tokens": req.OutputTokens,
		"costs":         costs,
		"currency":      "USD",
	})
}

// getRecommendations 获取优化建议
func (s *HTTPServer) getRecommendations(c *gin.Context) {
	recommendations := s.service.GetRecommendations(c.Request.Context())
	c.JSON(http.StatusOK, gin.H{
		"recommendations": recommendations,
		"count":           len(recommendations),
	})
}

// getCircuitStates 获取熔断器状态
func (s *HTTPServer) getCircuitStates(c *gin.Context) {
	states := s.service.GetCircuitStates(c.Request.Context())
	c.JSON(http.StatusOK, gin.H{
		"circuit_breakers": states,
	})
}

// Start 启动服务器
func (s *HTTPServer) Start() error {
	helper := log.NewHelper(s.logger)
	helper.Infof("HTTP server listening on %s", s.server.Addr)

	if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return fmt.Errorf("failed to start HTTP server: %w", err)
	}
	return nil
}

// Shutdown 优雅关闭服务器
func (s *HTTPServer) Shutdown(ctx context.Context) error {
	helper := log.NewHelper(s.logger)
	helper.Info("Shutting down HTTP server...")

	if err := s.server.Shutdown(ctx); err != nil {
		return fmt.Errorf("failed to shutdown HTTP server: %w", err)
	}

	helper.Info("HTTP server stopped")
	return nil
}

// loggingMiddleware 日志中间件
func loggingMiddleware(logger log.Logger) gin.HandlerFunc {
	helper := log.NewHelper(logger)

	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method

		c.Next()

		latency := time.Since(start)
		statusCode := c.Writer.Status()

		helper.Infow(
			"method", method,
			"path", path,
			"status", statusCode,
			"latency", latency.String(),
			"client_ip", c.ClientIP(),
		)
	}
}

// metricsMiddleware Prometheus 指标中间件
func metricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.FullPath() // 使用路由模板而不是实际路径
		if path == "" {
			path = c.Request.URL.Path
		}
		method := c.Request.Method

		c.Next()

		duration := time.Since(start).Seconds()
		status := fmt.Sprintf("%d", c.Writer.Status())

		httpRequestsTotal.WithLabelValues(method, path, status).Inc()
		httpRequestDuration.WithLabelValues(method, path).Observe(duration)
	}
}
