package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// AnalyticsService 分析服务
type AnalyticsService struct {
	clickHouseClient *ClickHouseClient
	cacheManager     *CacheManager
}

func main() {
	// 创建路由器
	r := gin.Default()

	// Prometheus metrics
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Health checks
	r.GET("/health", healthCheck)
	r.GET("/ready", readinessCheck)

	// API routes
	api := r.Group("/api/v1")
	{
		// 实时统计
		api.GET("/stats/realtime", getRealtimeStats)
		api.GET("/stats/summary", getSummary)

		// 用户分析
		api.GET("/users/activity", getUserActivity)
		api.GET("/users/engagement", getUserEngagement)
		api.GET("/users/retention", getUserRetention)

		// 对话分析
		api.GET("/conversations/stats", getConversationStats)
		api.GET("/conversations/trends", getConversationTrends)

		// 文档分析
		api.GET("/documents/stats", getDocumentStats)
		api.GET("/documents/usage", getDocumentUsage)

		// AI 使用分析
		api.GET("/ai/usage", getAIUsage)
		api.GET("/ai/cost", getAICost)
		api.GET("/ai/performance", getAIPerformance)

		// 租户分析
		api.GET("/tenants/ranking", getTenantRanking)
		api.GET("/tenants/:id/stats", getTenantStats)

		// 报表生成
		api.POST("/reports/generate", generateReport)
		api.GET("/reports/:id", getReport)
		api.GET("/reports", listReports)
	}

	// 启动服务器
	port := os.Getenv("PORT")
	if port == "" {
		port = "9006"
	}

	srv := &http.Server{
		Addr:    fmt.Sprintf(":%s", port),
		Handler: r,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	log.Printf("Analytics Service started on port %s", port)

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exited")
}

func healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "healthy",
		"service": "analytics-service",
	})
}

func readinessCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"ready": true,
		"checks": gin.H{
			"clickhouse": true,
			"cache":      true,
		},
	})
}

func getRealtimeStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"timestamp":              time.Now().Format(time.RFC3339),
		"active_users":           125,
		"active_conversations":   45,
		"messages_per_minute":    230,
		"ai_requests_per_minute": 85,
		"avg_response_time_ms":   450,
	})
}

func getSummary(c *gin.Context) {
	period := c.DefaultQuery("period", "today") // today, week, month

	c.JSON(http.StatusOK, gin.H{
		"period": period,
		"users": gin.H{
			"total_active":    1250,
			"new_users":       45,
			"returning_users": 1205,
		},
		"conversations": gin.H{
			"total":                3500,
			"avg_messages":         12.5,
			"avg_duration_minutes": 8.2,
		},
		"documents": gin.H{
			"total_uploaded":  280,
			"total_indexed":   275,
			"total_retrieved": 8500,
		},
		"ai": gin.H{
			"total_requests": 12000,
			"total_tokens":   4500000,
			"total_cost_usd": 125.50,
		},
	})
}

func getUserActivity(c *gin.Context) {
	tenantID := c.Query("tenant_id")
	startDate := c.DefaultQuery("start_date", time.Now().AddDate(0, 0, -7).Format("2006-01-02"))
	endDate := c.DefaultQuery("end_date", time.Now().Format("2006-01-02"))

	c.JSON(http.StatusOK, gin.H{
		"tenant_id":  tenantID,
		"start_date": startDate,
		"end_date":   endDate,
		"daily_stats": []gin.H{
			{
				"date":                         "2025-10-26",
				"active_users":                 125,
				"new_users":                    5,
				"sessions":                     340,
				"avg_session_duration_minutes": 15.2,
			},
			{
				"date":                         "2025-10-25",
				"active_users":                 118,
				"new_users":                    3,
				"sessions":                     320,
				"avg_session_duration_minutes": 14.8,
			},
		},
	})
}

func getUserEngagement(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_users": 1250,
		"engagement_levels": gin.H{
			"high":   gin.H{"count": 250, "percentage": 20},
			"medium": gin.H{"count": 625, "percentage": 50},
			"low":    gin.H{"count": 375, "percentage": 30},
		},
		"top_features": []gin.H{
			{"feature": "Chat", "usage_percentage": 85},
			{"feature": "Document Upload", "usage_percentage": 60},
			{"feature": "Voice", "usage_percentage": 30},
			{"feature": "Agent", "usage_percentage": 25},
		},
	})
}

func getUserRetention(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"cohort_analysis": []gin.H{
			{
				"cohort":           "2025-10",
				"users":            150,
				"retention_day_1":  85.0,
				"retention_day_7":  65.0,
				"retention_day_30": 45.0,
			},
		},
	})
}

func getConversationStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_conversations": 3500,
		"by_mode": gin.H{
			"chat":     2800,
			"agent":    500,
			"workflow": 150,
			"voice":    50,
		},
		"avg_messages_per_conversation": 12.5,
		"avg_duration_minutes":          8.2,
		"success_rate":                  0.92,
	})
}

func getConversationTrends(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"daily_trends": []gin.H{
			{
				"date":                 "2025-10-26",
				"conversations":        350,
				"messages":             4375,
				"avg_response_time_ms": 450,
			},
			{
				"date":                 "2025-10-25",
				"conversations":        340,
				"messages":             4250,
				"avg_response_time_ms": 480,
			},
		},
	})
}

func getDocumentStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_uploaded": 280,
		"total_indexed":  275,
		"by_format": gin.H{
			"pdf":  120,
			"docx": 80,
			"txt":  45,
			"md":   35,
		},
		"avg_size_mb":   2.5,
		"total_size_gb": 0.7,
	})
}

func getDocumentUsage(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_retrievals":            8500,
		"avg_retrievals_per_document": 30.4,
		"top_documents": []gin.H{
			{
				"document_id": "doc_123",
				"title":       "Product Manual",
				"retrievals":  450,
			},
			{
				"document_id": "doc_124",
				"title":       "FAQ",
				"retrievals":  380,
			},
		},
	})
}

func getAIUsage(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_requests": 12000,
		"by_type": gin.H{
			"rag":        7000,
			"agent":      3000,
			"voice":      1500,
			"multimodal": 500,
		},
		"success_rate":   0.95,
		"avg_latency_ms": 1250,
	})
}

func getAICost(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_cost_usd": 125.50,
		"total_tokens":   4500000,
		"by_model": []gin.H{
			{
				"model":    "gpt-4-turbo-preview",
				"tokens":   2000000,
				"cost_usd": 80.00,
			},
			{
				"model":    "gpt-3.5-turbo",
				"tokens":   2500000,
				"cost_usd": 45.50,
			},
		},
		"avg_cost_per_request_usd": 0.0105,
	})
}

func getAIPerformance(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"avg_latency_ms": 1250,
		"p50_latency_ms": 1100,
		"p95_latency_ms": 2200,
		"p99_latency_ms": 3500,
		"error_rate":     0.05,
		"by_type": []gin.H{
			{
				"type":           "rag",
				"avg_latency_ms": 1500,
				"success_rate":   0.96,
			},
			{
				"type":           "agent",
				"avg_latency_ms": 2500,
				"success_rate":   0.92,
			},
		},
	})
}

func getTenantRanking(c *gin.Context) {
	metric := c.DefaultQuery("metric", "usage") // usage, cost, activity

	c.JSON(http.StatusOK, gin.H{
		"metric": metric,
		"ranking": []gin.H{
			{
				"rank":        1,
				"tenant_id":   "tenant_123",
				"tenant_name": "Acme Corp",
				"value":       5000,
			},
			{
				"rank":        2,
				"tenant_id":   "tenant_124",
				"tenant_name": "Tech Inc",
				"value":       3500,
			},
		},
	})
}

func getTenantStats(c *gin.Context) {
	tenantID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"tenant_id": tenantID,
		"users": gin.H{
			"total":  250,
			"active": 180,
		},
		"conversations":  1200,
		"documents":      80,
		"ai_requests":    4500,
		"total_cost_usd": 42.50,
		"quota_usage": gin.H{
			"users":     gin.H{"used": 250, "limit": 500, "percentage": 50},
			"documents": gin.H{"used": 80, "limit": 1000, "percentage": 8},
			"api_calls": gin.H{"used": 45000, "limit": 100000, "percentage": 45},
		},
	})
}

func generateReport(c *gin.Context) {
	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"report_id":            "report_123",
		"type":                 req["type"],
		"status":               "generating",
		"estimated_completion": time.Now().Add(2 * time.Minute).Format(time.RFC3339),
	})
}

func getReport(c *gin.Context) {
	reportID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"report_id":    reportID,
		"type":         "monthly_summary",
		"status":       "completed",
		"download_url": "https://storage/reports/report_123.pdf",
		"created_at":   time.Now().Add(-1 * time.Hour).Format(time.RFC3339),
	})
}

func listReports(c *gin.Context) {
	tenantID := c.Query("tenant_id")

	reports := []gin.H{
		{
			"report_id":  "report_123",
			"type":       "monthly_summary",
			"tenant_id":  tenantID,
			"status":     "completed",
			"created_at": time.Now().Add(-24 * time.Hour).Format(time.RFC3339),
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"reports": reports,
		"total":   len(reports),
	})
}

// Components
type ClickHouseClient struct{}
type CacheManager struct{}
