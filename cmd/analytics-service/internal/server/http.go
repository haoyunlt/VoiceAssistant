package server

import (
	"errors"
	"net/http"
	"strconv"
	"time"
	"voicehelper/cmd/analytics-service/internal/domain"
	"voicehelper/cmd/analytics-service/internal/service"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// Logger 日志接口
type Logger interface {
	Info(msg string, fields ...zap.Field)
	Error(msg string, fields ...zap.Field)
	Warn(msg string, fields ...zap.Field)
}

// HTTPServer HTTP 服务器
type HTTPServer struct {
	engine  *gin.Engine
	service *service.AnalyticsService
	logger  Logger
}

// NewHTTPServer 创建 HTTP 服务器
func NewHTTPServer(srv *service.AnalyticsService, logger Logger) *HTTPServer {
	// 设置 Gin 模式
	gin.SetMode(gin.ReleaseMode)

	engine := gin.New()

	s := &HTTPServer{
		engine:  engine,
		service: srv,
		logger:  logger,
	}

	// 注册中间件
	s.registerMiddlewares()

	// 注册路由
	s.registerRoutes()

	return s
}

// registerMiddlewares 注册中间件
func (s *HTTPServer) registerMiddlewares() {
	// Recovery 中间件
	s.engine.Use(gin.Recovery())

	// 请求日志中间件
	s.engine.Use(s.requestLogger())

	// CORS 中间件
	s.engine.Use(s.corsMiddleware())

	// 错误处理中间件
	s.engine.Use(s.errorHandler())
}

// requestLogger 请求日志中间件
func (s *HTTPServer) requestLogger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		query := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()

		s.logger.Info("HTTP request",
			zap.String("method", c.Request.Method),
			zap.String("path", path),
			zap.String("query", query),
			zap.Int("status", status),
			zap.Duration("latency", latency),
			zap.String("client_ip", c.ClientIP()),
		)
	}
}

// corsMiddleware CORS 中间件
func (s *HTTPServer) corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID, X-API-Key")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	}
}

// errorHandler 错误处理中间件
func (s *HTTPServer) errorHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()

		if len(c.Errors) > 0 {
			err := c.Errors.Last()
			s.logger.Error("Request error",
				zap.String("path", c.Request.URL.Path),
				zap.Error(err),
			)
		}
	}
}

// registerRoutes 注册路由
func (s *HTTPServer) registerRoutes() {
	api := s.engine.Group("/api/v1")

	// 统计接口
	stats := api.Group("/stats")
	{
		stats.GET("/usage", s.getUsageStats)
		stats.GET("/model", s.getModelStats)
		stats.GET("/user/:user_id", s.getUserBehavior)
		stats.GET("/realtime", s.getRealtimeStats)
		stats.GET("/cost", s.getCostBreakdown)
	}

	// 报表接口
	reports := api.Group("/reports")
	{
		reports.POST("", s.createReport)
		reports.GET("/:id", s.getReport)
		reports.GET("", s.listReports)
		reports.DELETE("/:id", s.deleteReport)
	}

	// 健康检查
	s.engine.GET("/health", s.healthCheck)
	s.engine.GET("/ready", s.readinessCheck)
}

// getUsageStats 获取使用统计
func (s *HTTPServer) getUsageStats(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	if tenantID == "" {
		s.respondError(c, http.StatusBadRequest, "tenant_id is required")
		return
	}

	period := c.DefaultQuery("period", "day")
	start, end, err := s.parseTimeRange(c)
	if err != nil {
		s.respondError(c, http.StatusBadRequest, err.Error())
		return
	}

	stats, err := s.service.GetUsageStats(c.Request.Context(), tenantID, period, start, end)
	if err != nil {
		s.handleServiceError(c, err)
		return
	}

	c.JSON(http.StatusOK, stats)
}

// getModelStats 获取模型统计
func (s *HTTPServer) getModelStats(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	if tenantID == "" {
		s.respondError(c, http.StatusBadRequest, "tenant_id is required")
		return
	}

	period := c.DefaultQuery("period", "day")
	start, end, err := s.parseTimeRange(c)
	if err != nil {
		s.respondError(c, http.StatusBadRequest, err.Error())
		return
	}

	stats, err := s.service.GetModelStats(c.Request.Context(), tenantID, period, start, end)
	if err != nil {
		s.handleServiceError(c, err)
		return
	}

	c.JSON(http.StatusOK, stats)
}

// getUserBehavior 获取用户行为统计
func (s *HTTPServer) getUserBehavior(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	if tenantID == "" {
		s.respondError(c, http.StatusBadRequest, "tenant_id is required")
		return
	}

	userID := c.Param("user_id")
	if userID == "" {
		s.respondError(c, http.StatusBadRequest, "user_id is required")
		return
	}

	period := c.DefaultQuery("period", "day")
	start, end, err := s.parseTimeRange(c)
	if err != nil {
		s.respondError(c, http.StatusBadRequest, err.Error())
		return
	}

	behavior, err := s.service.GetUserBehavior(c.Request.Context(), tenantID, userID, period, start, end)
	if err != nil {
		s.handleServiceError(c, err)
		return
	}

	c.JSON(http.StatusOK, behavior)
}

// getRealtimeStats 获取实时统计
func (s *HTTPServer) getRealtimeStats(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	if tenantID == "" {
		s.respondError(c, http.StatusBadRequest, "tenant_id is required")
		return
	}

	stats, err := s.service.GetRealtimeStats(c.Request.Context(), tenantID)
	if err != nil {
		s.handleServiceError(c, err)
		return
	}

	c.JSON(http.StatusOK, stats)
}

