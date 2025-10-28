package server

import (
	"context"
	"net/http"
	"strconv"
	"time"
	"voicehelper/cmd/conversation-service/internal/domain"
	"voicehelper/cmd/conversation-service/internal/service"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
)

// HTTPServer HTTP 服务器
type HTTPServer struct {
	engine  *gin.Engine
	service *service.ConversationService
	logger  log.Logger
}

// NewHTTPServer 创建 HTTP 服务器
func NewHTTPServer(srv *service.ConversationService) *HTTPServer {
	// 创建不带默认中间件的 gin engine
	engine := gin.New()

	// 创建 logger
	logger := log.NewStdLogger(nil)

	s := &HTTPServer{
		engine:  engine,
		service: srv,
		logger:  logger,
	}

	// 注册全局中间件
	s.registerMiddleware()

	// 注册路由
	s.registerRoutes()

	return s
}

// registerMiddleware 注册中间件
func (s *HTTPServer) registerMiddleware() {
	// 恢复中间件（必须最先）
	s.engine.Use(RecoveryMiddleware(s.logger))

	// CORS 中间件
	s.engine.Use(CORSMiddleware())

	// 追踪中间件
	s.engine.Use(TracingMiddleware())

	// 日志中间件
	s.engine.Use(LoggingMiddleware(s.logger))

	// 超时中间件（30秒）
	s.engine.Use(TimeoutMiddleware(30 * time.Second))

	// 认证中间件
	s.engine.Use(AuthMiddleware())

	// 限流中间件
	s.engine.Use(RateLimitMiddleware())
}

// registerRoutes 注册路由
func (s *HTTPServer) registerRoutes() {
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

	// 健康检查
	s.engine.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})
}

// createConversation 创建对话
func (s *HTTPServer) createConversation(c *gin.Context) {
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
	if err != nil {
		Error(c, err)
		return
	}

	Created(c, conversation)
}

// getConversation 获取对话
func (s *HTTPServer) getConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	// 如果没有提供 user_id，尝试从认证上下文获取
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

	conversation, err := s.service.GetConversation(c.Request.Context(), id, userID)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, conversation)
}

// updateConversation 更新对话
func (s *HTTPServer) updateConversation(c *gin.Context) {
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

	// 如果没有提供 user_id，尝试从认证上下文获取
	if req.UserID == "" {
		if uid, exists := c.Get("user_id"); exists {
			req.UserID = uid.(string)
		}
	}

	if err := s.service.UpdateConversationTitle(c.Request.Context(), id, req.UserID, req.Title); err != nil {
		Error(c, err)
		return
	}

	Success(c, nil)
}

// archiveConversation 归档对话
func (s *HTTPServer) archiveConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	// 如果没有提供 user_id，尝试从认证上下文获取
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

	if err := s.service.ArchiveConversation(c.Request.Context(), id, userID); err != nil {
		Error(c, err)
		return
	}

	Success(c, nil)
}

// deleteConversation 删除对话
func (s *HTTPServer) deleteConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	// 如果没有提供 user_id，尝试从认证上下文获取
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

	if err := s.service.DeleteConversation(c.Request.Context(), id, userID); err != nil {
		Error(c, err)
		return
	}

	NoContent(c)
}

// listConversations 列出对话
func (s *HTTPServer) listConversations(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	userID := c.Query("user_id")

	// 如果没有提供，尝试从认证上下文获取
	if tenantID == "" {
		if tid, exists := c.Get("tenant_id"); exists {
			tenantID = tid.(string)
		}
	}
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

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

// sendMessage 发送消息
func (s *HTTPServer) sendMessage(c *gin.Context) {
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

	// 如果没有提供 user_id，尝试从认证上下文获取
	if req.UserID == "" {
		if uid, exists := c.Get("user_id"); exists {
			req.UserID = uid.(string)
		}
	}

	message, err := s.service.SendMessage(
		c.Request.Context(),
		conversationID,
		req.UserID,
		domain.MessageRole(req.Role),
		req.Content,
	)
	if err != nil {
		Error(c, err)
		return
	}

	Created(c, message)
}

// getMessage 获取消息
func (s *HTTPServer) getMessage(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	// 如果没有提供 user_id，尝试从认证上下文获取
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

	message, err := s.service.GetMessage(c.Request.Context(), id, userID)
	if err != nil {
		Error(c, err)
		return
	}

	Success(c, message)
}

// listMessages 列出消息
func (s *HTTPServer) listMessages(c *gin.Context) {
	conversationID := c.Param("id")
	userID := c.Query("user_id")

	// 如果没有提供 user_id，尝试从认证上下文获取
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

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

// getRecentMessages 获取最近的消息
func (s *HTTPServer) getRecentMessages(c *gin.Context) {
	conversationID := c.Param("id")
	userID := c.Query("user_id")

	// 如果没有提供 user_id，尝试从认证上下文获取
	if userID == "" {
		if uid, exists := c.Get("user_id"); exists {
			userID = uid.(string)
		}
	}

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
func (s *HTTPServer) Start(addr string) error {
	return s.engine.Run(addr)
}

// Shutdown 优雅关闭服务器
func (s *HTTPServer) Shutdown(ctx context.Context) error {
	// Gin 没有内置的 Shutdown 方法
	// 实际上，当使用 engine.Run() 时，关闭会通过 context 取消来处理
	// 这里我们只是提供一个接口
	log.Log(log.LevelInfo, "msg", "HTTP server shutting down")
	return nil
}
