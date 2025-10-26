package server

import (
	"net/http"
	"strconv"

	"conversation-service/internal/domain"
	"conversation-service/internal/service"

	"github.com/gin-gonic/gin"
)

// HTTPServer HTTP 服务器
type HTTPServer struct {
	engine  *gin.Engine
	service *service.ConversationService
}

// NewHTTPServer 创建 HTTP 服务器
func NewHTTPServer(srv *service.ConversationService) *HTTPServer {
	engine := gin.Default()

	s := &HTTPServer{
		engine:  engine,
		service: srv,
	}

	s.registerRoutes()

	return s
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
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
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
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, conversation)
}

// getConversation 获取对话
func (s *HTTPServer) getConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	conversation, err := s.service.GetConversation(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, conversation)
}

// updateConversation 更新对话
func (s *HTTPServer) updateConversation(c *gin.Context) {
	id := c.Param("id")

	var req struct {
		UserID string `json:"user_id" binding:"required"`
		Title  string `json:"title" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := s.service.UpdateConversationTitle(c.Request.Context(), id, req.UserID, req.Title); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusOK)
}

// archiveConversation 归档对话
func (s *HTTPServer) archiveConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	if err := s.service.ArchiveConversation(c.Request.Context(), id, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusOK)
}

// deleteConversation 删除对话
func (s *HTTPServer) deleteConversation(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	if err := s.service.DeleteConversation(c.Request.Context(), id, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusNoContent)
}

// listConversations 列出对话
func (s *HTTPServer) listConversations(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	userID := c.Query("user_id")
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	conversations, total, err := s.service.ListConversations(c.Request.Context(), tenantID, userID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
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
		UserID  string `json:"user_id" binding:"required"`
		Role    string `json:"role" binding:"required"`
		Content string `json:"content" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	message, err := s.service.SendMessage(
		c.Request.Context(),
		conversationID,
		req.UserID,
		domain.MessageRole(req.Role),
		req.Content,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, message)
}

// getMessage 获取消息
func (s *HTTPServer) getMessage(c *gin.Context) {
	id := c.Param("id")
	userID := c.Query("user_id")

	message, err := s.service.GetMessage(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, message)
}

// listMessages 列出消息
func (s *HTTPServer) listMessages(c *gin.Context) {
	conversationID := c.Param("id")
	userID := c.Query("user_id")
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	messages, total, err := s.service.ListMessages(c.Request.Context(), conversationID, userID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
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
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "10"))

	messages, err := s.service.GetRecentMessages(c.Request.Context(), conversationID, userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"messages": messages,
	})
}

// Start 启动服务器
func (s *HTTPServer) Start(addr string) error {
	return s.engine.Run(addr)
}
