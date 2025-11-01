package server

import (
	"context"
	"net/http"
	"time"

	"voicehelper/cmd/conversation-service/internal/middleware"
	"voicehelper/cmd/conversation-service/internal/service"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
)

// HTTPServerV2 增强版 HTTP 服务器
type HTTPServerV2 struct {
	engine         *gin.Engine
	service        *service.ConversationService
	logger         log.Logger

	// 中间件管理器
	jwtManager         *middleware.JWTManager
	rateLimiter        *middleware.RateLimiter
	idempotencyManager *middleware.IdempotencyManager
	auditLogger        *middleware.AuditLogger
	corsManager        *middleware.CORSManager
	healthChecker      *HealthChecker
}

// HTTPServerConfig HTTP 服务器配置
type HTTPServerConfig struct {
	Mode string // debug, release, test

	// 中间件配置
	JWT         *middleware.JWTConfig
	RateLimit   *middleware.RateLimiterConfig
	Idempotency *middleware.IdempotencyConfig
	Audit       *middleware.AuditConfig
	CORS        *middleware.CORSConfig

	// 依赖
	Redis  *redis.Client
	DB     *gorm.DB
}

// NewHTTPServerV2 创建增强版 HTTP 服务器
func NewHTTPServerV2(
	srv *service.ConversationService,
	config *HTTPServerConfig,
	logger log.Logger,
) *HTTPServerV2 {
	// 设置 Gin 模式
	if config.Mode != "" {
		gin.SetMode(config.Mode)
	}

	engine := gin.New()

	// 创建中间件管理器
	jwtManager := middleware.NewJWTManager(config.JWT, logger)
	rateLimiter := middleware.NewRateLimiter(config.Redis, config.RateLimit, logger)
	idempotencyManager := middleware.NewIdempotencyManager(config.Redis, config.Idempotency, logger)
	auditLogger := middleware.NewAuditLogger(config.Audit, logger)
	corsManager := middleware.NewCORSManager(config.CORS, logger)
	healthChecker := NewHealthChecker(config.DB, config.Redis, logger)

	s := &HTTPServerV2{
		engine:             engine,
		service:            srv,
		logger:             logger,
		jwtManager:         jwtManager,
		rateLimiter:        rateLimiter,
		idempotencyManager: idempotencyManager,
		auditLogger:        auditLogger,
		corsManager:        corsManager,
		healthChecker:      healthChecker,
	}

	// 注册中间件（顺序很重要）
	s.registerMiddleware()

	// 注册路由
	s.registerRoutes()

	return s
}

// registerMiddleware 注册中间件
func (s *HTTPServerV2) registerMiddleware() {
	// 1. Recovery 中间件（必须最先，捕获 panic）
	s.engine.Use(RecoveryMiddleware(s.logger))

	// 2. CORS 中间件（早期处理预检请求）
	s.engine.Use(s.corsManager.Middleware())

	// 3. Prometheus 指标采集
	s.engine.Use(middleware.MetricsMiddleware())

	// 4. 追踪中间件（OpenTelemetry）
	s.engine.Use(TracingMiddleware())

	// 5. 日志中间件
	s.engine.Use(LoggingMiddleware(s.logger))

	// 6. JWT 认证中间件（在限流之前，提取用户身份）
	s.engine.Use(s.jwtManager.Middleware())

	// 7. 限流中间件（基于用户身份）
	s.engine.Use(s.rateLimiter.Middleware())

	// 8. 幂等性中间件（写操作）
	s.engine.Use(s.idempotencyManager.Middleware())

	// 9. 审计日志中间件（记录关键操作）
	s.engine.Use(s.auditLogger.Middleware())

	// 10. 超时中间件（30秒）
	s.engine.Use(TimeoutMiddleware(30 * time.Second))
}

// registerRoutes 注册路由
func (s *HTTPServerV2) registerRoutes() {
	// ========================================
	// 健康检查与监控端点（无需认证）
	// ========================================
	s.engine.GET("/health", s.healthChecker.HealthHandler())
	s.engine.GET("/readiness", s.healthChecker.ReadinessHandler())
	s.engine.GET("/health/detailed", s.healthChecker.DetailedHealthHandler())
	s.engine.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ========================================
	// API 路由
	// ========================================
	api := s.engine.Group("/api/v1")

	// 对话接口
	conversations := api.Group("/conversations")
	{
		conversations.POST("", s.createConversation)
		conversations.GET("/:id", s.getConversation)
		conversations.PUT("/:id", s.updateConversation)
		conversations.POST("/:id/archive", s.archiveConversation)
		conversations.DELETE("/:id", s.deleteConversation)
		conversations.GET("", s.listConversations)

		// 消息接口
		conversations.POST("/:id/messages", s.sendMessage)
		conversations.GET("/:id/messages", s.listMessages)
		conversations.GET("/:id/messages/recent", s.getRecentMessages)
	}

	// 消息接口
	messages := api.Group("/messages")
	{
		messages.GET("/:id", s.getMessage)
	}
}

