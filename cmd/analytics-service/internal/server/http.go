package server

import (
	"net/http"
	"strconv"
	"time"

	"analytics-service/internal/service"

	"github.com/gin-gonic/gin"
)

// HTTPServer HTTP 服务器
type HTTPServer struct {
	engine  *gin.Engine
	service *service.AnalyticsService
}

// NewHTTPServer 创建 HTTP 服务器
func NewHTTPServer(srv *service.AnalyticsService) *HTTPServer {
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
	s.engine.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})
}

// getUsageStats 获取使用统计
func (s *HTTPServer) getUsageStats(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	period := c.Query("period")
	start, _ := time.Parse(time.RFC3339, c.Query("start"))
	end, _ := time.Parse(time.RFC3339, c.Query("end"))

	stats, err := s.service.GetUsageStats(c.Request.Context(), tenantID, period, start, end)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// getModelStats 获取模型统计
func (s *HTTPServer) getModelStats(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	period := c.Query("period")
	start, _ := time.Parse(time.RFC3339, c.Query("start"))
	end, _ := time.Parse(time.RFC3339, c.Query("end"))

	stats, err := s.service.GetModelStats(c.Request.Context(), tenantID, period, start, end)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// getUserBehavior 获取用户行为统计
func (s *HTTPServer) getUserBehavior(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	userID := c.Param("user_id")
	period := c.Query("period")
	start, _ := time.Parse(time.RFC3339, c.Query("start"))
	end, _ := time.Parse(time.RFC3339, c.Query("end"))

	behavior, err := s.service.GetUserBehavior(c.Request.Context(), tenantID, userID, period, start, end)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, behavior)
}

// getRealtimeStats 获取实时统计
func (s *HTTPServer) getRealtimeStats(c *gin.Context) {
	tenantID := c.Query("tenant_id")

	stats, err := s.service.GetRealtimeStats(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// getCostBreakdown 获取成本分解
func (s *HTTPServer) getCostBreakdown(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	period := c.Query("period")
	start, _ := time.Parse(time.RFC3339, c.Query("start"))
	end, _ := time.Parse(time.RFC3339, c.Query("end"))

	breakdown, err := s.service.GetCostBreakdown(c.Request.Context(), tenantID, period, start, end)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
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
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	reports, total, err := s.service.ListReports(c.Request.Context(), tenantID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
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

// Start 启动服务器
func (s *HTTPServer) Start(addr string) error {
	return s.engine.Run(addr)
}