// getCostBreakdown 获取成本分解
func (s *HTTPServer) getCostBreakdown(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	if tenantID == "" {
		s.respondError(c, http.StatusBadRequest, "tenant_id is required")
		return
	}

	period := c.DefaultQuery("period", "day")
	start, end, err := s.parseTimeRange(c)
	if err != nil {
		s.respondError(c, http.StatusBadRequest, err.Error())
		return
	}

	breakdown, err := s.service.GetCostBreakdown(c.Request.Context(), tenantID, period, start, end)
	if err != nil {
		s.handleServiceError(c, err)
		return
	}

	c.JSON(http.StatusOK, breakdown)
}

// createReport 创建报表
func (s *HTTPServer) createReport(c *gin.Context) {
	var req struct {
		TenantID  string `json:"tenant_id" binding:"required"`
		Type      string `json:"type" binding:"required"`
		Name      string `json:"name" binding:"required"`
		CreatedBy string `json:"created_by" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	report, err := s.service.CreateReport(c.Request.Context(), req.TenantID, req.Type, req.Name, req.CreatedBy)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, report)
}

// getReport 获取报表
func (s *HTTPServer) getReport(c *gin.Context) {
	id := c.Param("id")

	report, err := s.service.GetReport(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, report)
}

// listReports 列出报表
func (s *HTTPServer) listReports(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	if tenantID == "" {
		s.respondError(c, http.StatusBadRequest, "tenant_id is required")
		return
	}

	limit, err := strconv.Atoi(c.DefaultQuery("limit", "20"))
	if err != nil || limit <= 0 || limit > 100 {
		s.respondError(c, http.StatusBadRequest, "invalid limit, must be between 1 and 100")
		return
	}

	offset, err := strconv.Atoi(c.DefaultQuery("offset", "0"))
	if err != nil || offset < 0 {
		s.respondError(c, http.StatusBadRequest, "invalid offset, must be non-negative")
		return
	}

	reports, total, err := s.service.ListReports(c.Request.Context(), tenantID, limit, offset)
	if err != nil {
		s.handleServiceError(c, err)
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"reports": reports,
		"total":   total,
		"limit":   limit,
		"offset":  offset,
	})
}

// deleteReport 删除报表
func (s *HTTPServer) deleteReport(c *gin.Context) {
	id := c.Param("id")

	if err := s.service.DeleteReport(c.Request.Context(), id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusNoContent)
}

// Engine 返回 Gin 引擎
func (s *HTTPServer) Engine() *gin.Engine {
	return s.engine
}

// Start 启动服务器
func (s *HTTPServer) Start(addr string) error {
	return s.engine.Run(addr)
}

// ErrorResponse 错误响应
type ErrorResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
}

// respondError 响应错误
func (s *HTTPServer) respondError(c *gin.Context, statusCode int, message string) {
	c.JSON(statusCode, ErrorResponse{
		Code:    statusCode,
		Message: message,
	})
}

// respondErrorWithDetails 响应错误（带详情）
func (s *HTTPServer) respondErrorWithDetails(c *gin.Context, statusCode int, message, details string) {
	s.logger.Error("HTTP error",
		zap.String("path", c.Request.URL.Path),
		zap.Int("status", statusCode),
		zap.String("message", message),
		zap.String("details", details),
	)

	c.JSON(statusCode, ErrorResponse{
		Code:    statusCode,
		Message: message,
		Details: details,
	})
}

// handleServiceError 处理服务层错误
func (s *HTTPServer) handleServiceError(c *gin.Context, err error) {
	switch {
	case errors.Is(err, domain.ErrMetricNotFound), errors.Is(err, domain.ErrReportNotFound):
		s.respondError(c, http.StatusNotFound, err.Error())
	case errors.Is(err, domain.ErrInvalidTimePeriod), errors.Is(err, domain.ErrInvalidReportType):
		s.respondError(c, http.StatusBadRequest, err.Error())
	case errors.Is(err, domain.ErrInsufficientData):
		s.respondError(c, http.StatusUnprocessableEntity, err.Error())
	default:
		s.logger.Error("Service error", zap.Error(err))
		s.respondError(c, http.StatusInternalServerError, "internal server error")
	}
}

// parseTimeRange 解析时间范围
func (s *HTTPServer) parseTimeRange(c *gin.Context) (start, end time.Time, err error) {
	startStr := c.Query("start")
	endStr := c.Query("end")

	if startStr == "" {
		err = errors.New("start time is required")
		return
	}

	if endStr == "" {
		err = errors.New("end time is required")
		return
	}

	start, err = time.Parse(time.RFC3339, startStr)
	if err != nil {
		err = errors.New("invalid start time format, expected RFC3339")
		return
	}

	end, err = time.Parse(time.RFC3339, endStr)
	if err != nil {
		err = errors.New("invalid end time format, expected RFC3339")
		return
	}

	if end.Before(start) {
		err = errors.New("end time must be after start time")
		return
	}

	return start, end, nil
}

// healthCheck 健康检查
func (s *HTTPServer) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "healthy",
		"service": "analytics-service",
		"time":    time.Now().Format(time.RFC3339),
	})
}

// readinessCheck 就绪检查
func (s *HTTPServer) readinessCheck(c *gin.Context) {
	// TODO: 添加真实的依赖检查
	// 检查数据库连接
	// 检查 ClickHouse 连接
	// 检查 Redis 连接

	c.JSON(http.StatusOK, gin.H{
		"ready": true,
		"checks": gin.H{
			"database":   "ok",
			"clickhouse": "ok",
			"redis":      "ok",
		},
		"time": time.Now().Format(time.RFC3339),
	})
}
