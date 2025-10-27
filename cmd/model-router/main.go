package main

import (
	"context"
	"fmt"
	"log"
	"model-router/internal/application"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// ModelRouter 模型路由服务
type ModelRouter struct {
	router        *Router
	loadBalancer  *LoadBalancer
	healthChecker *HealthChecker
	costOptimizer *CostOptimizer
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
		// 路由请求
		api.POST("/route", routeRequest)

		// 模型管理
		api.GET("/models", listModels)
		api.GET("/models/:name", getModel)
		api.GET("/models/:name/health", checkModelHealth)

		// 负载均衡
		api.GET("/load", getLoadStats)

		// 成本统计
		api.GET("/cost", getCostStats)
	}

	// 启动服务器
	port := os.Getenv("PORT")
	if port == "" {
		port = "9004"
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

	log.Printf("Model Router started on port %s", port)

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
		"service": "model-router",
	})
}

func readinessCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"ready": true,
		"checks": gin.H{
			"router":       true,
			"loadbalancer": true,
			"models":       true,
		},
	})
}

// 全局路由器（应该在初始化时创建）
var router *application.IntelligentRouter

func routeRequest(c *gin.Context) {
	var req struct {
		Strategy      string `json:"strategy"`       // round_robin, cost_optimized, latency_based, load_balanced
		RequiredModel string `json:"required_model"` // 可选，指定模型
		EstTokens     int    `json:"est_tokens"`     // 预估token数
		TenantID      string `json:"tenant_id"`
		Priority      int    `json:"priority"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 确保路由器已初始化
	if router == nil {
		router = application.NewIntelligentRouter()

		// 注册示例模型（实际应从配置或数据库加载）
		router.RegisterModel(&application.ModelConfig{
			ID:              "gpt-4-turbo",
			Name:            "gpt-4-turbo-preview",
			Provider:        "openai",
			Endpoint:        "https://api.openai.com/v1/chat/completions",
			Priority:        1,
			CostPer1KTokens: 0.03,
			MaxRPS:          100,
			Timeout:         30 * time.Second,
			Enabled:         true,
		})

		router.RegisterModel(&application.ModelConfig{
			ID:              "gpt-3.5-turbo",
			Name:            "gpt-3.5-turbo",
			Provider:        "openai",
			Endpoint:        "https://api.openai.com/v1/chat/completions",
			Priority:        2,
			CostPer1KTokens: 0.002,
			MaxRPS:          500,
			Timeout:         30 * time.Second,
			Enabled:         true,
		})
	}

	// 构建路由请求
	routingReq := &application.RoutingRequest{
		Strategy:      application.RoutingStrategy(req.Strategy),
		RequiredModel: req.RequiredModel,
		EstTokens:     req.EstTokens,
		TenantID:      req.TenantID,
		Priority:      req.Priority,
		Context:       c.Request.Context(),
	}

	// 默认策略
	if routingReq.Strategy == "" {
		routingReq.Strategy = application.StrategyLoadBalanced
	}

	// 执行路由
	result, err := router.Route(routingReq)
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":   "routing_failed",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"model":             result.Model.Name,
		"model_id":          result.Model.ID,
		"provider":          result.Model.Provider,
		"endpoint":          result.Model.Endpoint,
		"routing_reason":    result.Reason,
		"estimated_cost":    result.EstimatedCost,
		"estimated_latency": result.EstimatedLatency,
		"fallback_used":     result.FallbackUsed,
	})
}

func listModels(c *gin.Context) {
	models := []map[string]interface{}{
		{
			"name":        "gpt-4-turbo-preview",
			"provider":    "openai",
			"type":        "chat",
			"cost_per_1k": 0.03,
			"status":      "healthy",
		},
		{
			"name":        "gpt-3.5-turbo",
			"provider":    "openai",
			"type":        "chat",
			"cost_per_1k": 0.002,
			"status":      "healthy",
		},
		{
			"name":        "claude-3-opus",
			"provider":    "anthropic",
			"type":        "chat",
			"cost_per_1k": 0.075,
			"status":      "healthy",
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"models": models,
		"count":  len(models),
	})
}

func getModel(c *gin.Context) {
	name := c.Param("name")

	// TODO: 从实际存储获取模型信息
	c.JSON(http.StatusOK, gin.H{
		"name":        name,
		"provider":    "openai",
		"type":        "chat",
		"cost_per_1k": 0.03,
		"status":      "healthy",
		"endpoints":   []string{"https://api.openai.com/v1/chat/completions"},
	})
}

func checkModelHealth(c *gin.Context) {
	name := c.Param("name")

	// TODO: 实际健康检查
	c.JSON(http.StatusOK, gin.H{
		"model":        name,
		"status":       "healthy",
		"latency_ms":   50,
		"success_rate": 0.999,
		"last_check":   time.Now().Format(time.RFC3339),
	})
}

func getLoadStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_requests":  1000,
		"active_requests": 10,
		"models": []gin.H{
			{
				"name":     "gpt-4-turbo-preview",
				"requests": 600,
				"load":     0.6,
			},
			{
				"name":     "gpt-3.5-turbo",
				"requests": 400,
				"load":     0.4,
			},
		},
	})
}

func getCostStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_cost": 100.50,
		"today_cost": 10.25,
		"models": []gin.H{
			{
				"name":   "gpt-4-turbo-preview",
				"cost":   80.40,
				"tokens": 2680000,
			},
			{
				"name":   "gpt-3.5-turbo",
				"cost":   20.10,
				"tokens": 10050000,
			},
		},
	})
}

// Router 路由器
type Router struct{}

// LoadBalancer 负载均衡器
type LoadBalancer struct{}

// HealthChecker 健康检查器
type HealthChecker struct{}

// CostOptimizer 成本优化器
type CostOptimizer struct{}