// ========================================
// 处理器实现（与原有实现相同）
// ========================================

func (s *HTTPServerV2) createConversation(c *gin.Context) {
	start := time.Now()

	var req struct {
		TenantID string `json:"tenant_id" binding:"required"`
		UserID   string `json:"user_id" binding:"required"`
		Title    string `json:"title" binding:"required"`
		Mode     string `json:"mode" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, Response{
			Code:    400,
			Message: err.Error(),
		})
		return
	}

	conversation, err := s.service.CreateConversation(
		c.Request.Context(),
		req.TenantID,
		req.UserID,
		req.Title,
		domain.ConversationMode(req.Mode),
	)

	// 记录指标
	middleware.RecordConversationCreateDuration(req.TenantID, time.Since(start))

	if err != nil {
		middleware.RecordConversationOperation("create", "error", req.TenantID)
		Error(c, err)
		return
	}

	middleware.RecordConversationOperation("create", "success", req.TenantID)
	Created(c, conversation)
}

func (s *HTTPServerV2) getConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.GetString("user_id")

	conversation, err := s.service.GetConversation(c.Request.Context(), id, userID)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, conversation)
}

func (s *HTTPServerV2) updateConversation(c *gin.Context) {
	id := c.Param("id")

	var req struct {
		UserID string `json:"user_id"`
		Title  string `json:"title" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, Response{
			Code:    400,
			Message: err.Error(),
		})
		return
	}

	userID := c.GetString("user_id")
	if req.UserID != "" {
		userID = req.UserID
	}

	if err := s.service.UpdateConversationTitle(c.Request.Context(), id, userID, req.Title); err != nil {
		Error(c, err)
		return
	}

	Success(c, nil)
}

func (s *HTTPServerV2) archiveConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.GetString("user_id")

	if err := s.service.ArchiveConversation(c.Request.Context(), id, userID); err != nil {
		Error(c, err)
		return
	}

	Success(c, nil)
}

func (s *HTTPServerV2) deleteConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.GetString("user_id")

	if err := s.service.DeleteConversation(c.Request.Context(), id, userID); err != nil {
		Error(c, err)
		return
	}

	NoContent(c)
}

func (s *HTTPServerV2) listConversations(c *gin.Context) {
	tenantID := c.GetString("tenant_id")
	userID := c.GetString("user_id")

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	conversations, total, err := s.service.ListConversations(c.Request.Context(), tenantID, userID, limit, offset)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, gin.H{
		"conversations": conversations,
		"total":         total,
		"limit":         limit,
		"offset":        offset,
	})
}

func (s *HTTPServerV2) sendMessage(c *gin.Context) {
	start := time.Now()
	conversationID := c.Param("id")

	var req struct {
		UserID  string `json:"user_id"`
		Role    string `json:"role" binding:"required"`
		Content string `json:"content" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, Response{
			Code:    400,
			Message: err.Error(),
		})
		return
	}

	userID := c.GetString("user_id")
	if req.UserID != "" {
		userID = req.UserID
	}

	message, err := s.service.SendMessage(
		c.Request.Context(),
		conversationID,
		userID,
		domain.MessageRole(req.Role),
		req.Content,
	)

	// 记录指标
	tenantID := c.GetString("tenant_id")
	middleware.RecordMessageSendDuration(tenantID, time.Since(start))

	if err != nil {
		Error(c, err)
		return
	}

	Created(c, message)
}

func (s *HTTPServerV2) getMessage(c *gin.Context) {
	id := c.Param("id")
	userID := c.GetString("user_id")

	message, err := s.service.GetMessage(c.Request.Context(), id, userID)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, message)
}

func (s *HTTPServerV2) listMessages(c *gin.Context) {
	conversationID := c.Param("id")
	userID := c.GetString("user_id")

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	messages, total, err := s.service.ListMessages(c.Request.Context(), conversationID, userID, limit, offset)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, gin.H{
		"messages": messages,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

func (s *HTTPServerV2) getRecentMessages(c *gin.Context) {
	conversationID := c.Param("id")
	userID := c.GetString("user_id")

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "10"))

	messages, err := s.service.GetRecentMessages(c.Request.Context(), conversationID, userID, limit)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, gin.H{
		"messages": messages,
	})
}

// Start 启动服务器
func (s *HTTPServerV2) Start(addr string) error {
	return s.engine.Run(addr)
}

// Shutdown 优雅关闭服务器
func (s *HTTPServerV2) Shutdown(ctx context.Context) error {
	log.Log(log.LevelInfo, "msg", "HTTP server shutting down")
	// TODO: 实现优雅关闭
	return nil
}
